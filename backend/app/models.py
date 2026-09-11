"""
SQLAlchemy ORM models — one class per table, matching the 9-table
schema and ERD in Chapter 3 of the project report.

Design notes:
- Primary keys are UUIDs generated in Python (uuid.uuid4), not by the
  database, so we don't depend on a Postgres extension (pgcrypto /
  uuid-ossp) being enabled on your local install.
- JSON columns store structured pipeline output (e.g. parsed CV skills,
  GitHub repo lists) without needing a separate table per field —
  appropriate here since this data is read/written as a whole blob by
  the Competency Engine, not queried field-by-field.
- Enums are defined as native Python enums AND passed to SQLAlchemy's
  Enum type, so Postgres enforces valid values at the database level,
  not just in application code.
"""
import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, Float, Integer, Text, DateTime,
    ForeignKey, Enum as SAEnum, JSON
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return uuid.uuid4()


# ---------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------

class UserRole(str, enum.Enum):
    candidate = "candidate"
    recruiter = "recruiter"
    admin = "admin"


class ScreeningMode(str, enum.Enum):
    standard = "standard"
    bdiof = "bdiof"
    hybrid = "hybrid"


class ApplicationStatus(str, enum.Enum):
    applied = "applied"
    viewed = "viewed"
    shortlisted = "shortlisted"
    interview = "interview"
    rejected = "rejected"
    offered = "offered"


# ---------------------------------------------------------------------
# 1. users
# ---------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SAEnum(UserRole), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Terms & consent (required before a candidate/recruiter can use the platform)
    consent_given = Column(Boolean, default=False, nullable=False)
    consent_at = Column(DateTime, nullable=True)

    # Password reset (see auth.py's /forgot-password and /reset-password)
    reset_token = Column(String, nullable=True)
    reset_token_expires = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    candidate_profile = relationship(
        "CandidateProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    companies = relationship("Company", back_populates="recruiter", cascade="all, delete-orphan")


# ---------------------------------------------------------------------
# 2. companies
# ---------------------------------------------------------------------

class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    website = Column(String, nullable=True)
    industry = Column(String, nullable=True)

    # Admin-only bias metrics (never shown to the recruiter who owns this company)
    bias_score = Column(Float, nullable=True)
    badge_earned = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    recruiter = relationship("User", back_populates="companies")
    jobs = relationship("Job", back_populates="company", cascade="all, delete-orphan")


# ---------------------------------------------------------------------
# 3. candidate_profiles
# ---------------------------------------------------------------------

class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)

    bio = Column(Text, nullable=True)
    location = Column(String, nullable=True)  # stored, but withheld from BDIOF dossiers

    # --- Pipeline 1: Formal (CV) ---
    cv_file_url = Column(String, nullable=True)
    cv_skills = Column(JSON, nullable=True)          # list[str]
    cv_projects = Column(JSON, nullable=True)         # list[dict]
    ats_score = Column(Float, nullable=True)
    regional_terms = Column(JSON, nullable=True)      # list[str] detected regional terminology
    experience_level = Column(String, nullable=True)
    education_tier = Column(String, nullable=True)    # graduate / self-taught / bootcamp / undisclosed

    # --- Pipeline 2: Informal (GitHub) ---
    github_username = Column(String, nullable=True)
    github_repos = Column(JSON, nullable=True)
    github_languages = Column(JSON, nullable=True)
    github_activity = Column(JSON, nullable=True)     # commit frequency, stars, etc.
    learning_trajectory = Column(JSON, nullable=True)

    # --- Pipeline 3: Community ---
    certifications = Column(JSON, nullable=True)      # e.g. Andela, ALX, Genesys Hub
    stackoverflow_data = Column(JSON, nullable=True)
    devto_data = Column(JSON, nullable=True)
    peer_endorsements = Column(JSON, nullable=True)

    # --- Competency Engine output ---
    p_emb_score = Column(Float, default=0.0, nullable=False)
    g_act_score = Column(Float, default=0.0, nullable=False)
    c_peer_score = Column(Float, default=0.0, nullable=False)
    l_traj_score = Column(Float, default=0.0, nullable=False)
    evidence_score = Column(Float, default=0.0, nullable=False)
    badges = Column(JSON, nullable=True)              # {"Python": "Verified", "React": "Confirmed"}
    profile_completeness = Column(Float, default=0.0, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="candidate_profile")
    applications = relationship("Application", back_populates="candidate", cascade="all, delete-orphan")
    interview_sessions = relationship("InterviewSession", back_populates="candidate", cascade="all, delete-orphan")


# ---------------------------------------------------------------------
# 4. jobs
# ---------------------------------------------------------------------

class Job(Base):
    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    required_skills = Column(JSON, nullable=True)     # list[str]
    location = Column(String, nullable=True)
    screening_mode = Column(SAEnum(ScreeningMode), default=ScreeningMode.standard, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="jobs")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan")


# ---------------------------------------------------------------------
# 5. applications
# ---------------------------------------------------------------------

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)

    status = Column(SAEnum(ApplicationStatus), default=ApplicationStatus.applied, nullable=False)
    screening_mode_at_application = Column(SAEnum(ScreeningMode), nullable=False)
    was_anonymized_when_selected = Column(Boolean, nullable=True)
    evidence_score_at_application = Column(Float, nullable=True)

    # --- Automated post-rejection feedback ---
    #
    # Written once, automatically, at the moment an application moves to
    # `rejected` (see services/feedback_service.py and the status-change
    # endpoint in routers/recruiters.py). Stored on the application row
    # rather than recomputed on read for two reasons:
    #
    #   1. The diagnosis compares the candidate against the median of
    #      the applicants who were advanced for THIS job AT THAT TIME.
    #      That benchmark keeps moving as the recruiter works through
    #      the pipeline, so a value recomputed weeks later would explain
    #      a different decision than the one that was actually made.
    #   2. It makes the feedback auditable — what the candidate was told
    #      is durable, not a function of current database state.
    #
    # Nullable because every application predating this feature, and
    # every application never rejected, legitimately has none.
    primary_reason = Column(String, nullable=True)
    growth_tip = Column(String, nullable=True)

    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    candidate = relationship("CandidateProfile", back_populates="applications")
    job = relationship("Job", back_populates="applications")


# ---------------------------------------------------------------------
# 6. audit_logs
# ---------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    recruiter_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)

    action = Column(String, nullable=False)  # viewed, shortlisted, revealed, rejected, offered
    was_anonymized = Column(Boolean, nullable=False)
    screening_mode = Column(SAEnum(ScreeningMode), nullable=True)
    time_spent_seconds = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------
# 7. messages
# ---------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    receiver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)

    content = Column(Text, nullable=True)
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ---------------------------------------------------------------------
# 8. interview_sessions
# ---------------------------------------------------------------------

class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    candidate_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)

    questions = Column(JSON, nullable=True)
    answers = Column(JSON, nullable=True)
    scores = Column(JSON, nullable=True)
    overall_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    candidate = relationship("CandidateProfile", back_populates="interview_sessions")


# ---------------------------------------------------------------------
# 9. notifications
# ---------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    related_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
