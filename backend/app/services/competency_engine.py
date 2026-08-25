"""
Competency Engine — merges all three pipelines (CV, GitHub, Community)
into a unified Competency Profile, assigns verification badges, and
computes the Evidence Score:

    E_s = 0.40·P_emb + 0.25·G_act + 0.20·C_peer + 0.15·L_traj

Where:
    P_emb  — semantic similarity between the candidate's project
             descriptions and their own claimed skills (self-
             consistency check, used for the profile-level baseline
             score). A job-specific P_emb, comparing projects against
             a SPECIFIC job's requirements, is computed separately at
             application time (see recruiter portal phase) and stored
             per-application in applications.evidence_score_at_application
             — the two are related but not the same computation.
    G_act  — GitHub activity, already computed by the GitHub pipeline
             (github_service.compute_g_act_score) and stored as
             profile.g_act_score.
    C_peer — community standing, already computed by the community
             pipeline (community_service.compute_c_peer_score) and
             stored as profile.c_peer_score.
    L_traj — learning trajectory, computed here from the GitHub
             pipeline's raw trend and repo-creation-date data.

All four components are 0.0-1.0 before weighting, so E_s is also
0.0-1.0 by construction (bounded, since each term contributes at most
its weight).
"""
from collections import defaultdict
from datetime import datetime, timezone
import re

from app.models import CandidateProfile
from app.data.skill_taxonomy import SKILL_LOOKUP
from app.services.embedding_service import best_match_similarity

EVIDENCE_WEIGHTS = {"p_emb": 0.40, "g_act": 0.25, "c_peer": 0.20, "l_traj": 0.15}

BADGE_TIERS = {1: "Declared", 2: "Confirmed", 3: "Verified"}


def update_profile_completeness(profile: CandidateProfile) -> float:
    """
    Simple three-way completeness measure: each pipeline contributes
    up to one third, based on whether it has any data at all. This
    answers "has the candidate engaged with this pipeline?" not "how
    strong is this evidence?" — the Evidence Score answers that.
    """
    weight_per_pipeline = 100 / 3
    completeness = 0.0

    if profile.cv_skills:
        completeness += weight_per_pipeline
    if profile.github_username:
        completeness += weight_per_pipeline
    if profile.certifications or profile.peer_endorsements or profile.stackoverflow_data or profile.devto_data:
        completeness += weight_per_pipeline

    return round(completeness, 1)


# ---------------------------------------------------------------------
# Unified skill list and verification badges
# ---------------------------------------------------------------------

def _normalize_skill(skill: str) -> str:
    """Maps a skill string to its canonical taxonomy form where
    possible, so 'python' and 'Python' and 'PYTHON' all merge into one
    entry rather than being counted as three different skills."""
    return SKILL_LOOKUP.get(skill.lower().strip(), skill.strip())


def _skills_from_cv(profile: CandidateProfile) -> set[str]:
    return {_normalize_skill(s) for s in (profile.cv_skills or [])}


def _skills_from_github(profile: CandidateProfile) -> set[str]:
    inferred = set()
    if profile.github_activity:
        inferred |= set(profile.github_activity.get("inferred_skills", []))
    if profile.github_languages:
        inferred |= set(profile.github_languages.keys())
    return {_normalize_skill(s) for s in inferred}


def _skills_from_community(profile: CandidateProfile) -> set[str]:
    """
    A skill counts as community-corroborated if it's named in a
    certification's title/issuer text, or if another candidate has
    endorsed the profile owner for it (peer endorsements are community
    pipeline evidence — see community_service.py).

    Uses word-boundary matching (\\b), not plain substring containment
    — naive `"r" in text` would false-positive-match the language "R"
    against ordinary words like "softwaRe" or "EngineeRing", which is
    exactly the kind of silent bug that erodes trust in a bias-
    measurement tool if it ships unnoticed.
    """
    found = set()

    cert_text = " ".join(
        f"{c.get('name', '')} {c.get('issuer', '')}" for c in (profile.certifications or [])
    ).lower()
    for skill_lower, canonical in SKILL_LOOKUP.items():
        pattern = r"\b" + re.escape(skill_lower) + r"\b"
        if re.search(pattern, cert_text):
            found.add(canonical)

    for endorsement in (profile.peer_endorsements or []):
        found.add(_normalize_skill(endorsement["skill"]))

    return found


def build_competency_profile(profile: CandidateProfile) -> dict:
    """
    Returns {skill: {"tier": "Declared"/"Confirmed"/"Verified",
    "sources": [...]}} — the unified, badge-tagged skill list that is
    the direct output of Chapter 3's Figure 3.2 (Competency Profile
    Building activity diagram), and the thing recruiters see instead
    of a CV in BDIOF screening mode (built in the next phase).

    Badge tier is the COUNT of distinct pipelines that surface a
    skill, not which specific pipelines — a self-taught candidate with
    Python on GitHub and a Python-relevant community certification
    reaches Confirmed (2 sources) without ever uploading a CV, which
    is the exact paradox-resolution example from Chapter 1's
    Background: they can out-rank a CV-only graduate (Declared, 1
    source) despite having no formal credential at all.
    """
    cv_skills = _skills_from_cv(profile)
    github_skills = _skills_from_github(profile)
    community_skills = _skills_from_community(profile)

    all_skills = cv_skills | github_skills | community_skills
    competency_profile = {}

    for skill in sorted(all_skills):
        sources = []
        if skill in cv_skills:
            sources.append("CV")
        if skill in github_skills:
            sources.append("GitHub")
        if skill in community_skills:
            sources.append("Community")

        competency_profile[skill] = {
            "tier": BADGE_TIERS[len(sources)],
            "sources": sources,
        }

    return competency_profile


# ---------------------------------------------------------------------
# L_traj — learning trajectory (15% weight)
# ---------------------------------------------------------------------

_TREND_SCORES = {"Increasing": 1.0, "Stable": 0.6, "Declining": 0.3, "Insufficient data": 0.0}


def compute_l_traj_score(profile: CandidateProfile) -> float:
    """
    Combines two signals: the GitHub pipeline's push-recency trend
    (proxy for commit frequency trend — see github_service.
    estimate_learning_trajectory), weighted 60%, and a skill
    acquisition rate derived from repo creation dates, weighted 40%.

    Skill acquisition rate = share of the candidate's distinct GitHub
    languages first seen in the last 2 years — a candidate still
    picking up new languages recently scores higher than one whose
    entire language set was established years ago and hasn't grown.
    """
    if not profile.learning_trajectory:
        return 0.0

    trend = profile.learning_trajectory.get("trend", "Insufficient data")
    trend_component = _TREND_SCORES.get(trend, 0.0)

    acquisition_component = _compute_skill_acquisition_rate(profile.github_repos or [])

    return round(0.6 * trend_component + 0.4 * acquisition_component, 3)


def _compute_skill_acquisition_rate(repos: list[dict]) -> float:
    first_seen_year: dict[str, int] = {}
    for repo in repos:
        lang = repo.get("language")
        created_at = repo.get("created_at")
        if not lang or not created_at:
            continue
        year = int(created_at[:4])
        if lang not in first_seen_year or year < first_seen_year[lang]:
            first_seen_year[lang] = year

    if not first_seen_year:
        return 0.0

    current_year = datetime.now(timezone.utc).year
    recent = sum(1 for year in first_seen_year.values() if year >= current_year - 2)
    return min(recent / len(first_seen_year), 1.0)


# ---------------------------------------------------------------------
# P_emb — baseline self-consistency score (40% weight)
# ---------------------------------------------------------------------

def compute_p_emb_baseline(profile: CandidateProfile) -> float:
    """
    Baseline P_emb for profile-level display: measures whether the
    candidate's PROJECTS actually substantiate the SKILLS they claim,
    using semantic similarity rather than exact keyword overlap (so
    a project described as "built a REST API for order management"
    counts as evidence for a claimed "Backend Development" skill even
    without the exact words matching).

    This is deliberately NOT the same computation as job-matching
    P_emb (candidate projects vs. a specific job's requirements) —
    that happens later, per-application, once job postings exist. This
    baseline answers a narrower question: "is this profile internally
    coherent?" rather than "is this profile a good fit for job X?"
    """
    project_texts = [
        p.get("description", "") for p in (profile.cv_projects or [])
    ] + [
        r.get("description", "") for r in (profile.github_repos or []) if r.get("description")
    ]

    unified = build_competency_profile(profile)
    skill_texts = list(unified.keys())

    return round(best_match_similarity(project_texts, skill_texts), 3)


# ---------------------------------------------------------------------
# Full Evidence Score
# ---------------------------------------------------------------------

def compute_evidence_score(p_emb: float, g_act: float, c_peer: float, l_traj: float) -> float:
    return round(
        EVIDENCE_WEIGHTS["p_emb"] * p_emb
        + EVIDENCE_WEIGHTS["g_act"] * g_act
        + EVIDENCE_WEIGHTS["c_peer"] * c_peer
        + EVIDENCE_WEIGHTS["l_traj"] * l_traj,
        3,
    )


def compute_job_specific_evidence_score(profile: CandidateProfile, job) -> dict:
    """
    Recomputes P_emb against a SPECIFIC job's requirements (rather than
    the candidate's own claimed skills, which is what the profile-level
    baseline P_emb measures), and recombines it with the candidate's
    existing G_act/C_peer/L_traj to produce a job-specific Evidence
    Score. This is what ranks candidates in a recruiter's Competency
    Dossier for a given job (Chapter 3, Section 3.5) — the baseline
    evidence_score on the profile is NOT used for ranking, because it
    answers a different question ("is this profile internally
    coherent?") than the one a recruiter is actually asking ("is this
    candidate a good match for THIS job?").
    """
    project_texts = [
        p.get("description", "") for p in (profile.cv_projects or [])
    ] + [
        r.get("description", "") for r in (profile.github_repos or []) if r.get("description")
    ]

    job_reference_texts = list(job.required_skills or [])
    if job.description:
        job_reference_texts.append(job.description)

    p_emb = round(best_match_similarity(project_texts, job_reference_texts), 3)

    evidence_score = compute_evidence_score(
        p_emb=p_emb,
        g_act=profile.g_act_score or 0.0,
        c_peer=profile.c_peer_score or 0.0,
        l_traj=profile.l_traj_score or 0.0,
    )

    return {
        "p_emb": p_emb,
        "g_act": profile.g_act_score or 0.0,
        "c_peer": profile.c_peer_score or 0.0,
        "l_traj": profile.l_traj_score or 0.0,
        "evidence_score": evidence_score,
    }


def recompute_competency_profile(profile: CandidateProfile) -> dict:
    """
    The main orchestrator — called after ANY pipeline update (CV
    upload, GitHub link, certification added, endorsement received,
    etc.) to keep the unified profile, badges, and Evidence Score
    consistent. This is the "merge" step in Chapter 3's Figure 3.2.

    Mutates profile in place (caller is responsible for db.commit()),
    and also returns the unified competency_profile dict since that
    isn't stored as its own column — profile.badges stores just the
    skill-to-tier mapping (a lighter view), while the full dict with
    per-skill sources is recomputed on demand for API responses.
    """
    l_traj = compute_l_traj_score(profile)
    p_emb = compute_p_emb_baseline(profile)

    profile.l_traj_score = l_traj
    profile.p_emb_score = p_emb
    # g_act_score and c_peer_score are set by their own pipelines
    # (github_service / community_service) — read here, not written.

    profile.evidence_score = compute_evidence_score(
        p_emb=p_emb,
        g_act=profile.g_act_score or 0.0,
        c_peer=profile.c_peer_score or 0.0,
        l_traj=l_traj,
    )

    competency_profile = build_competency_profile(profile)
    profile.badges = {skill: data["tier"] for skill, data in competency_profile.items()}
    profile.profile_completeness = update_profile_completeness(profile)

    return competency_profile
