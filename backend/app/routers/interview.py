"""
AI Mock Interview endpoints. Questions are generated from the
candidate's own competency profile skills (or a specific job's
required_skills, if job_id is given), so the practice interview is
relevant to what the candidate is actually trying to demonstrate.
"""
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole, CandidateProfile, Job, InterviewSession
from app.schemas import (
    InterviewStartRequest, InterviewStartResponse, InterviewSubmitRequest,
    InterviewSubmitResponse, InterviewSessionOut, QuestionScore,
)
from app.deps import require_role
from app.services.ai_service import generate_interview_questions, score_interview_answers
from app.services.competency_engine import build_competency_profile

router = APIRouter(prefix="/candidates/interview", tags=["interview"])


@router.post("/start", response_model=InterviewStartResponse, status_code=201)
async def start_interview(
    payload: InterviewStartRequest,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")

    job_title = None
    skills = list(build_competency_profile(profile).keys())

    if payload.job_id:
        job = db.query(Job).filter(Job.id == payload.job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job_title = job.title
        # Prefer the job's required skills when practising for a
        # specific role — more relevant than the candidate's full
        # skill list, which may include things irrelevant to this job.
        if job.required_skills:
            skills = job.required_skills

    if not skills:
        raise HTTPException(
            status_code=400,
            detail="No skills found on your profile yet. Build your Competency Profile "
            "(upload a CV, link GitHub, or add a certification) before starting a mock interview.",
        )

    result = await generate_interview_questions(
        skills=skills, job_title=job_title, num_questions=payload.num_questions,
    )

    session = InterviewSession(
        candidate_id=profile.id,
        job_id=payload.job_id,
        questions=result["questions"],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return InterviewStartResponse(
        session_id=session.id, questions=result["questions"], provider_used=result["provider_used"],
    )


@router.post("/{session_id}/submit", response_model=InterviewSubmitResponse)
async def submit_interview_answers(
    session_id: uuid_lib.UUID,
    payload: InterviewSubmitRequest,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.candidate_id == profile.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    if session.answers is not None:
        raise HTTPException(status_code=400, detail="This session has already been submitted")

    qa_pairs = [{"question": a.question, "answer": a.answer} for a in payload.answers]
    result = await score_interview_answers(qa_pairs)

    session.answers = [a.model_dump() for a in payload.answers]
    session.scores = result["scores"]
    session.overall_score = result["overall_score"]
    db.commit()

    return InterviewSubmitResponse(
        session_id=session.id,
        scores=[QuestionScore(**s) for s in result["scores"]],
        overall_score=result["overall_score"],
        overall_feedback=result["overall_feedback"],
        provider_used=result["provider_used"],
    )


@router.get("/{session_id}", response_model=InterviewSessionOut)
def get_interview_session(
    session_id: uuid_lib.UUID,
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    session = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == session_id, InterviewSession.candidate_id == profile.id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    return session


@router.get("", response_model=list[InterviewSessionOut])
def list_interview_history(
    current_user: User = Depends(require_role(UserRole.candidate)),
    db: Session = Depends(get_db),
):
    profile = db.query(CandidateProfile).filter(CandidateProfile.user_id == current_user.id).first()
    if not profile:
        return []
    return (
        db.query(InterviewSession)
        .filter(InterviewSession.candidate_id == profile.id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )
