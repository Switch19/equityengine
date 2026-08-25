"""
Builds the Competency Dossier a recruiter sees for a job's applicants,
in either anonymised (BDIOF/Hybrid pre-reveal) or identity-visible
(Standard/Hybrid post-reveal) form.

SECURITY-RELEVANT DESIGN NOTE, read before touching this file:

build_anonymized_candidate_view() below is written using an ALLOW-LIST
pattern — it constructs a fresh dict field-by-field from an explicit
whitelist, rather than taking the full candidate profile and trying to
strip out identity-revealing fields. This is deliberate. A block-list
("copy everything except X, Y, Z") silently leaks whatever new field
gets added to CandidateProfile in the future and is forgotten from the
strip-list — exactly the kind of bug that would quietly undermine this
project's entire thesis. An allow-list can only ever under-include,
never over-include, which is the safe failure direction here.

Fields deliberately EXCLUDED from the anonymised view, and why:
    - full_name, email          — direct identity
    - location                  — the literal signal BDIOF exists to hide
    - cv_file_url                — filenames often contain the
                                    candidate's real name (e.g.
                                    "John_Doe_CV.pdf")
    - github_username, repo URLs — usernames are frequently real names
                                    or recognisable handles; repo names
                                    can be identifying
    - regional_terms             — contains SPECIFIC institution and
                                    tech-programme names (e.g.
                                    "University of Lagos"), which is
                                    exactly the geographic/institutional
                                    signal this system exists to hide
                                    from initial screening. Only the
                                    already-generic education_tier
                                    category (Graduate/Bootcamp/Self-
                                    Taught/Undisclosed) is shown.
    - bio                        — free text the candidate wrote about
                                    themselves, commonly self-identifying
                                    ("Hi, I'm [name] from [city]...").
                                    Not currently scrubbed of PII — a
                                    disclosed limitation, not a hidden one.
    - stackoverflow_data.display_name / profile_url, devto_data.username
                                  — identity via a linked external account
"""
import hashlib

from app.models import CandidateProfile, Job, Application
from app.services.competency_engine import build_competency_profile, compute_job_specific_evidence_score


def generate_pseudonym(candidate_id) -> str:
    """
    Deterministic, presentable stand-in for a candidate's real
    identity — same candidate always gets the same pseudonym (stable
    across a recruiter's repeated views of a dossier), without
    exposing the raw database UUID to the frontend.
    """
    digest = hashlib.sha256(str(candidate_id).encode()).hexdigest()[:6].upper()
    return f"Candidate-{digest}"


def build_anonymized_candidate_view(profile: CandidateProfile, job: Job, application: Application) -> dict:
    """See module docstring — allow-list of safe fields only."""
    score_breakdown = compute_job_specific_evidence_score(profile, job)
    competency_profile = build_competency_profile(profile)

    return {
        "application_id": str(application.id),
        "pseudonym": generate_pseudonym(profile.id),
        "evidence_score_breakdown": score_breakdown,
        "skills": competency_profile,
        "experience_level": profile.experience_level or "Not specified",
        "education_tier": profile.education_tier or "Undisclosed",
        "profile_completeness": profile.profile_completeness,
        "status": application.status.value,
        "applied_at": application.applied_at.isoformat(),
        "is_anonymized": True,
    }


def build_revealed_candidate_view(profile: CandidateProfile, user, job: Job, application: Application) -> dict:
    """
    Full view, shown once identity has been legitimately revealed
    (Standard mode from the start, or BDIOF/Hybrid after a recruiter's
    explicit reveal action — see the /reveal endpoint, which is the
    only code path permitted to call this function for a BDIOF/Hybrid
    application).
    """
    score_breakdown = compute_job_specific_evidence_score(profile, job)
    competency_profile = build_competency_profile(profile)

    return {
        "application_id": str(application.id),
        "user_id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "location": profile.location,
        "bio": profile.bio,
        "cv_file_url": profile.cv_file_url,
        "github_username": profile.github_username,
        "regional_terms": profile.regional_terms,
        "evidence_score_breakdown": score_breakdown,
        "skills": competency_profile,
        "experience_level": profile.experience_level or "Not specified",
        "education_tier": profile.education_tier or "Undisclosed",
        "profile_completeness": profile.profile_completeness,
        "status": application.status.value,
        "applied_at": application.applied_at.isoformat(),
        "is_anonymized": False,
    }


def rank_applications_by_evidence_score(candidate_views: list[dict]) -> list[dict]:
    """
    Both anonymised and revealed views carry the same
    evidence_score_breakdown shape, so this works for either. Ranking
    by job-specific Evidence Score happens regardless of screening
    mode — what differs between modes is whether identity is visible
    alongside that ranking, not the ranking itself. Any bias in
    Standard mode therefore shows up in the recruiter's shortlisting
    DECISIONS relative to this ranking (captured by the Bias Audit
    Engine), not in the ranking algorithm.
    """
    return sorted(
        candidate_views,
        key=lambda v: v["evidence_score_breakdown"]["evidence_score"],
        reverse=True,
    )
