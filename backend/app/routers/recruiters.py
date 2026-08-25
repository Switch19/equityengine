"""
Recruiter-facing endpoints: company profile, job posting, the
Competency Dossier (ranked, mode-appropriate candidate view),
shortlisting workflow, and progressive identity reveal.
"""
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, UserRole, Company, Job, Application, CandidateProfile,
    ScreeningMode, ApplicationStatus,
)
from app.schemas import (
    CompanyCreate, CompanyOut, JobCreate, JobUpdate, JobOut,
    ApplicationStatusUpdate, DossierCandidateOut, ViewLimitStatus,
)
from app.deps import require_role
from app.services.dossier_service import (
    build_anonymized_candidate_view, build_revealed_candidate_view,
    rank_applications_by_evidence_score,
)
from app.services.audit_service import log_action, check_view_limit, has_been_revealed
from app.services.notification_service import create_notification
from app.services.email_service import send_application_status_email, send_profile_revealed_email

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
