"""
Recruiter-facing endpoints: company profile, job posting, the
Competency Dossier (ranked, mode-appropriate candidate view),
shortlisting workflow, progressive identity reveal, and the Talent Pool
(identity-visible sourcing across all candidates — see
services/talent_pool_service.py for how that differs from the dossier
and why).
"""
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, Company, Job, Application, CandidateProfile,
    ScreeningMode, ApplicationStatus,
)
from app.schemas import (
    CompanyCreate, CompanyOut, JobCreate, JobUpdate, JobOut,
    ApplicationStatusUpdate, DossierCandidateOut, ViewLimitStatus,
    TalentPoolOut, TalentPoolInviteRequest, TalentPoolInviteResponse,
)
from app.deps import require_role
from app.services.dossier_service import (
    build_anonymized_candidate_view, build_revealed_candidate_view,
    rank_applications_by_evidence_score,
)
from app.services.audit_service import log_action, check_view_limit, has_been_revealed
from app.services.feedback_service import generate_rejection_feedback
from app.services.notification_service import create_notification
from app.services.email_service import (
    send_application_status_email, send_profile_revealed_email, send_job_invitation_email,
)
from app.services.talent_pool_service import (
    INVITATION_TYPE, InvitationError, build_invitation_message, list_talent_pool,
    validate_invitation,
)

router = APIRouter(prefix="/recruiters", tags=["recruiters"])


# ---------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------

@router.post("/company", response_model=CompanyOut, status_code=201)
def create_company(
    payload: CompanyCreate,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    existing = db.query(Company).filter(Company.recruiter_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already have a company profile")

    company = Company(recruiter_id=current_user.id, **payload.model_dump())
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@router.get("/company", response_model=CompanyOut)
def get_my_company(
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.recruiter_id == current_user.id).first()
    if not company:
        raise HTTPException(status_code=404, detail="No company profile yet — create one first")
    return company


# ---------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------

@router.post("/jobs", response_model=JobOut, status_code=201)
def post_job(
    payload: JobCreate,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.recruiter_id == current_user.id).first()
    if not company:
        raise HTTPException(
            status_code=400,
            detail="Create a company profile before posting a job (POST /recruiters/company)",
        )

    job = Job(recruiter_id=current_user.id, company_id=company.id, **payload.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get("/jobs", response_model=list[JobOut])
def list_my_jobs(
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    return db.query(Job).filter(Job.recruiter_id == current_user.id).order_by(Job.created_at.desc()).all()


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    job = _get_own_job(job_id, current_user, db)
    return job


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: uuid_lib.UUID,
    payload: JobUpdate,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    job = _get_own_job(job_id, current_user, db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


def _get_own_job(job_id, current_user: User, db: Session) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.recruiter_id != current_user.id:
        raise HTTPException(status_code=403, detail="This job belongs to a different recruiter")
    return job


# ---------------------------------------------------------------------
# Reveal state check moved to app.services.audit_service.has_been_revealed
# so chat (Phase 8) can share the exact same logic.
# ---------------------------------------------------------------------

def _build_view_for_application(db: Session, job: Job, application: Application, current_user: User) -> dict:
    profile = application.candidate
    user = profile.user

    if job.screening_mode == ScreeningMode.standard:
        return build_revealed_candidate_view(profile, user, job, application)

    revealed = has_been_revealed(db, current_user.id, profile.id, job.id)
    if revealed:
        return build_revealed_candidate_view(profile, user, job, application)
    return build_anonymized_candidate_view(profile, job, application)


# ---------------------------------------------------------------------
# Competency Dossier
# ---------------------------------------------------------------------

@router.get("/jobs/{job_id}/candidates", response_model=list[DossierCandidateOut])
def get_dossier(
    job_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    """
    Returns the ranked candidate list for a job — this is the
    Competency Dossier. List browsing does NOT itself log a "viewed"
    audit entry or count against the rate limit; only opening an
    individual candidate's detail view does (see the endpoint below).
    Scanning a ranked list is not the behaviour the rate limit exists
    to discourage — repeatedly re-opening the SAME candidate's full
    detail without deciding is.
    """
    job = _get_own_job(job_id, current_user, db)
    applications = db.query(Application).filter(Application.job_id == job_id).all()

    views = [_build_view_for_application(db, job, app, current_user) for app in applications]
    return rank_applications_by_evidence_score(views)


@router.get("/jobs/{job_id}/candidates/{application_id}", response_model=DossierCandidateOut)
def view_candidate_detail(
    job_id: uuid_lib.UUID,
    application_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    job = _get_own_job(job_id, current_user, db)
    application = _get_application_for_job(application_id, job, db)
    profile = application.candidate

    limit_status = check_view_limit(db, current_user.id, profile.id, application.status)
    if limit_status["limited"]:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You have viewed this candidate {limit_status['views_so_far']} times. "
                "Please shortlist, request an interview, or reject before viewing again."
            ),
        )

    log_action(
        db, recruiter_id=current_user.id, candidate_id=profile.id, job_id=job.id,
        action="viewed", was_anonymized=(job.screening_mode != ScreeningMode.standard),
        screening_mode=job.screening_mode,
    )

    return _build_view_for_application(db, job, application, current_user)


@router.get("/jobs/{job_id}/candidates/{application_id}/view-limit", response_model=ViewLimitStatus)
def get_view_limit_status(
    job_id: uuid_lib.UUID,
    application_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    job = _get_own_job(job_id, current_user, db)
    application = _get_application_for_job(application_id, job, db)
    return check_view_limit(db, current_user.id, application.candidate.id, application.status)


def _get_application_for_job(application_id, job: Job, db: Session) -> Application:
    application = (
        db.query(Application)
        .filter(Application.id == application_id, Application.job_id == job.id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found for this job")
    return application


# ---------------------------------------------------------------------
# Shortlisting workflow + progressive reveal
# ---------------------------------------------------------------------

# Status transitions that trigger identity reveal, per screening mode.
# BDIOF: reveal only once a recruiter formally requests an interview
# (Chapter 3, Figure 3.3). Hybrid: reveal one stage earlier, at
# shortlisting, per the original design spec ("Hybrid: Anonymised
# first round, identity revealed for shortlist").
_BDIOF_REVEAL_TRIGGERS = {ApplicationStatus.interview, ApplicationStatus.offered}
_HYBRID_REVEAL_TRIGGERS = {ApplicationStatus.shortlisted, ApplicationStatus.interview, ApplicationStatus.offered}


@router.patch("/jobs/{job_id}/candidates/{application_id}/status", response_model=DossierCandidateOut)
async def update_application_status(
    job_id: uuid_lib.UUID,
    application_id: uuid_lib.UUID,
    payload: ApplicationStatusUpdate,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    job = _get_own_job(job_id, current_user, db)
    application = _get_application_for_job(application_id, job, db)
    profile = application.candidate

    already_revealed_before = has_been_revealed(db, current_user.id, profile.id, job.id)

    application.status = payload.status
    if job.screening_mode == ScreeningMode.standard:
        application.was_anonymized_when_selected = False
    elif not already_revealed_before:
        application.was_anonymized_when_selected = True

    # Automated post-rejection feedback. Generated here, after the
    # recruiter's decision is already made, so it can only ever explain
    # the outcome — it is never an input to it (see
    # services/feedback_service.py).
    if payload.status == ApplicationStatus.rejected:
        feedback = generate_rejection_feedback(db, application, job)
        application.primary_reason = feedback["primary_reason"]
        application.growth_tip = feedback["growth_tip"]
    else:
        # A status moving off `rejected` — a recruiter correcting a
        # misclick, or reconsidering — must not leave the old diagnosis
        # behind. The candidate's dashboard shows this card whenever the
        # fields are populated, so stale text would keep explaining a
        # rejection that no longer exists.
        application.primary_reason = None
        application.growth_tip = None

    db.commit()

    log_action(
        db, recruiter_id=current_user.id, candidate_id=profile.id, job_id=job.id,
        action=payload.status.value, was_anonymized=(job.screening_mode != ScreeningMode.standard),
        screening_mode=job.screening_mode, time_spent_seconds=payload.time_spent_seconds,
    )

    should_reveal_now = (
        job.screening_mode == ScreeningMode.bdiof and payload.status in _BDIOF_REVEAL_TRIGGERS
    ) or (
        job.screening_mode == ScreeningMode.hybrid and payload.status in _HYBRID_REVEAL_TRIGGERS
    )
    if should_reveal_now and not already_revealed_before:
        log_action(
            db, recruiter_id=current_user.id, candidate_id=profile.id, job_id=job.id,
            action="revealed", was_anonymized=True, screening_mode=job.screening_mode,
        )

    # Notify the candidate — this is step 6/9 of Chapter 3's sequence
    # diagram ("Notify: application shortlisted" / "interview requested").
    # In-app notification uses profile.user_id directly (no need to
    # load the full User); the email additionally needs profile.user
    # loaded, since it needs the actual email address and name.
    await create_notification(
        db, user_id=profile.user_id, notification_type="application_status",
        message=f"Your application for '{job.title}' is now: {payload.status.value}",
        related_id=application.id,
    )
    await send_application_status_email(
        profile.user.email, profile.user.full_name, job.title, payload.status.value
    )

    db.refresh(application)
    return _build_view_for_application(db, job, application, current_user)


@router.post("/jobs/{job_id}/candidates/{application_id}/reveal", response_model=DossierCandidateOut)
async def reveal_candidate(
    job_id: uuid_lib.UUID,
    application_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    """
    Explicit reveal, independent of a status change — lets a recruiter
    reveal identity without necessarily moving straight to "interview"
    status. Logged exactly like an automatic reveal, so it shows up
    identically in the Bias Audit Engine's data either way.
    """
    job = _get_own_job(job_id, current_user, db)
    application = _get_application_for_job(application_id, job, db)
    profile = application.candidate

    if job.screening_mode == ScreeningMode.standard:
        raise HTTPException(status_code=400, detail="This job is not anonymised — identity is already visible")

    if not has_been_revealed(db, current_user.id, profile.id, job.id):
        log_action(
            db, recruiter_id=current_user.id, candidate_id=profile.id, job_id=job.id,
            action="revealed", was_anonymized=True, screening_mode=job.screening_mode,
        )
        await create_notification(
            db, user_id=profile.user_id, notification_type="profile_revealed",
            message=f"A recruiter has viewed your full profile for '{job.title}'.",
            related_id=application.id,
        )
        await send_profile_revealed_email(profile.user.email, profile.user.full_name, job.title)

    return _build_view_for_application(db, job, application, current_user)


# ---------------------------------------------------------------------
# Talent Pool
# ---------------------------------------------------------------------

@router.get("/talent-pool", response_model=TalentPoolOut)
def get_talent_pool(
    search: str | None = Query(None, description="Match a candidate name or any verified skill"),
    min_score: float | None = Query(
        None, ge=0.0, le=1.0, description="Minimum Evidence Score, on the 0.0-1.0 scale"
    ),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    """
    Every registered candidate with a built profile, strongest Evidence
    Score first, for proactive sourcing.

    Unlike the Competency Dossier, this is identity-visible and is NOT
    scoped to one job — so it deliberately withholds location, bio, CV
    file, and any per-job application state. The reasoning for that
    split, and why it does not undercut BDIOF, is in
    services/talent_pool_service.py's module docstring; read it before
    widening the field set here.

    Browsing this list logs no audit entry and does not count against
    the per-candidate view limit. Both of those exist to constrain
    repeated re-examination of a specific APPLICANT before deciding on
    them; nobody is being decided on here, and there is no application
    to decide.
    """
    return list_talent_pool(db, search=search, min_score=min_score, limit=limit, offset=offset)


@router.post(
    "/talent-pool/{candidate_id}/invite",
    response_model=TalentPoolInviteResponse,
    status_code=201,
)
async def invite_candidate_to_job(
    candidate_id: uuid_lib.UUID,
    payload: TalentPoolInviteRequest,
    current_user: User = Depends(require_role(UserRole.recruiter)),
    db: Session = Depends(get_db),
):
    """
    Invites a candidate to apply for one of this recruiter's active jobs.

    An invitation is an in-app notification plus an email; it is NOT an
    application. The candidate still has to apply, and their application
    then enters the same pipeline as any other — anonymised first if the
    job runs in BDIOF or Hybrid mode. That boundary is what keeps
    sourcing from becoming a way around anonymised screening: a
    recruiter can ask someone to apply, but cannot place, rank, or
    advance them from here.

    Nothing is logged to the audit trail, because an invitation is not
    an action taken ON an application — there is no application yet, and
    a log row referencing a job the candidate has not applied to would
    misrepresent the Bias Audit Engine's shortlist-rate denominators.
    """
    try:
        profile, candidate_user, job = validate_invitation(
            db, current_user, candidate_id, payload.job_id
        )
    except InvitationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    company = db.query(Company).filter(Company.recruiter_id == current_user.id).first()
    company_name = company.name if company else None

    await create_notification(
        db, user_id=candidate_user.id, notification_type=INVITATION_TYPE,
        message=build_invitation_message(job, company_name, payload.note),
        # related_id is the JOB, not an application — there is no
        # application yet, and it is what the candidate needs to open.
        # talent_pool_service reads this back to mark already-invited
        # candidates, so it is load-bearing, not just informational.
        related_id=job.id,
    )
    await send_job_invitation_email(
        candidate_user.email, candidate_user.full_name, job.title, company_name, payload.note
    )

    return TalentPoolInviteResponse(
        detail=f"Invitation sent to {candidate_user.full_name}.",
        candidate_id=str(profile.id),
        job_id=str(job.id),
        job_title=job.title,
    )
