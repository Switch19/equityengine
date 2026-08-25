"""
Notification creation. Every notification is persisted to the
database (so it's visible when the user next logs in, even if they
were offline when it happened) AND pushed live over WebSocket if the
target user currently has an open connection — see connection_manager.py.
"""
from sqlalchemy.orm import Session

from app.models import Notification


async def create_notification(
    db: Session, user_id, notification_type: str, message: str, related_id=None, push: bool = True,
) -> Notification:
    notification = Notification(
        user_id=user_id, type=notification_type, message=message, related_id=related_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    if push:
        # Imported here, not at module level, to avoid a circular
        # import: connection_manager doesn't need to know about
        # notifications, but notifications need to know how to push.
        from app.services.connection_manager import manager
        await manager.send_personal_message(str(user_id), {
            "event": "notification",
            "id": str(notification.id),
            "type": notification.type,
            "message": notification.message,
            "related_id": str(related_id) if related_id else None,
            "created_at": notification.created_at.isoformat(),
        })

    return notification
