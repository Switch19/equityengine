from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.profile import CandidateProfile
from app.services.resume_parser import extract_resume_text
from app.services.nlp_service import analyze_resume
import shutil
import os

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.get("/")
def get_candidates(db: Session = Depends(get_db)):
    return {"message": "Candidates endpoint ready"}

@router.post("/upload-resume/{user_id}")
async def upload_resume(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Validate file type
    if not file.filename.endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    # Save file
    file_path = f"{UPLOAD_DIR}/{user_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract text
    try:
        text = extract_resume_text(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Run BDIOF Vector 1 NLP analysis
    analysis = analyze_resume(text)

    # Save or update profile
    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).first()

    if not profile:
        profile = CandidateProfile(
            user_id=user_id,
            raw_resume_path=file_path,
            skills=", ".join(analysis["skills_detected"]),
            visibility_score=analysis["visibility_score"]
        )
        db.add(profile)
    else:
        profile.raw_resume_path = file_path
        profile.skills = ", ".join(analysis["skills_detected"])
        profile.visibility_score = analysis["visibility_score"]

    db.commit()
    db.refresh(profile)

    return {
        "message": "Resume uploaded and analyzed successfully",
        "analysis": analysis
    }

@router.get("/intelligence/{user_id}")
def get_candidate_intelligence(user_id: int, db: Session = Depends(get_db)):
    """
    BDIOF Vector 3B — Candidate Intelligence Feed
    Returns personalized insights based on real recruiter
    interaction data to close the feedback loop.
    """
    from app.models.audit import AuditLog
    from app.models.job import Job

    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).first()

    if not profile:
        return {
            "has_profile": False,
            "message": "Upload your CV to start receiving intelligence insights."
        }

    # How many times viewed anonymously
    profile_views = db.query(AuditLog).filter(
        AuditLog.candidate_id == user_id,
        AuditLog.action == "viewed_anonymized"
    ).count()

    # How many interview requests
    interview_requests = db.query(AuditLog).filter(
        AuditLog.candidate_id == user_id,
        AuditLog.action == "identity_revealed"
    ).count()

    # Conversion rate
    conversion_rate = round((interview_requests / profile_views * 100), 2) if profile_views > 0 else 0

    # Generate recommendations
    recommendations = []

    if profile.visibility_score < 70:
        recommendations.append({
            "type": "warning",
            "message": f"Your CV has a {profile.visibility_score}% global visibility score. Review the BDIOF optimization suggestions to improve it."
        })

    if profile_views > 0 and interview_requests == 0:
        recommendations.append({
            "type": "tip",
            "message": "Recruiters viewed your profile but haven't requested an interview yet. Consider optimizing your skill keywords to better match job requirements."
        })

    if profile_views == 0:
        recommendations.append({
            "type": "info",
            "message": "Your profile hasn't been viewed yet. Make sure your skills are up to date and your CV is optimized."
        })

    if interview_requests > 0:
        recommendations.append({
            "type": "success",
            "message": f"🎉 {interview_requests} recruiter(s) have requested an interview with you! Check your email."
        })

    skill_count = len(profile.skills.split(',')) if profile.skills else 0
    if skill_count < 10:
        recommendations.append({
            "type": "tip",
            "message": f"You have {skill_count} skills detected. Candidates with 15+ skills get 2x more profile views."
        })

    return {
        "has_profile": True,
        "stats": {
            "profile_views": profile_views,
            "interview_requests": interview_requests,
            "conversion_rate": conversion_rate,
            "skill_score": profile.skill_score or 0,
            "visibility_score": profile.visibility_score or 0,
            "skills_count": skill_count
        },
        "recommendations": recommendations
    }
@router.post("/github/{user_id}")
def analyze_github(user_id: int, github_url: str, db: Session = Depends(get_db)):
    """
    BDIOF Vector 1 — GitHub Integration
    Analyzes candidate's GitHub profile and merges
    with existing CV data in the BDIOF pipeline.
    """
    from app.services.github_service import analyze_github_profile

    result = analyze_github_profile(github_url)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    # Merge GitHub languages with existing CV skills
    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).first()

    if profile:
        existing_skills = set(s.strip().lower() for s in (profile.skills or "").split(","))
        github_skills = set(result["top_languages"])
        merged_skills = existing_skills.union(github_skills)
        profile.skills = ", ".join(merged_skills)
        profile.github_url = github_url
        db.commit()

    return {
        "message": "GitHub profile analyzed and merged with CV data",
        "github_analysis": result
    }
@router.get("/recommended-jobs/{user_id}")
def get_recommended_jobs(user_id: int, db: Session = Depends(get_db)):
    """
    Recommendation Engine — returns top 3 jobs ranked
    by Skill-Score match against candidate's profile.
    """
    from app.models.job import Job
    from app.services.skill_matcher import compute_skill_score

    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).first()

    if not profile or not profile.skills:
        return {"recommendations": [], "has_profile": False}

    jobs = db.query(Job).filter(Job.is_active == True).all()
    scored_jobs = []

    for job in jobs:
        score = compute_skill_score(profile.skills, job.required_skills)
        missing_skills = []

        job_skills = set(s.strip().lower() for s in job.required_skills.split(","))
        candidate_skills = set(s.strip().lower() for s in profile.skills.split(","))
        missing_skills = list(job_skills - candidate_skills)

        scored_jobs.append({
            "job_id": job.id,
            "title": job.title,
            "description": job.description,
            "required_skills": job.required_skills,
            "location": job.location,
            "skill_score": score,
            "missing_skills": missing_skills[:5]
        })

    scored_jobs.sort(key=lambda x: x["skill_score"], reverse=True)
    return {
        "recommendations": scored_jobs[:3],
        "has_profile": True
    }

from pydantic import BaseModel
from typing import List

class SuggestionItem(BaseModel):
    original: str
    suggestion: str
    reason: str = ""

@router.post("/generate-optimized-cv/{user_id}")
async def generate_optimized_cv_endpoint(
    user_id: int,
    approved_suggestions: List[SuggestionItem],
    db: Session = Depends(get_db)
):
    """
    BDIOF Vector 1 — Generate Optimized CV
    Applies approved suggestions and returns downloadable PDF.
    """
    from app.services.cv_generator import generate_optimized_cv
    from fastapi.responses import FileResponse

    profile = db.query(CandidateProfile).filter(
        CandidateProfile.user_id == user_id
    ).first()

    if not profile or not profile.raw_resume_path:
        raise HTTPException(
            status_code=400,
            detail="No CV uploaded yet. Please upload your CV first."
        )

    if not os.path.exists(profile.raw_resume_path):
        raise HTTPException(
            status_code=404,
            detail="Original CV file not found."
        )

    try:
        suggestions_dict = [s.dict() for s in approved_suggestions]
        output_path, changes = generate_optimized_cv(
            profile.raw_resume_path,
            suggestions_dict,
            user_id
        )

        profile.optimized_resume_path = output_path
        db.commit()

        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename=f"EquityEngine_Optimized_CV_{user_id}.pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))