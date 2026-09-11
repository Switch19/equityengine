"""
Candidate-facing endpoints: CV upload (Pipeline 1) and profile
viewing/editing.
"""
import os
import uuid as uuid_lib
from datetime import datetime


from fastapi.responses import StreamingResponse
import io
from app.services.cv_generator import build_optimized_cv_pdf

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import User, CandidateProfile, UserRole, Job, Application, ApplicationStatus, ScreeningMode
from app.schemas import (
    CVUploadResponse, CandidateProfileOut, CandidateProfileUpdate,
    GitHubLinkRequest, GitHubAnalysisResponse,
    CertificationCreate, StackOverflowLinkRequest, DevToLinkRequest,
    EndorsementCreate, CommunityProfileResponse,
    FullCompetencyProfileResponse, EvidenceScoreBreakdown,
    JobOut, ApplicationCreate, ApplicationOut,
)
from app.deps import require_role
from app.services.resume_parser import parse_cv
from app.services.ats_compliance import compute_ats_score
from app.services.competency_engine import (
    update_profile_completeness, recompute_competency_profile, build_competency_profile,
    compute_job_specific_evidence_score,
)
from app.services.github_service import analyze_github_profile, GitHubServiceError
from app.services.notification_service import create_notification
from app.services.community_service import (
    fetch_stackoverflow_stats, fetch_devto_stats, classify_certification,
    add_endorsement, summarize_endorsements_for_owner, compute_c_peer_score,
    CommunityServiceError,
)

router = APIRouter(prefix="/candidates", tags=["candidates"])

UPLOAD_DIR = "uploads/cvs"
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


def _get_own_profile(current_user: User, db: Session) -> CandidateProfile:
    profile = (
        db.query(CandidateProfile)
        .filter(CandidateProfile.user_id == current_user.id)
        .first()
    )
    if not profile:
        # Should not normally happen — a profile row is created at
        # registration — but handled defensively in case of older
        # accounts or manual DB edits.
        profile = CandidateProfile(user_id=current_user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.post("/cv/upload", response_model=CVUploadResponse)
async def upload_cv(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    ext = file.filename.lower().rsplit(".", 1)[-1] if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB.")

    try:
        parsed = parse_cv(file_bytes, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Save the original file to disk so it can be downloaded/reviewed later.
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_filename = f"{current_user.id}_{int(datetime.utcnow().timestamp())}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    ats_result = compute_ats_score(text=parsed["raw_text"], skills_found=parsed["skills"])

    profile = _get_own_profile(current_user, db)
    profile.cv_file_url = f"/uploads/cvs/{safe_filename}"
    profile.cv_skills = parsed["skills"]
    profile.cv_projects = parsed["projects"]
    profile.regional_terms = parsed["regional_terms"]
    profile.experience_level = parsed["experience_level"]
    profile.education_tier = parsed["education_tier"]
    profile.ats_score = ats_result["score"]
    recompute_competency_profile(profile)

    db.commit()
    db.refresh(profile)

    return CVUploadResponse(
        cv_skills=parsed["skills"],
        regional_terms=parsed["regional_terms"],
        experience_level=parsed["experience_level"],
        education_tier=parsed["education_tier"],
        projects=parsed["projects"],
        ats_score=ats_result["score"],
        ats_breakdown=ats_result["breakdown"],
        ats_suggestions=ats_result["suggestions"],
        profile_completeness=profile.profile_completeness,
    )


@router.post("/github/link", response_model=GitHubAnalysisResponse)
async def link_github(
    payload: GitHubLinkRequest,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    try:
        result = await analyze_github_profile(payload.github_username)
    except GitHubServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    profile = _get_own_profile(current_user, db)
    profile.github_username = result["github_username"]
    profile.github_repos = result["repos"]
    profile.github_languages = result["languages"]
    profile.learning_trajectory = result["learning_trajectory"]
    profile.g_act_score = result["g_act_score"]
    profile.github_activity = {
        **result["activity"],
        "inferred_skills": result["inferred_skills"],
    }
    recompute_competency_profile(profile)

    db.commit()
    db.refresh(profile)

    return GitHubAnalysisResponse(
        github_username=result["github_username"],
        profile_summary=result["profile_summary"],
        repos=result["repos"],
        languages=result["languages"],
        activity=result["activity"],
        learning_trajectory=result["learning_trajectory"],
        inferred_skills=result["inferred_skills"],
        g_act_score=result["g_act_score"],
        profile_completeness=profile.profile_completeness,
    )


def _recompute_c_peer(profile: CandidateProfile) -> None:
    profile.c_peer_score = compute_c_peer_score(
        profile.certifications, profile.stackoverflow_data, profile.peer_endorsements
    )


@router.post("/certifications", response_model=CommunityProfileResponse)
def add_certification(
    payload: CertificationCreate,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = _get_own_profile(current_user, db)

    new_cert = classify_certification(payload.name, payload.issuer, payload.date_earned)
    profile.certifications = (profile.certifications or []) + [new_cert]

    _recompute_c_peer(profile)
    recompute_competency_profile(profile)
    db.commit()
    db.refresh(profile)

    return CommunityProfileResponse(
        certifications=profile.certifications,
        stackoverflow_data=profile.stackoverflow_data,
        endorsement_summary=summarize_endorsements_for_owner(profile.peer_endorsements),
        c_peer_score=profile.c_peer_score,
        profile_completeness=profile.profile_completeness,
    )


@router.post("/community/stackoverflow/link", response_model=CommunityProfileResponse)
async def link_stackoverflow(
    payload: StackOverflowLinkRequest,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    try:
        so_data = await fetch_stackoverflow_stats(payload.stackoverflow_user_id)
    except CommunityServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    profile = _get_own_profile(current_user, db)
    profile.stackoverflow_data = so_data

    _recompute_c_peer(profile)
    recompute_competency_profile(profile)
    db.commit()
    db.refresh(profile)

    return CommunityProfileResponse(
        certifications=profile.certifications or [],
        stackoverflow_data=profile.stackoverflow_data,
        endorsement_summary=summarize_endorsements_for_owner(profile.peer_endorsements),
        c_peer_score=profile.c_peer_score,
        profile_completeness=profile.profile_completeness,
    )


@router.post("/community/devto/link")
async def link_devto(
    payload: DevToLinkRequest,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    """
    Dev.to article activity is stored but does not currently feed
    c_peer_score directly — it's informational evidence of community
    writing/thought-leadership shown on the candidate's profile. If
    you want it to contribute to the score, it belongs alongside
    certifications and Stack Overflow in compute_c_peer_score(); left
    out here deliberately so the formula's three inputs stay traceable
    to what Chapter 2 actually reviewed (certifications, Stack
    Overflow, peer endorsement) rather than growing informally.
    """
    try:
        devto_data = await fetch_devto_stats(payload.devto_username)
    except CommunityServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    profile = _get_own_profile(current_user, db)
    profile.devto_data = devto_data
    recompute_competency_profile(profile)
    db.commit()
    db.refresh(profile)

    return {"devto_data": devto_data, "profile_completeness": profile.profile_completeness}


@router.post("/{candidate_id}/endorse", response_model=dict)
def endorse_candidate(
    candidate_id: uuid_lib.UUID,
    payload: EndorsementCreate,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    if str(candidate_id) != str(payload.candidate_id):
        raise HTTPException(status_code=400, detail="candidate_id in URL and body must match")

    endorser_profile = _get_own_profile(current_user, db)
    if str(endorser_profile.id) == str(candidate_id):
        raise HTTPException(status_code=400, detail="You cannot endorse your own profile")

    target = db.query(CandidateProfile).filter(CandidateProfile.id == candidate_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        target.peer_endorsements = add_endorsement(
            target.peer_endorsements, str(endorser_profile.id), payload.skill
        )
    except CommunityServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    _recompute_c_peer(target)
    recompute_competency_profile(target)
    db.commit()

    return {"detail": f"Endorsed for {payload.skill}"}


@router.get("/me/endorsements", response_model=CommunityProfileResponse)
def get_my_endorsements(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = _get_own_profile(current_user, db)
    return CommunityProfileResponse(
        certifications=profile.certifications or [],
        stackoverflow_data=profile.stackoverflow_data,
        endorsement_summary=summarize_endorsements_for_owner(profile.peer_endorsements),
        c_peer_score=profile.c_peer_score,
        profile_completeness=profile.profile_completeness,
    )


@router.get("/me/competency-profile", response_model=FullCompetencyProfileResponse)
def get_my_competency_profile(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = _get_own_profile(current_user, db)
    skills = build_competency_profile(profile)

    return FullCompetencyProfileResponse(
        skills=skills,
        evidence_score_breakdown=EvidenceScoreBreakdown(
            p_emb=profile.p_emb_score or 0.0,
            g_act=profile.g_act_score or 0.0,
            c_peer=profile.c_peer_score or 0.0,
            l_traj=profile.l_traj_score or 0.0,
            evidence_score=profile.evidence_score or 0.0,
        ),
        profile_completeness=profile.profile_completeness,
    )


@router.get("/me/profile", response_model=CandidateProfileOut)
def get_my_profile(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    return _get_own_profile(current_user, db)

@router.get("/me/cv/download")
def download_optimized_cv(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    """
    Generates a CV PDF from the candidate's unified Competency Profile
    (CV + GitHub + community evidence combined) — not just their
    originally uploaded CV text. This means even a candidate who never
    uploaded a formal CV, and only linked GitHub and added a
    certification, can still download a presentable, exportable CV.
    """
    profile = _get_own_profile(current_user, db)
    pdf_bytes = build_optimized_cv_pdf(profile, current_user)

    safe_name = current_user.full_name.replace(" ", "_")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={safe_name}_CV.pdf"},
    )


@router.patch("/me/profile", response_model=CandidateProfileOut)
def update_my_profile(
    payload: CandidateProfileUpdate,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = _get_own_profile(current_user, db)

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    recompute_competency_profile(profile)
    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------
# Job browsing and applications
# ---------------------------------------------------------------------

def _serialize_application(application: Application) -> ApplicationOut:
    """
    ApplicationOut plus the job's title, which is not a column on
    applications. Resolved here rather than added as a model property so
    the extra query stays visible at the call site — callers that already
    hold the Job, or that eager-load it, pay nothing.
    """
    out = ApplicationOut.model_validate(application)
    out.job_title = application.job.title if application.job else None
    return out


@router.get("/jobs", response_model=list[JobOut])
def browse_jobs(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    return db.query(Job).filter(Job.is_active == True).order_by(Job.created_at.desc()).all()  # noqa: E712


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job_detail(
    job_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()  # noqa: E712
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or no longer active")
    return job


@router.post("/jobs/{job_id}/apply", response_model=ApplicationOut, status_code=201)
async def apply_to_job(
    job_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id, Job.is_active == True).first()  # noqa: E712
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or no longer active")

    profile = _get_own_profile(current_user, db)

    existing = (
        db.query(Application)
        .filter(Application.candidate_id == profile.id, Application.job_id == job_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already applied to this job")

    # Snapshot the Evidence Score at the moment of application — this
    # is what applications.evidence_score_at_application exists for
    # (Chapter 3, Table 3.1): the candidate's live score can keep
    # changing after this point (more GitHub activity, new
    # certifications), but the score that was actually used to
    # evaluate THIS application is preserved for audit purposes.
    score_breakdown = compute_job_specific_evidence_score(profile, job)

    application = Application(
        candidate_id=profile.id,
        job_id=job_id,
        status=ApplicationStatus.applied,
        screening_mode_at_application=job.screening_mode,
        evidence_score_at_application=score_breakdown["evidence_score"],
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    # Notify the recruiter — deliberately WITHOUT the candidate's name
    # for anonymised jobs. A notification is exactly the kind of
    # incidental channel that could quietly leak identity if built
    # carelessly (see chat_service.py's docstring for the same
    # principle applied to chat) — the message text is the allow-list
    # here, same discipline as dossier_service.py's field-level one.
    if job.screening_mode == ScreeningMode.standard:
        notify_text = f"{current_user.full_name} applied to '{job.title}'."
    else:
        notify_text = f"A new application was received for '{job.title}' (anonymised — view the Competency Dossier)."

    await create_notification(
        db, user_id=job.recruiter_id, notification_type="new_application",
        message=notify_text, related_id=application.id,
    )

    return _serialize_application(application)


@router.get("/me/applications", response_model=list[ApplicationOut])
def get_my_applications(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = _get_own_profile(current_user, db)
    applications = (
        db.query(Application)
        # Eager-loaded because every row's job title is serialized below;
        # lazy loading would be one query per application.
        .options(joinedload(Application.job))
        .filter(Application.candidate_id == profile.id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    return [_serialize_application(application) for application in applications]
