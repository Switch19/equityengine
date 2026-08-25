"""
Audit logging and view-rate-limiting.

Every recruiter action on a candidate gets logged here with an
explicit was_anonymized flag — this is the raw data the Bias Audit
Engine (a later phase) will aggregate into the Visibility Gap metric.
Logging happens at the point of action, not reconstructed later, so
the audit trail can't be retroactively edited to look more favourable.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditLog, ApplicationStatus

MAX_VIEWS_BEFORE_DECISION_REQUIRED = 5


def log_action(
    db: Session,
    recruiter_id,
    candidate_id,
    job_id,
    action: str,
    was_anonymized: bool,
    screening_mode,
    time_spent_seconds: int | None = None,
) -> AuditLog:
    entry = AuditLog(
        recruiter_id=recruiter_id,
        candidate_id=candidate_id,
        job_id=job_id,
        action=action,
        was_anonymized=was_anonymized,
        screening_mode=screening_mode,
        time_spent_seconds=time_spent_seconds,
    )
    db.add(entry)
    db.commit()
    return entry


def count_recruiter_views(db: Session, recruiter_id, candidate_id) -> int:
    """
    Counts "viewed" actions by this recruiter against this candidate,
    across ALL jobs — the rate limit is per (recruiter, candidate)
    pair platform-wide, not per job, since the underlying bias
    behaviour this guards against (endlessly re-viewing a profile
    without deciding, in case someone "better" turns up) isn't
    scoped to a single posting.
    """
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.recruiter_id == recruiter_id,
            AuditLog.candidate_id == candidate_id,
            AuditLog.action == "viewed",
        )
        .count()
    )


def check_view_limit(db: Session, recruiter_id, candidate_id, current_status: ApplicationStatus) -> dict:
    """
    Returns whether this recruiter has hit the view cap for this
    candidate. A candidate already past the "undecided" stage
    (shortlisted, interview, rejected, offered) is exempt — the limit
    exists to force a decision, and a decision has already been made.
    """
    if current_status != ApplicationStatus.applied and current_status != ApplicationStatus.viewed:
        return {"limited": False, "views_so_far": None}

    views_so_far = count_recruiter_views(db, recruiter_id, candidate_id)
    return {
        "limited": views_so_far >= MAX_VIEWS_BEFORE_DECISION_REQUIRED,
        "views_so_far": views_so_far,
    }


def has_been_revealed(db: Session, recruiter_id, candidate_id, job_id) -> bool:
    """
    Reveal state is derived from the audit log, not a stored flag — a
    rejected-after-interview application must stay revealed, but
    "rejected" isn't itself a reveal-triggering status, so current
    status alone can't tell us whether reveal already happened
    earlier. Shared by recruiters.py (dossier views) and the chat
    system (Phase 8) — both need the exact same answer to "has this
    recruiter legitimately seen this candidate's identity for this
    job yet?", and duplicating this check in two places would risk
    them silently drifting apart.
    """
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.recruiter_id == recruiter_id,
            AuditLog.candidate_id == candidate_id,
            AuditLog.job_id == job_id,
            AuditLog.action == "revealed",
        )
        .first()
        is not None
    )
