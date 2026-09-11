"""
Pydantic schemas used to validate incoming requests and shape outgoing
responses for the auth endpoints. Kept separate from models.py: models
describe the database, schemas describe the API contract, and the two
are allowed to diverge (e.g. a schema never includes hashed_password).

Note: email fields use `str` with a manual regex check rather than
Pydantic's EmailStr, because EmailStr requires the separate
`email-validator` package. If you do have email-validator installed,
you can switch back to EmailStr and drop the validator below.
"""
import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.models import UserRole, ScreeningMode, ApplicationStatus

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegister(BaseModel):
    email: str
    full_name: str
    password: str
    role: UserRole
    consent_given: bool

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email address")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v

    @field_validator("consent_given")
    @classmethod
    def must_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the terms and consent notice to register")
        return v

    @field_validator("role")
    @classmethod
    def no_admin_self_registration(cls, v: UserRole) -> UserRole:
        if v == UserRole.admin:
            raise ValueError("Admin accounts cannot be created via public registration")
        return v


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    consent_given: bool
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


# ---------------------------------------------------------------------
# Candidate profile schemas
# ---------------------------------------------------------------------

class RegionalTermsOut(BaseModel):
    institutions: list[str] = []
    tech_programmes: list[str] = []
    other_terms: list[str] = []
    all_matches: list[str] = []


class ProjectOut(BaseModel):
    title: str
    description: str


class CVUploadResponse(BaseModel):
    """
    Returned immediately after CV upload, for the human-in-the-loop
    review step (Chapter 3, Figure 3.2) — the candidate sees exactly
    what was extracted and can correct it before it's used anywhere.
    """
    cv_skills: list[str]
    regional_terms: RegionalTermsOut
    experience_level: str
    education_tier: str
    projects: list[ProjectOut]
    ats_score: int
    ats_breakdown: dict
    ats_suggestions: list[str]
    profile_completeness: float


class GitHubLinkRequest(BaseModel):
    github_username: str


class GitHubProfileSummary(BaseModel):
    name: Optional[str] = None
    bio: Optional[str] = None
    public_repos: Optional[int] = None
    followers: Optional[int] = None
    account_created: Optional[str] = None


class GitHubRepoOut(BaseModel):
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    url: Optional[str] = None
    pushed_at: Optional[str] = None


class GitHubAnalysisResponse(BaseModel):
    """Returned after linking a GitHub account, for the candidate to
    review before it's folded into their Competency Profile."""
    github_username: str
    profile_summary: GitHubProfileSummary
    repos: list[GitHubRepoOut]
    languages: dict
    activity: dict
    learning_trajectory: dict
    inferred_skills: list[str]
    g_act_score: float
    profile_completeness: float


# ---------------------------------------------------------------------
# Community pipeline schemas
# ---------------------------------------------------------------------

class CertificationCreate(BaseModel):
    name: str
    issuer: str = ""
    date_earned: str = ""


class CertificationOut(BaseModel):
    name: str
    issuer: str
    date_earned: str
    tier: int
    added_at: str


class StackOverflowLinkRequest(BaseModel):
    stackoverflow_user_id: str


class DevToLinkRequest(BaseModel):
    devto_username: str


class EndorsementCreate(BaseModel):
    candidate_id: uuid.UUID
    skill: str


class EndorsementSummary(BaseModel):
    total_endorsements: int
    by_skill: dict


class CommunityProfileResponse(BaseModel):
    certifications: list[CertificationOut]
    stackoverflow_data: Optional[dict] = None
    endorsement_summary: EndorsementSummary
    c_peer_score: float
    profile_completeness: float


class CompetencySkillOut(BaseModel):
    tier: str  # Declared / Confirmed / Verified
    sources: list[str]  # e.g. ["CV", "GitHub"]


class EvidenceScoreBreakdown(BaseModel):
    p_emb: float
    g_act: float
    c_peer: float
    l_traj: float
    evidence_score: float


class FullCompetencyProfileResponse(BaseModel):
    """The unified, badge-tagged skill list plus Evidence Score
    breakdown — this is the Competency Profile from Chapter 3's Figure
    3.2, and the basis for the Competency Dossier recruiters will see
    in BDIOF screening mode (built in a later phase)."""
    skills: dict[str, CompetencySkillOut]
    evidence_score_breakdown: EvidenceScoreBreakdown
    profile_completeness: float


class CandidateProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    bio: Optional[str] = None
    location: Optional[str] = None

    cv_file_url: Optional[str] = None
    cv_skills: Optional[list[str]] = None
    cv_projects: Optional[list[dict]] = None
    ats_score: Optional[float] = None
    regional_terms: Optional[dict] = None
    experience_level: Optional[str] = None
    education_tier: Optional[str] = None

    github_username: Optional[str] = None
    certifications: Optional[list] = None
    stackoverflow_data: Optional[dict] = None
    devto_data: Optional[dict] = None
    peer_endorsements: Optional[list] = None

    # The two pipeline-owned sub-scores are exposed here (not only on
    # the GitHub/community link responses) so the profile builder can
    # show what each pipeline currently contributes to the Evidence
    # Score, and how much a just-completed link moved it. Defaults keep
    # this additive for any client reading the older shape.
    g_act_score: float = 0.0
    c_peer_score: float = 0.0

    evidence_score: float
    badges: Optional[dict] = None
    profile_completeness: float

    class Config:
        from_attributes = True


class CandidateProfileUpdate(BaseModel):
    """Fields a candidate can edit directly, including corrections to
    what the CV parser extracted (the human-in-the-loop review)."""
    bio: Optional[str] = None
    location: Optional[str] = None
    cv_skills: Optional[list[str]] = None
    education_tier: Optional[str] = None
    experience_level: Optional[str] = None


# ---------------------------------------------------------------------
# Recruiter portal schemas
# ---------------------------------------------------------------------

class CompanyCreate(BaseModel):
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    website: Optional[str] = None
    industry: Optional[str] = None
    badge_earned: bool
    created_at: datetime

    class Config:
        from_attributes = True


class JobCreate(BaseModel):
    title: str
    description: str
    required_skills: list[str] = []
    location: Optional[str] = None
    screening_mode: ScreeningMode = ScreeningMode.standard


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[list[str]] = None
    location: Optional[str] = None
    screening_mode: Optional[ScreeningMode] = None
    is_active: Optional[bool] = None


class JobOut(BaseModel):
    id: uuid.UUID
    recruiter_id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    title: str
    description: str
    required_skills: Optional[list[str]] = None
    location: Optional[str] = None
    screening_mode: ScreeningMode
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID


class ApplicationOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    status: ApplicationStatus
    screening_mode_at_application: ScreeningMode
    evidence_score_at_application: Optional[float] = None

    # Auto-generated at the moment of rejection (see
    # services/feedback_service.py). Both are None for any application
    # that has not been rejected, and for rejections recorded before
    # this feature existed — the candidate UI treats a missing pair as
    # "no diagnostics available" rather than as an error.
    primary_reason: Optional[str] = None
    growth_tip: Optional[str] = None

    # Resolved from the related Job so the candidate's own views can
    # name the role without a request per application. Optional because
    # it is populated by the router, not read off the ORM row.
    job_title: Optional[str] = None

    applied_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplicationStatusUpdate(BaseModel):
    status: ApplicationStatus
    time_spent_seconds: Optional[int] = None


class DossierCandidateOut(BaseModel):
    """Shape is the same whether anonymised or revealed — is_anonymized
    tells the frontend which fields to expect populated. Left loose
    (dict-typed nested fields) rather than a strict schema per variant,
    since the two views genuinely have different field sets by design
    (see dossier_service.py's allow-list) and forcing them into one
    rigid schema would work against that safety property, not for it."""
    application_id: str
    is_anonymized: bool
    user_id: Optional[str] = None
    pseudonym: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    cv_file_url: Optional[str] = None
    github_username: Optional[str] = None
    regional_terms: Optional[dict] = None
    evidence_score_breakdown: dict
    skills: dict
    experience_level: str
    education_tier: str
    profile_completeness: float
    status: str
    applied_at: str

    # Present only on a rejected application, and only for information —
    # the recruiter sees what the candidate was told, but never sets it.
    primary_reason: Optional[str] = None
    growth_tip: Optional[str] = None


class ViewLimitStatus(BaseModel):
    limited: bool
    views_so_far: Optional[int] = None


# ---------------------------------------------------------------------
# Recruiter Talent Pool schemas
#
# The Talent Pool is identity-visible sourcing across all candidates,
# as distinct from the anonymised, per-job Competency Dossier above.
# See services/talent_pool_service.py for why the two differ, and for
# the fields deliberately absent here (location, bio, CV file, and any
# per-job application status).
# ---------------------------------------------------------------------

class TalentPoolPipelineOut(BaseModel):
    label: str
    score: float          # 0.0-1.0, this pipeline's own strength
    weight: float         # its share of the Evidence Score
    contribution: float   # score * weight — what it adds to the total
    linked: bool          # whether the candidate connected this pipeline
    detail: str           # short human-readable summary of the evidence


class TalentPoolSkillOut(BaseModel):
    skill: str
    tier: str
    sources: list[str]


class TalentPoolCandidateOut(BaseModel):
    candidate_id: str
    user_id: str
    full_name: str
    email: str
    experience_level: str
    education_tier: str
    evidence_score: float
    profile_completeness: float
    evidence_score_breakdown: EvidenceScoreBreakdown
    pipelines: dict[str, TalentPoolPipelineOut]
    skills: list[str]
    top_skills: list[TalentPoolSkillOut]
    github_username: Optional[str] = None
    total_applications: int
    invited_job_ids: list[str]
    registered_at: datetime


class TalentPoolOut(BaseModel):
    candidates: list[TalentPoolCandidateOut]
    total_count: int
    limit: int
    offset: int


class TalentPoolInviteRequest(BaseModel):
    job_id: uuid.UUID
    note: Optional[str] = None

    @field_validator("note")
    @classmethod
    def note_max_length(cls, v: Optional[str]) -> Optional[str]:
        # The note is embedded in a notification the candidate reads in
        # a list; a long one would be truncated in the UI anyway, so it
        # is rejected here rather than silently cut off.
        if v is not None and len(v) > 500:
            raise ValueError("Note must be 500 characters or fewer")
        return v


class TalentPoolInviteResponse(BaseModel):
    detail: str
    candidate_id: str
    job_id: str
    job_title: str


# ---------------------------------------------------------------------
# Bias Audit Engine / admin schemas
# ---------------------------------------------------------------------

class ModeRateOut(BaseModel):
    total_applications: int
    selected_count: int
    shortlist_rate: Optional[float] = None
    small_sample: bool


class VisibilityGapOut(BaseModel):
    rates_by_mode: dict[str, ModeRateOut]
    visibility_gap: Optional[float] = None
    visibility_gap_percent_improvement: Optional[float] = None
    warnings: list[str]
    methodology_note: str


class TimeseriesPointOut(BaseModel):
    period: str
    standard_shortlist_rate: Optional[float] = None
    bdiof_shortlist_rate: Optional[float] = None
    visibility_gap: Optional[float] = None
    standard_sample_size: int
    bdiof_sample_size: int


class DiversityReportOut(BaseModel):
    all_candidates_distribution: dict[str, float]
    shortlisted_candidates_distribution: dict[str, float]
    total_candidates: int
    total_shortlisted: int
    small_sample: bool


class RecruiterBiasScoreOut(BaseModel):
    recruiter_id: str
    recruiter_name: str
    total_applications_received: int
    anonymized_shortlist_rate: Optional[float] = None
    identity_visible_shortlist_rate: Optional[float] = None
    internal_visibility_gap: Optional[float] = None
    applicant_pool_graduate_share: Optional[float] = None
    shortlisted_graduate_share: Optional[float] = None
    bias_score: Optional[float] = None
    small_sample: bool


class PlatformStatsOut(BaseModel):
    total_candidates: int
    total_recruiters: int
    total_companies: int
    total_jobs: int
    active_jobs: int
    total_applications: int
    total_shortlisted: int
    jobs_by_screening_mode: dict[str, int]


# ---------------------------------------------------------------------
# Admin registry / activity-feed schemas
#
# These shape the Admin Dashboard's live monitoring view. They carry
# real names and email addresses, so — unlike most schemas in this file
# — they must only ever be returned from a route guarded by
# require_role(UserRole.admin). See routers/admin.py.
# ---------------------------------------------------------------------

class AdminCandidateRowOut(BaseModel):
    candidate_id: Optional[str] = None  # None until the candidate builds a profile
    user_id: str
    full_name: str
    email: str
    is_active: bool
    has_profile: bool
    location: Optional[str] = None
    education_tier: Optional[str] = None
    experience_level: Optional[str] = None
    evidence_score: float
    profile_completeness: float
    has_cv: bool
    has_github: bool
    has_community: bool
    total_applications: int
    total_shortlisted: int
    registered_at: datetime
    last_action_at: Optional[datetime] = None


class AdminRecruiterRowOut(BaseModel):
    user_id: str
    full_name: str
    email: str
    is_active: bool
    company_name: Optional[str] = None
    total_jobs: int
    active_jobs: int
    total_applications_received: int
    total_shortlisted: int
    total_views: int
    total_reveals: int
    registered_at: datetime
    last_action_at: Optional[datetime] = None


class AdminAuditLogRowOut(BaseModel):
    id: str
    action: str
    was_anonymized: bool
    screening_mode: Optional[str] = None
    time_spent_seconds: Optional[int] = None
    created_at: datetime
    recruiter_id: str
    recruiter_name: str
    candidate_id: str
    candidate_name: str
    job_id: Optional[str] = None
    job_title: Optional[str] = None


class AdminActivityFeedOut(BaseModel):
    logs: list[AdminAuditLogRowOut]
    total_count: int
    limit: int
    offset: int
    available_actions: list[str]
    server_time: datetime


# ---------------------------------------------------------------------
# Chat and notification schemas
# ---------------------------------------------------------------------

class MessageCreate(BaseModel):
    receiver_id: uuid.UUID
    job_id: uuid.UUID
    content: str


class MessageOut(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID
    job_id: uuid.UUID
    content: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    other_user_id: str
    other_user_name: str
    other_user_role: Optional[str] = None
    job_id: str
    job_title: str
    last_message: str
    last_message_at: str
    unread_count: int


class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    message: str
    is_read: bool
    related_id: Optional[uuid.UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountOut(BaseModel):
    unread_count: int


# ---------------------------------------------------------------------
# AI Mock Interview schemas
# ---------------------------------------------------------------------

class InterviewStartRequest(BaseModel):
    job_id: Optional[uuid.UUID] = None
    num_questions: int = 5


class InterviewStartResponse(BaseModel):
    session_id: uuid.UUID
    questions: list[str]
    provider_used: str


class AnswerSubmission(BaseModel):
    question: str
    answer: str


class InterviewSubmitRequest(BaseModel):
    answers: list[AnswerSubmission]


class QuestionScore(BaseModel):
    score: float
    feedback: str


class InterviewSubmitResponse(BaseModel):
    session_id: uuid.UUID
    scores: list[QuestionScore]
    overall_score: float
    overall_feedback: str
    provider_used: str


class InterviewSessionOut(BaseModel):
    id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    questions: Optional[list] = None
    answers: Optional[list] = None
    scores: Optional[list] = None
    overall_score: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True
