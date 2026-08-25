"""
Chat authorization and message persistence.

DESIGN CONSTRAINT worth reading before touching this file: chatting
inherently exposes identity — a message thread is tied to a real user
account, and conversation content itself often reveals who someone is
even if the platform tried to keep it anonymous. Allowing chat before
progressive reveal would therefore be a backdoor around the entire
BDIOF anonymisation mechanism built in Phase 6. can_users_chat() below
is the single gate that prevents this, and it is checked on every
message send, not just once when a conversation "opens" — a job's
screening mode can't change after the fact, but checking every time
costs nothing and removes any risk of a stale-permission bug.
"""
from sqlalchemy.orm import Session

from app.models import User, UserRole, CandidateProfile, Job, Application, Message, ScreeningMode
from app.services.audit_service import has_been_revealed


class ChatAuthorizationError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def can_users_chat(db: Session, user_a: User, user_b: User, job_id) -> Application:
    """
    Returns the linking Application if user_a and user_b are permitted
    to chat about job_id, otherwise raises ChatAuthorizationError.
    Returning the Application (rather than just True/False) saves the
    caller a second query, since callers generally need it anyway
    (e.g. to log an audit entry).
    """
    if user_a.role == user_b.role:
        raise ChatAuthorizationError("Chat is only between a candidate and a recruiter, not two users of the same role.")

    candidate_user = user_a if user_a.role == UserRole.candidate else user_b
    recruiter_user = user_b if user_a.role == UserRole.candidate else user_a

    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise ChatAuthorizationError("Job not found.", status_code=404)
    if job.recruiter_id != recruiter_user.id:
        raise ChatAuthorizationError("This job does not belong to the recruiter in this conversation.")

    candidate_profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == candidate_user.id).first()
    if not candidate_profile:
        raise ChatAuthorizationError("Candidate profile not found.", status_code=404)

    application = (
        db.query(Application)
        .filter(Application.candidate_id == candidate_profile.id, Application.job_id == job_id)
        .first()
    )
    if not application:
        raise ChatAuthorizationError("This candidate has not applied to this job — no basis for a conversation.")

    if job.screening_mode != ScreeningMode.standard:
        if not has_been_revealed(db, recruiter_user.id, candidate_profile.id, job.id):
            raise ChatAuthorizationError(
                "This application is still under anonymised screening. Chat opens once the "
                "recruiter requests an interview (or otherwise reveals identity) for this application.",
                status_code=403,
            )

    return application


def save_message(
    db: Session, sender_id, receiver_id, job_id, content: str | None = None,
    file_url: str | None = None, file_name: str | None = None, file_type: str | None = None,
) -> Message:
    message = Message(
        sender_id=sender_id, receiver_id=receiver_id, job_id=job_id,
        content=content, file_url=file_url, file_name=file_name, file_type=file_type,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_thread(db: Session, user_a_id, user_b_id, job_id) -> list[Message]:
    return (
        db.query(Message)
        .filter(
            Message.job_id == job_id,
            (
                ((Message.sender_id == user_a_id) & (Message.receiver_id == user_b_id))
                | ((Message.sender_id == user_b_id) & (Message.receiver_id == user_a_id))
            ),
        )
        .order_by(Message.created_at.asc())
        .all()
    )


def mark_thread_read(db: Session, reader_id, other_user_id, job_id) -> int:
    """Marks all messages FROM other_user_id TO reader_id in this
    thread as read. Returns the count updated, so the caller can skip
    a websocket push if nothing actually changed."""
    updated = (
        db.query(Message)
        .filter(
            Message.job_id == job_id,
            Message.sender_id == other_user_id,
            Message.receiver_id == reader_id,
            Message.is_read == False,  # noqa: E712
        )
        .update({"is_read": True})
    )
    db.commit()
    return updated


def list_conversations(db: Session, user_id) -> list[dict]:
    """
    Returns one entry per distinct (other_user, job) pair this user
    has exchanged messages in, each with the most recent message, an
    unread count, and enough context (other party's name, job title)
    for an inbox UI to be usable without a second round-trip per
    conversation. Built in Python over a bounded result set rather
    than a single complex SQL aggregate query, which is easier to
    verify is correct at this project's scale and avoids a fragile
    hand-written GROUP BY across a computed "other user" column.
    """
    messages = (
        db.query(Message)
        .filter((Message.sender_id == user_id) | (Message.receiver_id == user_id))
        .order_by(Message.created_at.desc())
        .all()
    )

    conversations: dict[tuple, dict] = {}
    for m in messages:
        other_id = m.receiver_id if m.sender_id == user_id else m.sender_id
        key = (str(other_id), str(m.job_id))
        if key not in conversations:
            conversations[key] = {
                "other_user_id": str(other_id),
                "job_id": str(m.job_id),
                "last_message": m.content or f"[{m.file_type or 'file'}]",
                "last_message_at": m.created_at.isoformat(),
                "unread_count": 0,
            }
        if m.receiver_id == user_id and not m.is_read:
            conversations[key]["unread_count"] += 1

    if not conversations:
        return []

    other_user_ids = {v["other_user_id"] for v in conversations.values()}
    job_ids = {v["job_id"] for v in conversations.values()}

    users_by_id = {
        str(u.id): u for u in db.query(User).filter(User.id.in_(other_user_ids)).all()
    }
    jobs_by_id = {
        str(j.id): j for j in db.query(Job).filter(Job.id.in_(job_ids)).all()
    }

    for conv in conversations.values():
        other_user = users_by_id.get(conv["other_user_id"])
        job = jobs_by_id.get(conv["job_id"])
        conv["other_user_name"] = other_user.full_name if other_user else "Unknown user"
        conv["other_user_role"] = other_user.role.value if other_user else None
        conv["job_title"] = job.title if job else "Unknown job"

    return list(conversations.values())
