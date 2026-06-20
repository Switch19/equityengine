from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.audit import AuditLog
from app.models.profile import CandidateProfile
from app.services.skill_matcher import compute_skill_score, anonymize_candidate

router = APIRouter()

@router.get("/talent-pool")
def browse_talent_pool(skills: str, recruiter_id: int, db: Session = Depends(get_db)):
    """
    BDIOF Vector 2 — Talent Pool
    Recruiter searches by skills without posting a job.
    All candidates still fully anonymized.
    """
    profiles = db.query(CandidateProfile).all()
    results = []

    for profile in profiles:
        skill_score = compute_skill_score(
            profile.skills or "",
            skills
        )

        if skill_score > 0:
            # Log talent pool interaction
            log = AuditLog(
                recruiter_id=recruiter_id,
                candidate_id=profile.user_id,
                job_id=1,
                action="talent_pool_view",
                was_anonymized=True
            )
            db.add(log)
            db.commit()

            anonymized = anonymize_candidate({
                "id": profile.user_id,
                "skills": profile.skills,
                "skill_score": skill_score,
                "visibility_score": profile.visibility_score
            })
            results.append(anonymized)

    results.sort(key=lambda x: x["skill_score"], reverse=True)
    return {
        "searched_skills": skills,
        "candidates": results
    }