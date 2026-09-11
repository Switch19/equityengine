"""
Admin registry and live activity feed — the read side of the audit trail.

audit_service.py WRITES an audit row at the point of each recruiter
action; this module READS those rows back out, alongside candidate and
recruiter roster listings, for the Admin Dashboard's monitoring view.
The split matters: nothing here ever writes, so polling these functions
every few seconds from an open dashboard cannot mutate the trail it is
displaying.

Everything in this module is admin-only *by construction*. The three
functions below are each exposed through exactly one route in
routers/admin.py, behind require_role(UserRole.admin), and there is
deliberately no candidate- or recruiter-reachable route anywhere in the
app that returns candidate rosters, recruiter rosters, or audit rows.
That is the enforcement point — see the note at the top of
routers/admin.py before adding any new caller.

Query shape: per-entity counts are fetched up front as grouped
aggregates and joined in Python, so the number of database round-trips
is constant regardless of how many rows come back. The obvious
alternative — one COUNT per candidate inside the row loop — is an N+1
that works fine on seed data but degrades visibly once a dashboard is
polling it on an interval.
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Application, ApplicationStatus, AuditLog, CandidateProfile, Company, Job, User, UserRole,
)
from app.services.bias_audit_engine import SELECTED_STATUSES

# Actions the activity feed offers as filter options.
#
# Derived from ApplicationStatus rather than hardcoded, because
# routers/recruiters.py logs decision actions as
# `action=payload.status.value` — so every status value is a possible
# action string, and a hardcoded list would silently go stale the next
# time a status is added to the enum. "revealed" is appended separately:
# it is logged as a literal, not a status, since identity reveal is a
# side effect of a decision rather than a decision in itself.
#
# An action present in the log but missing here still shows up in an
# unfiltered feed; it just isn't offered in the dropdown.
KNOWN_ACTIONS = [status.value for status in ApplicationStatus] + ["revealed"]

MAX_FEED_PAGE_SIZE = 200


# ---------------------------------------------------------------------
# Candidate roster
# ---------------------------------------------------------------------

def list_candidates(db: Session) -> list[dict]:
    """
    Every candidate account with its profile-completion and evidence
    figures, newest registration first.

    Uses an outer join to CandidateProfile: a candidate who has
    registered but not yet built a profile must still appear in the
    roster (an admin looking for drop-off after signup specifically
    needs to see those), so a missing profile yields zeroes rather
    than dropping the row.
    """
    application_counts = _count_by(db, Application.candidate_id, Application.id)
    shortlist_counts = _count_by(
        db, Application.candidate_id, Application.id,
        filters=[Application.status.in_(SELECTED_STATUSES)],
    )
    # Latest recruiter action against each candidate — the closest
    # thing to "last seen by the platform" that the audit trail holds.
    last_action_at = dict(
        db.query(AuditLog.candidate_id, func.max(AuditLog.created_at))
        .group_by(AuditLog.candidate_id)
        .all()
    )

    rows = (
        db.query(User, CandidateProfile)
        .outerjoin(CandidateProfile, CandidateProfile.user_id == User.id)
        .filter(User.role == UserRole.candidate)
        .order_by(User.created_at.desc())
        .all()
    )

    results = []
    for user, profile in rows:
        profile_id = profile.id if profile else None
        results.append({
            "candidate_id": str(profile_id) if profile_id else None,
            "user_id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
            "has_profile": profile is not None,
            "location": profile.location if profile else None,
            "education_tier": profile.education_tier if profile else None,
            "experience_level": profile.experience_level if profile else None,
            "evidence_score": profile.evidence_score if profile else 0.0,
            "profile_completeness": profile.profile_completeness if profile else 0.0,
            # Which of the three evidence pipelines this candidate has
            # actually connected. Read straight off stored columns
            # rather than recomputing the Competency Profile per row —
            # that would mean running the competency engine once per
            # candidate on every poll.
            "has_cv": bool(profile and profile.cv_skills),
            "has_github": bool(profile and profile.github_username),
            "has_community": bool(
                profile and (profile.certifications or profile.stackoverflow_data or profile.devto_data)
            ),
            "total_applications": application_counts.get(profile_id, 0),
            "total_shortlisted": shortlist_counts.get(profile_id, 0),
            "registered_at": user.created_at,
            "last_action_at": last_action_at.get(profile_id),
        })
    return results


# ---------------------------------------------------------------------
# Recruiter roster
# ---------------------------------------------------------------------

def list_recruiters(db: Session) -> list[dict]:
    """
    Every recruiter account with posting and screening volume, newest
    registration first.

    Deliberately does NOT include the recruiter's bias score. That
    lives on /admin/recruiters/bias-scores and is computed by the Bias
    Audit Engine; keeping the two separate means this roster stays a
    cheap, pollable listing rather than triggering a full bias
    recomputation every few seconds.
    """
    job_counts = _count_by(db, Job.recruiter_id, Job.id)
    active_job_counts = _count_by(db, Job.recruiter_id, Job.id, filters=[Job.is_active.is_(True)])

    # Applications received across all of a recruiter's jobs, and how
    # many of those they moved forward. Grouped on Job.recruiter_id via
    # a join so this stays one query rather than one per recruiter.
    applications_received = dict(
        db.query(Job.recruiter_id, func.count(Application.id))
        .join(Application, Application.job_id == Job.id)
        .group_by(Job.recruiter_id)
        .all()
    )
    shortlisted_by_recruiter = dict(
        db.query(Job.recruiter_id, func.count(Application.id))
        .join(Application, Application.job_id == Job.id)
        .filter(Application.status.in_(SELECTED_STATUSES))
        .group_by(Job.recruiter_id)
        .all()
    )

    action_counts = _recruiter_action_counts(db)
    last_action_at = dict(
        db.query(AuditLog.recruiter_id, func.max(AuditLog.created_at))
        .group_by(AuditLog.recruiter_id)
        .all()
    )
    company_names = dict(
        db.query(Company.recruiter_id, func.min(Company.name))
        .group_by(Company.recruiter_id)
        .all()
    )

    recruiters = (
        db.query(User)
        .filter(User.role == UserRole.recruiter)
        .order_by(User.created_at.desc())
        .all()
    )

    results = []
    for user in recruiters:
        per_action = action_counts.get(user.id, {})
        results.append({
            "user_id": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
            "company_name": company_names.get(user.id),
            "total_jobs": job_counts.get(user.id, 0),
            "active_jobs": active_job_counts.get(user.id, 0),
            "total_applications_received": applications_received.get(user.id, 0),
            "total_shortlisted": shortlisted_by_recruiter.get(user.id, 0),
            "total_views": per_action.get("viewed", 0),
            "total_reveals": per_action.get("revealed", 0),
            "registered_at": user.created_at,
            "last_action_at": last_action_at.get(user.id),
        })
    return results


# ---------------------------------------------------------------------
# Live activity feed (audit log)
# ---------------------------------------------------------------------

def list_activity_log(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    action: str | None = None,
) -> dict:
    """
    Newest-first page of the raw audit trail, with recruiter names,
    candidate names, and job titles resolved for display.

    Names are resolved in three bulk lookups after the page is
    fetched, not by walking ORM relationships per row — AuditLog
    intentionally declares no relationships (see models.py), and lazy
    loading them would be an N+1 against a table that grows with every
    recruiter action.
    """
    limit = max(1, min(limit, MAX_FEED_PAGE_SIZE))
    offset = max(0, offset)

    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)

    total_count = query.count()
    rows = (
        query
        # id is the tiebreaker: created_at is only second-resolution in
        # practice, and without a stable secondary sort two rows
        # written in the same second could swap places between polls
        # and appear to duplicate across page boundaries.
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    recruiter_names = _bulk_names(db, {r.recruiter_id for r in rows})
    candidate_names = _bulk_candidate_names(db, {r.candidate_id for r in rows})
    job_titles = _bulk_job_titles(db, {r.job_id for r in rows if r.job_id})

    logs = [
        {
            "id": str(row.id),
            "action": row.action,
            "was_anonymized": row.was_anonymized,
            "screening_mode": row.screening_mode.value if row.screening_mode else None,
            "time_spent_seconds": row.time_spent_seconds,
            "created_at": row.created_at,
            "recruiter_id": str(row.recruiter_id),
            "recruiter_name": recruiter_names.get(row.recruiter_id, "Unknown recruiter"),
            "candidate_id": str(row.candidate_id),
            # A candidate name is shown here even for an action taken
            # under anonymised screening. That is intentional and is
            # the point of an audit trail: the recruiter could not see
            # the identity at decision time (was_anonymized records
            # that), but the auditor reviewing the decision must be
            # able to. This is exactly why the whole module is
            # admin-gated.
            "candidate_name": candidate_names.get(row.candidate_id, "Unknown candidate"),
            "job_id": str(row.job_id) if row.job_id else None,
            "job_title": job_titles.get(row.job_id) if row.job_id else None,
        }
        for row in rows
    ]

    return {
        "logs": logs,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "available_actions": KNOWN_ACTIONS,
        # Lets the dashboard show "as of <time>" against the server's
        # clock rather than the browser's, which may differ.
        "server_time": datetime.utcnow(),
    }


# ---------------------------------------------------------------------
# Internal query helpers
# ---------------------------------------------------------------------

def _count_by(db: Session, group_column, count_column, filters=None) -> dict:
    """COUNT(count_column) grouped by group_column, as a plain dict."""
    query = db.query(group_column, func.count(count_column))
    for condition in filters or []:
        query = query.filter(condition)
    return dict(query.group_by(group_column).all())


def _recruiter_action_counts(db: Session) -> dict:
    """
    {recruiter_id: {action: count}} across the whole audit log, built
    from one grouped query rather than one per (recruiter, action).
    """
    counts: dict = {}
    rows = (
        db.query(AuditLog.recruiter_id, AuditLog.action, func.count(AuditLog.id))
        .group_by(AuditLog.recruiter_id, AuditLog.action)
        .all()
    )
    for recruiter_id, action, count in rows:
        counts.setdefault(recruiter_id, {})[action] = count
    return counts


def _bulk_names(db: Session, user_ids: set) -> dict:
    if not user_ids:
        return {}
    return dict(db.query(User.id, User.full_name).filter(User.id.in_(user_ids)).all())


def _bulk_candidate_names(db: Session, candidate_profile_ids: set) -> dict:
    """
    Keyed by CandidateProfile.id, not User.id — AuditLog.candidate_id
    is a foreign key to candidate_profiles, while recruiter_id points
    at users. Mixing the two up yields a feed of "Unknown candidate"
    rows that still returns 200, so the join here is deliberate.
    """
    if not candidate_profile_ids:
        return {}
    return dict(
        db.query(CandidateProfile.id, User.full_name)
        .join(User, User.id == CandidateProfile.user_id)
        .filter(CandidateProfile.id.in_(candidate_profile_ids))
        .all()
    )


def _bulk_job_titles(db: Session, job_ids: set) -> dict:
    if not job_ids:
        return {}
    return dict(db.query(Job.id, Job.title).filter(Job.id.in_(job_ids)).all())
