"""
Recruiter Talent Pool — proactive sourcing across every registered
candidate, rather than reactive review of one job's applicants.

This is the counterpart to dossier_service.py, and the distinction
between the two is the important thing in this file:

    dossier_service  — candidates who APPLIED to a specific job,
                       identity withheld until progressive reveal,
                       ranked by that job's requirements.
    talent_pool      — every candidate on the platform, searchable,
                       ranked by their profile-level Evidence Score.

The Talent Pool is identity-visible. That is a deliberate scope
decision, not an oversight of the BDIOF anonymisation this project is
built around, and the reasoning is worth stating plainly because the
two look contradictory at a glance:

  - BDIOF anonymises the EVALUATION of a specific application, because
    that is where the measurable bias in this project's thesis occurs —
    a recruiter comparing applicants against each other and choosing
    between them.
  - Sourcing is not that comparison. A recruiter here is inviting
    someone to apply, and the outcome of that invitation is a normal
    application that then enters the anonymised pipeline like any other
    if the job runs in BDIOF or Hybrid mode. An invitation cannot
    shortlist, reject, or rank anyone.
  - An anonymous talent pool could not be invited FROM in the first
    place, because an invitation has to reach a real person.

What this module therefore does NOT expose, so that sourcing cannot
become a side channel around the dossier's protections:
  - No location. It is the single signal BDIOF exists to suppress, and
    a recruiter filtering a sourcing list by city would reproduce
    exactly the bias the platform measures.
  - No CV file URL and no bio free text, both of which carry
    unscrubbed personal detail (see dossier_service.py's field notes).
  - No per-job application status, and no indication of who applied to
    or was rejected from which job. A recruiter's own dossier already
    tells them about their own jobs; this view must not tell them
    anything about anyone else's.
  - No audit-log or view-limit data — that is admin-only by
    construction (see routers/admin.py).
"""
import uuid as uuid_lib

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Application, CandidateProfile, Job, Notification, User, UserRole,
)
from app.services.competency_engine import EVIDENCE_WEIGHTS, build_competency_profile

# Notification type used to record an invitation. Invitations are stored
# as notifications rather than in a table of their own: the notification
# IS the invitation as far as the candidate is concerned, and it already
# carries everything an invitation needs (recipient, job, timestamp,
# read state). A dedicated table would duplicate all of that to add only
# a status field that nothing currently reads — the invitation's real
# outcome is whether an Application row appears, which is already
# queryable. Revisit if invitations ever need expiry or withdrawal.
INVITATION_TYPE = "job_invitation"

MAX_PAGE_SIZE = 200

# GitHub owns two Evidence Score components (activity now, trajectory
# over time) and they are shown as one pipeline, because that is how a
# candidate experiences them — one linked account. The combined score is
# their weighted mean, so it stays on the same 0.0-1.0 scale as the
# other two pipelines and the contributions still sum to the Evidence
# Score.
_GITHUB_WEIGHT = EVIDENCE_WEIGHTS["g_act"] + EVIDENCE_WEIGHTS["l_traj"]


def list_talent_pool(
    db: Session,
    search: str | None = None,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """
    Every candidate with a profile, strongest Evidence Score first.

    Filtering is server-side so that the client never has to hold the
    whole pool to search it, and so skill matching can use the same
    normalised, badge-tagged skill list the Competency Engine produces
    rather than a raw substring scan of stored CV text. `search` matches
    a candidate's name or any skill in that unified list; `min_score`
    is on the 0.0-1.0 Evidence Score scale.

    Candidates who registered but never built a profile are excluded —
    an inner join, unlike the admin registry's outer join. A recruiter
    sourcing for a role has nothing to act on for a candidate with no
    evidence at all, whereas an admin looking at signup drop-off
    specifically needs to see them.
    """
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    query = (
        db.query(CandidateProfile, User)
        .join(User, User.id == CandidateProfile.user_id)
        .filter(User.role == UserRole.candidate, User.is_active.is_(True))
    )
    if min_score is not None:
        query = query.filter(CandidateProfile.evidence_score >= min_score)

    rows = query.order_by(CandidateProfile.evidence_score.desc()).all()

    # Skill matching needs the unified competency profile, which is
    # computed rather than stored, so name/skill search and the total
    # count are resolved in Python after the score filter has already
    # narrowed the set in SQL.
    candidates = [_build_pool_row(profile, user) for profile, user in rows]
    if search and search.strip():
        needle = search.strip().lower()
        candidates = [c for c in candidates if _matches(c, needle)]

    total_count = len(candidates)
    page = candidates[offset:offset + limit]

    # Application and invitation counts are fetched for the page only,
    # as two grouped queries rather than one pair per candidate.
    _attach_activity_counts(db, page)

    return {
        "candidates": page,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


def _matches(candidate: dict, needle: str) -> bool:
    if needle in candidate["full_name"].lower():
        return True
    return any(needle in skill.lower() for skill in candidate["skills"])


def _build_pool_row(profile: CandidateProfile, user: User) -> dict:
    competency_profile = build_competency_profile(profile)
    return {
        "candidate_id": str(profile.id),
        "user_id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "experience_level": profile.experience_level or "Not specified",
        "education_tier": profile.education_tier or "Undisclosed",
        "evidence_score": profile.evidence_score or 0.0,
        "profile_completeness": profile.profile_completeness or 0.0,
        "evidence_score_breakdown": {
            "p_emb": profile.p_emb_score or 0.0,
            "g_act": profile.g_act_score or 0.0,
            "c_peer": profile.c_peer_score or 0.0,
            "l_traj": profile.l_traj_score or 0.0,
            "evidence_score": profile.evidence_score or 0.0,
        },
        "pipelines": _pipeline_breakdown(profile),
        "skills": list(competency_profile.keys()),
        "top_skills": _top_skills(competency_profile),
        "github_username": profile.github_username,
        "total_applications": 0,
        "invited_job_ids": [],
        "registered_at": user.created_at,
    }


def _pipeline_breakdown(profile: CandidateProfile) -> dict:
    """
    The three evidence pipelines, each with its own score, its share of
    the Evidence Score, and the contribution those two multiply out to —
    so a recruiter can see WHERE a score came from, not just how high it
    is. That is the whole point of an evidence-based dossier: a
    candidate at 0.55 built mostly from GitHub and community evidence is
    a different proposition from one at 0.55 built entirely off a
    polished CV, and the single figure cannot distinguish them.
    """
    p_emb = profile.p_emb_score or 0.0
    g_act = profile.g_act_score or 0.0
    c_peer = profile.c_peer_score or 0.0
    l_traj = profile.l_traj_score or 0.0

    github_score = (
        EVIDENCE_WEIGHTS["g_act"] * g_act + EVIDENCE_WEIGHTS["l_traj"] * l_traj
    ) / _GITHUB_WEIGHT

    return {
        "formal": _pipeline_entry(
            label="Formal (CV)",
            score=p_emb,
            weight=EVIDENCE_WEIGHTS["p_emb"],
            linked=bool(profile.cv_skills),
            detail=_formal_detail(profile),
        ),
        "informal": _pipeline_entry(
            label="Informal (GitHub)",
            score=github_score,
            weight=_GITHUB_WEIGHT,
            linked=bool(profile.github_username),
            detail=_informal_detail(profile),
        ),
        "community": _pipeline_entry(
            label="Community",
            score=c_peer,
            weight=EVIDENCE_WEIGHTS["c_peer"],
            linked=bool(
                profile.certifications or profile.peer_endorsements
                or profile.stackoverflow_data or profile.devto_data
            ),
            detail=_community_detail(profile),
        ),
    }


def _pipeline_entry(label: str, score: float, weight: float, linked: bool, detail: str) -> dict:
    return {
        "label": label,
        "score": round(score, 3),
        "weight": weight,
        "contribution": round(score * weight, 3),
        "linked": linked,
        "detail": detail,
    }


def _formal_detail(profile: CandidateProfile) -> str:
    if not profile.cv_skills:
        return "No CV uploaded"
    parts = [f"{len(profile.cv_skills)} skills"]
    if profile.cv_projects:
        parts.append(f"{len(profile.cv_projects)} projects")
    if profile.ats_score is not None:
        parts.append(f"ATS {round(profile.ats_score)}")
    return " · ".join(parts)


def _informal_detail(profile: CandidateProfile) -> str:
    if not profile.github_username:
        return "No GitHub linked"
    parts = [f"{len(profile.github_repos or [])} repos"]
    if profile.github_languages:
        parts.append(f"{len(profile.github_languages)} languages")
    trend = (profile.learning_trajectory or {}).get("trend")
    if trend:
        parts.append(trend)
    return " · ".join(parts)


def _community_detail(profile: CandidateProfile) -> str:
    parts = []
    if profile.certifications:
        parts.append(f"{len(profile.certifications)} certifications")
    if profile.peer_endorsements:
        parts.append(f"{len(profile.peer_endorsements)} endorsements")
    if profile.stackoverflow_data:
        parts.append("Stack Overflow")
    if profile.devto_data:
        parts.append("Dev.to")
    return " · ".join(parts) if parts else "No community evidence"


def _top_skills(competency_profile: dict, count: int = 6) -> list[dict]:
    """
    The best-corroborated skills first — Verified (three pipelines)
    before Confirmed (two) before Declared (one) — because the tier is
    what makes this list worth more to a recruiter than a self-reported
    skill list. Alphabetical within a tier, so the order is stable
    across polls rather than shifting on dict iteration order.
    """
    tier_rank = {"Verified": 0, "Confirmed": 1, "Declared": 2}
    ordered = sorted(
        competency_profile.items(),
        key=lambda item: (tier_rank.get(item[1]["tier"], 3), item[0].lower()),
    )
    return [
        {"skill": skill, "tier": meta["tier"], "sources": meta["sources"]}
        for skill, meta in ordered[:count]
    ]


def _attach_activity_counts(db: Session, candidates: list[dict]) -> None:
    """
    Fills in total_applications and invited_job_ids for one page.

    total_applications is a bare count with no per-job detail, and no
    status breakdown: how many roles someone is pursuing is useful
    sourcing context, but WHICH roles, and how each went, is another
    recruiter's data (see the module docstring).

    Ids are converted back to uuid.UUID for the queries and to str for
    the lookups. The rows carry strings because that is what the API
    returns, but the columns are native Postgres uuid — binding a string
    against them, or keying a dict on the UUID a query returns while
    looking it up by string, both fail quietly rather than loudly.
    """
    if not candidates:
        return

    profile_ids = [uuid_lib.UUID(c["candidate_id"]) for c in candidates]
    user_ids = [uuid_lib.UUID(c["user_id"]) for c in candidates]

    application_counts = {
        str(candidate_id): count
        for candidate_id, count in db.query(Application.candidate_id, func.count(Application.id))
        .filter(Application.candidate_id.in_(profile_ids))
        .group_by(Application.candidate_id)
        .all()
    }

    # Which jobs each candidate has already been invited to, so the UI
    # can mark the button rather than let a recruiter send the same
    # invitation twice without realising.
    invitations: dict[str, list[str]] = {}
    invitation_rows = (
        db.query(Notification.user_id, Notification.related_id)
        .filter(
            Notification.user_id.in_(user_ids),
            Notification.type == INVITATION_TYPE,
            Notification.related_id.isnot(None),
        )
        .all()
    )
    for user_id, related_id in invitation_rows:
        invitations.setdefault(str(user_id), []).append(str(related_id))

    for candidate in candidates:
        candidate["total_applications"] = application_counts.get(candidate["candidate_id"], 0)
        candidate["invited_job_ids"] = invitations.get(candidate["user_id"], [])


# ---------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------

class InvitationError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def validate_invitation(
    db: Session, recruiter: User, candidate_id, job_id
) -> tuple[CandidateProfile, User, Job]:
    """
    Checks an invitation is legitimate before anything is sent, and
    returns the three rows the caller needs.

    The job-ownership check is the important one: without it a recruiter
    could invite candidates to another company's posting, which would
    let them generate traffic on a job they have no relationship to.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise InvitationError("Job not found.", status_code=404)
    if job.recruiter_id != recruiter.id:
        raise InvitationError("You can only invite candidates to your own jobs.", status_code=403)
    if not job.is_active:
        raise InvitationError("This job is closed — reopen it before inviting candidates.")

    profile = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not profile:
        raise InvitationError("Candidate not found.", status_code=404)

    candidate_user = db.query(User).filter(User.id == profile.user_id).first()
    if not candidate_user or not candidate_user.is_active:
        raise InvitationError("This candidate's account is not active.")

    existing_application = (
        db.query(Application)
        .filter(Application.candidate_id == profile.id, Application.job_id == job.id)
        .first()
    )
    if existing_application:
        # Distinguished from an "already invited" message on purpose: a
        # recruiter who sees "already applied" knows to go to the
        # dossier, where the application is actually actionable.
        raise InvitationError("This candidate has already applied to this job.")

    if _already_invited(db, candidate_user.id, job.id):
        raise InvitationError("You have already invited this candidate to this job.")

    return profile, candidate_user, job


def _already_invited(db: Session, user_id, job_id) -> bool:
    return (
        db.query(Notification)
        .filter(
            Notification.user_id == user_id,
            Notification.type == INVITATION_TYPE,
            Notification.related_id == job_id,
        )
        .first()
        is not None
    )


def build_invitation_message(job: Job, company_name: str | None, note: str | None) -> str:
    """
    The invitation text. Names the company where one exists, since a
    candidate deciding whether to spend time applying is entitled to
    know who is asking — the anonymisation in this platform protects the
    candidate from the recruiter, not the reverse.
    """
    who = f"{company_name} " if company_name else ""
    message = f"{who}invited you to apply for '{job.title}'."
    if note and note.strip():
        message += f" Note from the recruiter: {note.strip()}"
    return message
