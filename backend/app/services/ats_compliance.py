"""
Computes a conventional ATS-compatibility score for a candidate's CV.

Important distinction for anyone reading this alongside the thesis:
this score measures how well a CV would score against a STANDARD,
structure-based ATS parser (contact info present, standard section
headers, reasonable length, skill keyword density). It is shown to
candidates purely as diagnostic, actionable feedback ("here's how to
improve your CV's parseability").

It is NOT the Evidence Score, and it never feeds into candidate
ranking anywhere in this system. Evidence Score (built in a later
phase) evaluates competency; this function evaluates document
formatting. Keeping the two completely separate is what stops
EquityEngine from quietly becoming just another ATS optimiser — the
exact failure mode identified in Chapter 1's Statement of the Problem.
"""
import re

_EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")

_SECTION_HEADERS = {
    "experience": re.compile(r"\b(experience|work experience|employment)\b", re.IGNORECASE),
    "education": re.compile(r"\beducation\b", re.IGNORECASE),
    "skills": re.compile(r"\bskills\b", re.IGNORECASE),
}

_BULLET_PATTERN = re.compile(r"^\s*[-*•\u2022]", re.MULTILINE)


def compute_ats_score(text: str, skills_found: list[str]) -> dict:
    """
    Returns a dict with the overall score (0-100) and a breakdown, so
    the frontend can show candidates *why* they got the score they did
    rather than just a bare number.
    """
    breakdown = {}

    # Contact info present (10 points)
    breakdown["contact_info"] = 10 if _EMAIL_PATTERN.search(text) else 0

    # Standard section headers present (10 points each, 30 total)
    section_score = 0
    for name, pattern in _SECTION_HEADERS.items():
        if pattern.search(text):
            section_score += 10
    breakdown["standard_sections"] = section_score

    # Skill keyword density (up to 30 points, 3 per matched skill, capped)
    breakdown["skill_keywords"] = min(len(skills_found) * 3, 30)

    # Reasonable length — too short suggests missing detail, too long
    # suggests an ATS parser may truncate it (10 points)
    word_count = len(text.split())
    if 200 <= word_count <= 1200:
        breakdown["length"] = 10
    elif 100 <= word_count < 200 or 1200 < word_count <= 2000:
        breakdown["length"] = 5
    else:
        breakdown["length"] = 0

    # Bullet point usage — structured, parser-friendly formatting (10 points)
    bullet_count = len(_BULLET_PATTERN.findall(text))
    breakdown["formatting"] = 10 if bullet_count >= 3 else (5 if bullet_count >= 1 else 0)

    # Phone number present (10 points)
    breakdown["phone_number"] = 10 if _PHONE_PATTERN.search(text) else 0

    total = sum(breakdown.values())
    return {
        "score": min(total, 100),
        "breakdown": breakdown,
        "suggestions": _generate_suggestions(breakdown, word_count, bullet_count),
    }


def _generate_suggestions(breakdown: dict, word_count: int, bullet_count: int) -> list[str]:
    suggestions = []
    if breakdown["contact_info"] == 0:
        suggestions.append("Add a clear email address so recruiters and ATS parsers can find it.")
    if breakdown["standard_sections"] < 30:
        suggestions.append("Use standard section headers (Experience, Education, Skills) so parsers can locate content reliably.")
    if breakdown["skill_keywords"] < 15:
        suggestions.append("List more of your technical skills explicitly — this also feeds your Competency Profile once you link GitHub and community evidence.")
    if word_count < 200:
        suggestions.append("Your CV looks quite short — consider adding more detail about your experience and projects.")
    elif word_count > 1200:
        suggestions.append("Your CV is quite long — consider trimming to the most relevant, recent experience.")
    if bullet_count < 3:
        suggestions.append("Use bullet points to describe responsibilities and achievements — this is easier for both parsers and human reviewers to scan.")
    if breakdown["phone_number"] == 0:
        suggestions.append("Add a phone number for recruiters to reach you directly.")
    return suggestions
