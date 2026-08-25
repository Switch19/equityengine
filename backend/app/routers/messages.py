"""
REST endpoints for chat. Real-time delivery happens over WebSocket
(see ws.py), but these REST endpoints exist for: fetching history when
a conversation is opened, sending a message from a client not using
the WebSocket connection, and file attachments (kept as a REST
multipart upload rather than encoding file bytes over the WebSocket
connection, which is unnecessarily complex for this project's scale).
"""
import os
import uuid as uuid_lib
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import MessageCreate, MessageOut, ConversationOut, NotificationOut, UnreadCountOut
from app.deps import get_current_user
from app.services.chat_service import (
    can_users_chat, ChatAuthorizationError, save_message, get_thread,
    mark_thread_read, list_conversations,
)
from app.services.connection_manager import manager
from app.services.notification_service import create_notification

router = APIRouter(prefix="/messages", tags=["messages"])

UPLOAD_DIR = "uploads/chat"
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


@router.get("/conversations", response_model=list[ConversationOut])
def get_my_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return list_conversations(db, current_user.id)


@router.get("/thread/{other_user_id}/{job_id}", response_model=list[MessageOut])
def get_message_thread(
    other_user_id: uuid_lib.UUID,
    job_id: uuid_lib.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    other_user = db.query(User).filter(User.id == other_user_id).first()
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        can_users_chat(db, current_user, other_user, job_id)
    except ChatAuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    mark_thread_read(db, reader_id=current_user.id, other_user_id=other_user_id, job_id=job_id)
    return get_thread(db, current_user.id, other_user_id, job_id)


@router.post("/send", response_model=MessageOut, status_code=201)
async def send_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receiver = db.query(User).filter(User.id == payload.receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found")

    try:
        can_users_chat(db, current_user, receiver, payload.job_id)
    except ChatAuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    message = save_message(
        db, sender_id=current_user.id, receiver_id=payload.receiver_id,
        job_id=payload.job_id, content=payload.content,
    )

    await _push_message_and_notify(db, message, current_user)
    return message


@router.post("/send-file", response_model=MessageOut, status_code=201)
async def send_file_message(
    receiver_id: uuid_lib.UUID = Form(...),
    job_id: uuid_lib.UUID = Form(...),
    caption: str = Form(""),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="Recipient not found")

    try:
        can_users_chat(db, current_user, receiver, job_id)
    except ChatAuthorizationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    safe_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    message = save_message(
        db, sender_id=current_user.id, receiver_id=receiver_id, job_id=job_id,
        content=caption or None, file_url=f"/uploads/chat/{safe_filename}",
        file_name=file.filename, file_type=file.content_type,
    )

    await _push_message_and_notify(db, message, current_user)
    return message


async def _push_message_and_notify(db: Session, message, sender: User):
    """Shared by both send endpoints: push the message live if the
    receiver is online, and create a persisted notification either way
    (notifications aren't skipped just because the user is currently
    connected — they still want a notification-bell entry)."""
    await manager.send_personal_message(str(message.receiver_id), {
        "event": "new_message",
        "message_id": str(message.id),
        "sender_id": str(message.sender_id),
        "job_id": str(message.job_id),
        "content": message.content,
        "file_url": message.file_url,
        "file_name": message.file_name,
        "created_at": message.created_at.isoformat(),
    })

    preview = message.content or f"sent a file: {message.file_name}"
    await create_notification(
        db, user_id=message.receiver_id, notification_type="message",
        message=f"New message from {sender.full_name}: {preview[:80]}",
        related_id=message.id,
    )


# ---------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notifications_router.get("", response_model=list[NotificationOut])
def get_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Notification
    return (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )


@notifications_router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Notification
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.is_read == False)  # noqa: E712
        .count()
    )
    return {"unread_count": count}


@notifications_router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid_lib.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Notification
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == current_user.id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.is_read = True
    db.commit()
    return {"detail": "Marked as read"}


@notifications_router.patch("/read-all")
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import Notification
    db.query(Notification).filter(
        Notification.user_id == current_user.id, Notification.is_read == False  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"detail": "All notifications marked as read"}
