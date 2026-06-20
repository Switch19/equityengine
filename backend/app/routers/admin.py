from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User, UserRole
from app.models.job import Job
from app.models.profile import CandidateProfile
from passlib.context import CryptContext

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.post("/setup")
def create_admin(email: str, password: str, db: Session = Depends(get_db)):
    """Create the admin account — run once only."""
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Admin already exists")
    admin = User(
        email=email,
        full_name="Platform Administrator",
        hashed_password=pwd_context.hash(password),
        role=UserRole.admin
    )
    db.add(admin)
    db.commit()
    return {"message": "Admin created successfully"}

@router.get("/audit/summary")
def get_audit_summary(db: Session = Depends(get_db)):
    total_views = db.query(AuditLog).filter(
        AuditLog.action == "viewed_anonymized"
    ).count()

    total_reveals = db.query(AuditLog).filter(
        AuditLog.action == "identity_revealed"
    ).count()

    talent_pool_views = db.query(AuditLog).filter(
        AuditLog.action == "talent_pool_view"
    ).count()

    conversion_rate = round((total_reveals / total_views * 100), 2) if total_views > 0 else 0
    visibility_gap = round(100 - conversion_rate, 2)

    jobs = db.query(Job).all()
    job_breakdown = []
    for job in jobs:
        views = db.query(AuditLog).filter(
            AuditLog.job_id == job.id,
            AuditLog.action == "viewed_anonymized"
        ).count()
        reveals = db.query(AuditLog).filter(
            AuditLog.job_id == job.id,
            AuditLog.action == "identity_revealed"
        ).count()
        job_breakdown.append({
            "job_id": job.id,
            "job_title": job.title,
            "anonymized_views": views,
            "identity_reveals": reveals,
            "conversion_rate": round((reveals / views * 100), 2) if views > 0 else 0
        })

    total_candidates = db.query(CandidateProfile).count()
    total_jobs = db.query(Job).filter(Job.is_active == True).count()
    total_users = db.query(User).count()

    return {
        "platform_stats": {
            "total_users": total_users,
            "total_candidates": total_candidates,
            "total_active_jobs": total_jobs,
            "total_talent_pool_views": talent_pool_views,
        },
        "summary": {
            "total_anonymized_views": total_views,
            "total_identity_reveals": total_reveals,
            "overall_conversion_rate": conversion_rate,
            "visibility_gap": visibility_gap,
        },
        "job_breakdown": job_breakdown,
        "insight": get_insight(visibility_gap)
    }

def get_insight(gap: float) -> str:
    if gap >= 80:
        return "High visibility gap detected. Most candidates are being evaluated purely on skills — the system is working effectively."
    elif gap >= 50:
        return "Moderate visibility gap. Recruiters are screening candidates fairly before revealing identity."
    else:
        return "Low visibility gap. Most candidates are being shortlisted quickly — consider reviewing recruiter behavior patterns."