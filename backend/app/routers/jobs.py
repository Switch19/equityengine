from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.job import Job
from app.models.profile import CandidateProfile
from app.models.audit import AuditLog
from app.schemas.job import JobCreate, JobResponse
from app.services.skill_matcher import compute_skill_score, anonymize_candidate
from typing import List

router = APIRouter()

@router.post("/", response_model=JobResponse)
def create_job(job: JobCreate, recruiter_id: int, db: Session = Depends(get_db)):
    new_job = Job(
        recruiter_id=recruiter_id,
        title=job.title,
        description=job.description,
        required_skills=job.required_skills,
        location=job.location
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return new_job

@router.get("/")
def get_jobs(db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.is_active == True).all()
    return jobs

@router.get("/{job_id}/candidates")
def get_anonymized_candidates(job_id: int, recruiter_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get already revealed candidates for this recruiter + job
    revealed_logs = db.query(AuditLog).filter(
        AuditLog.job_id == job_id,
        AuditLog.recruiter_id == recruiter_id,
        AuditLog.action == "identity_revealed"
    ).all()
    revealed_candidate_ids = set(log.candidate_id for log in revealed_logs)

    profiles = db.query(CandidateProfile).all()
    ranked_candidates = []

    for profile in profiles:
        skill_score = compute_skill_score(
            profile.skills or "",
            job.required_skills
        )

        profile.skill_score = skill_score
        db.commit()

        # Log view only if not already revealed
        if profile.user_id not in revealed_candidate_ids:
            log = AuditLog(
                recruiter_id=recruiter_id,
                candidate_id=profile.user_id,
                job_id=job_id,
                action="viewed_anonymized",
                was_anonymized=True
            )
            db.add(log)
            db.commit()

        # If already revealed, return full identity
        if profile.user_id in revealed_candidate_ids:
            from app.models.user import User
            user = db.query(User).filter(User.id == profile.user_id).first()
            ranked_candidates.append({
                "anonymous_id": f"CANDIDATE-{profile.user_id}",
                "regional_identifier": "Revealed",
                "skills": profile.skills,
                "skill_score": skill_score,
                "visibility_score": profile.visibility_score,
                "is_anonymized": False,
                "revealed": {
                    "full_name": user.full_name if user else "",
                    "email": user.email if user else "",
                    "id": profile.user_id,
                    "skills": profile.skills,
                    "skill_score": skill_score,
                    "visibility_score": profile.visibility_score
                }
            })
        else:
            anonymized = anonymize_candidate({
                "id": profile.user_id,
                "skills": profile.skills,
                "skill_score": skill_score,
                "visibility_score": profile.visibility_score
            })
            ranked_candidates.append(anonymized)

    ranked_candidates.sort(key=lambda x: x["skill_score"], reverse=True)
    return {"job": job.title, "candidates": ranked_candidates}

@router.post("/{job_id}/reveal/{candidate_id}")
def reveal_candidate_identity(
    job_id: int,
    candidate_id: int,
    recruiter_id: int,
    db: Session = Depends(get_db)
):
    """
    Progressive identity reveal — only after recruiter
    initiates interview request.
    """
    from app.models.user import User

    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == candidate_id
    ).first()

    user = db.query(User).filter(User.id == candidate_id).first()

    if not profile or not user:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Log the reveal event for Bias Audit Engine
    log = AuditLog(
        recruiter_id=recruiter_id,
        candidate_id=candidate_id,
        job_id=job_id,
        action="identity_revealed",
        was_anonymized=False
    )
    db.add(log)
    db.commit()

    return {
        "message": "Identity revealed after interview request",
        "candidate": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "skills": profile.skills,
            "skill_score": profile.skill_score,
            "visibility_score": profile.visibility_score
        }
    }