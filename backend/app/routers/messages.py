from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.message import Message
from app.models.user import User
from pydantic import BaseModel

router = APIRouter()

class MessageCreate(BaseModel):
    sender_id: int
    receiver_id: int
    job_id: int
    content: str

@router.post("/send")
def send_message(msg: MessageCreate, db: Session = Depends(get_db)):
    new_message = Message(
        sender_id=msg.sender_id,
        receiver_id=msg.receiver_id,
        job_id=msg.job_id,
        content=msg.content
    )
    db.add(new_message)
    db.commit()
    db.refresh(new_message)
    return {"message": "Message sent", "id": new_message.id}

@router.get("/{job_id}/{user1_id}/{user2_id}")
def get_messages(job_id: int, user1_id: int, user2_id: int, db: Session = Depends(get_db)):
    messages = db.query(Message).filter(
        Message.job_id == job_id,
        ((Message.sender_id == user1_id) & (Message.receiver_id == user2_id)) |
        ((Message.sender_id == user2_id) & (Message.receiver_id == user1_id))
    ).order_by(Message.created_at).all()

    result = []
    for msg in messages:
        sender = db.query(User).filter(User.id == msg.sender_id).first()
        result.append({
            "id": msg.id,
            "sender_id": msg.sender_id,
            "sender_name": sender.full_name if sender else "Unknown",
            "receiver_id": msg.receiver_id,
            "content": msg.content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None
        })

    return {"messages": result, "count": len(result)}

@router.get("/inbox/{user_id}")
def get_inbox(user_id: int, db: Session = Depends(get_db)):
    """Get all conversations for a user."""
    messages = db.query(Message).filter(
        (Message.sender_id == user_id) | (Message.receiver_id == user_id)
    ).order_by(Message.created_at.desc()).all()

    conversations = {}
    for msg in messages:
        other_id = msg.receiver_id if msg.sender_id == user_id else msg.sender_id
        key = f"{min(user_id, other_id)}-{max(user_id, other_id)}-{msg.job_id}"
        if key not in conversations:
            other_user = db.query(User).filter(User.id == other_id).first()
            conversations[key] = {
                "other_user_id": other_id,
                "other_user_name": other_user.full_name if other_user else "Unknown",
                "job_id": msg.job_id,
                "last_message": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }

    return {"conversations": list(conversations.values())}