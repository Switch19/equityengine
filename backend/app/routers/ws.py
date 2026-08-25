"""
WebSocket endpoint for real-time chat and notification push.

Authentication note: standard HTTP Bearer-token auth (via the
Authorization header) doesn't work cleanly for WebSocket connections —
not all WebSocket clients (including browser JavaScript's native
WebSocket API) let you set custom headers on the handshake request. The
common, pragmatic pattern — used here — is to pass the JWT as a query
parameter instead: ws://host/ws/connect?token=<jwt>. This is somewhat
less secure than a header (query strings can end up in server access
logs), which is an acceptable trade-off for a final-year project demo
but worth a one-line mention as a limitation in Chapter 5 if you want
to be thorough.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import User
from app.security import decode_access_token
from app.services.connection_manager import manager
from app.services.chat_service import can_users_chat, ChatAuthorizationError, save_message
from app.services.notification_service import create_notification

router = APIRouter(tags=["websocket"])


def _authenticate_ws_token(token: str, db: Session) -> User | None:
    payload = decode_access_token(token)
    if not payload:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    return db.query(User).filter(User.id == user_id).first()


@router.websocket("/ws/connect")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    db = SessionLocal()
    try:
        user = _authenticate_ws_token(token, db)
        if not user:
            await websocket.close(code=4001)  # custom code: authentication failed
            return
        if not user.is_active:
            await websocket.close(code=4003)  # custom code: account deactivated
            return

        user_id_str = str(user.id)
        await manager.connect(user_id_str, websocket)

        try:
            while True:
                data = await websocket.receive_json()
                await _handle_incoming_message(db, user, data)
        except WebSocketDisconnect:
            manager.disconnect(user_id_str)
    finally:
        db.close()


async def _handle_incoming_message(db: Session, sender: User, data: dict):
    """
    Expected incoming payload shape:
        {"receiver_id": "...", "job_id": "...", "content": "..."}
    File attachments are NOT sent over the WebSocket — see messages.py's
    /send-file REST endpoint for those (see that file's docstring for
    why). This handler only deals with plain text messages.
    """
    receiver_id = data.get("receiver_id")
    job_id = data.get("job_id")
    content = data.get("content", "").strip()

    if not receiver_id or not job_id or not content:
        await manager.send_personal_message(str(sender.id), {
            "event": "error", "detail": "Message must include receiver_id, job_id, and non-empty content.",
        })
        return

    receiver = db.query(User).filter(User.id == receiver_id).first()
    if not receiver:
        await manager.send_personal_message(str(sender.id), {"event": "error", "detail": "Recipient not found."})
        return

    try:
        can_users_chat(db, sender, receiver, job_id)
    except ChatAuthorizationError as e:
        await manager.send_personal_message(str(sender.id), {"event": "error", "detail": e.message})
        return

    message = save_message(db, sender_id=sender.id, receiver_id=receiver_id, job_id=job_id, content=content)

    await manager.send_personal_message(str(sender.id), {
        "event": "message_sent",
        "message_id": str(message.id),
        "created_at": message.created_at.isoformat(),
    })

    delivered_live = await manager.send_personal_message(str(receiver_id), {
        "event": "new_message",
        "message_id": str(message.id),
        "sender_id": str(sender.id),
        "job_id": str(job_id),
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    })

    await create_notification(
        db, user_id=receiver_id, notification_type="message",
        message=f"New message from {sender.full_name}: {content[:80]}",
        related_id=message.id,
        push=not delivered_live,
    )
