def compute_skill_score(candidate_skills: str, job_requirements: str) -> float:
    if not candidate_skills or not job_requirements:
        return 0.0
    candidate_set = set(s.strip().lower() for s in candidate_skills.split(","))
    job_set = set(s.strip().lower() for s in job_requirements.split(","))
    if not job_set:
        return 0.0
    matches = candidate_set.intersection(job_set)
    score = (len(matches) / len(job_set)) * 100
    return round(min(100, score), 2)

def get_skill_tier(skill_count: int, skill_score: float) -> str:
    """Generate a meaningful anonymous identifier based on skill tier."""
    if skill_count >= 20 and skill_score >= 80:
        tier = "Senior"
    elif skill_count >= 15 and skill_score >= 60:
        tier = "Mid-Level"
    elif skill_count >= 8:
        tier = "Junior"
    else:
        tier = "Entry-Level"

    if skill_score >= 70:
        stack = "Full-Stack"
    elif skill_score >= 40:
        stack = "Backend"
    else:
        stack = "Tech"

    return f"{tier} {stack} Professional"

def anonymize_candidate(candidate: dict) -> dict:
    """
    BDIOF Vector 2 — Strip identity markers and return
    a neutralized candidate profile for recruiter view.
    """
    skill_count = len(candidate.get("skills", "").split(",")) if candidate.get("skills") else 0
    skill_score = candidate.get("skill_score", 0)
    tier = get_skill_tier(skill_count, skill_score)

    return {
        "anonymous_id": f"CANDIDATE-{candidate.get('id', '??')}",
        "regional_identifier": tier,
        "skills": candidate.get("skills", ""),
        "skill_score": skill_score,
        "visibility_score": candidate.get("visibility_score", 0),
        "is_anonymized": True
    }

def reveal_candidate(candidate: dict) -> dict:
    return { **candidate, "is_anonymized": False }