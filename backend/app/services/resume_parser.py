"""
Pipeline 1 (Formal): CV parsing.

Given raw CV file bytes, this module extracts:
  - skills (matched against the curated taxonomy)
  - regional terms (African institutions, tech hubs, and terminology
    that a conventional ATS keyword-matcher would not recognise)
  - experience level (heuristic, from "X years" phrasing)
  - education tier (graduate / bootcamp / self-taught / undisclosed)
  - projects (heuristic section-based extraction)

These are heuristics, not a solved NLP problem — CV formats vary
enormously and no rule-based extractor handles all of them. This is a
disclosed limitation, not a hidden flaw: the human-in-the-loop review
step (see Chapter 3, Figure 3.2) exists specifically because automatic
extraction is expected to need occasional correction by the candidate
before the profile is published.
"""
import io
import re
from functools import lru_cache

import fitz  # this is pymupdf's import name, not a typo
from docx import Document

from app.services.nlp_service import build_phrase_matcher, find_phrase_matches
from app.data.skill_taxonomy import SKILL_LOOKUP, ALL_SKILLS
from app.data.regional_terms import (
    AFRICAN_INSTITUTIONS, AFRICAN_TECH_PROGRAMMES, REGIONAL_TERMS, all_regional_phrases
)


# ---------------------------------------------------------------------
# Matchers are built once (cached) since the phrase lists are static.
# ---------------------------------------------------------------------

@lru_cache(maxsize=1)
def _skill_matcher():
    return build_phrase_matcher(ALL_SKILLS)


@lru_cache(maxsize=1)
def _regional_matcher():
    return build_phrase_matcher(all_regional_phrases())


# ---------------------------------------------------------------------
# Text extraction from uploaded file bytes
# ---------------------------------------------------------------------

def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extracts plain text from a PDF, DOCX, or TXT file. Raises
    ValueError for unsupported types so the router can return a clean
    400 response instead of a raw exception.
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext == "pdf":
        return _extract_pdf_text(file_bytes)
    elif ext == "docx":
        return _extract_docx_text(file_bytes)
    elif ext == "txt":
        return file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Please upload a PDF, DOCX, or TXT file.")


def _extract_pdf_text(file_bytes: bytes) -> str:
    text_parts = []
    with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
        for page in pdf:
            text_parts.append(page.get_text())
    return "\n".join(text_parts)


def _extract_docx_text(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)


# ---------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------

def extract_skills(text: str) -> list[str]:
    matched = find_phrase_matches(text, _skill_matcher())
    # Normalise to canonical casing from the taxonomy, then dedupe.
    canonical = {SKILL_LOOKUP.get(m.lower(), m) for m in matched}
    return sorted(canonical)


# ---------------------------------------------------------------------
# Regional term detection — the bias-relevant extraction
# ---------------------------------------------------------------------

def detect_regional_terms(text: str) -> dict:
    matched = find_phrase_matches(text, _regional_matcher())

    institutions_lower = {i.lower() for i in AFRICAN_INSTITUTIONS}
    programmes_lower = {p.lower() for p in AFRICAN_TECH_PROGRAMMES}
    terms_lower = {t.lower() for t in REGIONAL_TERMS}

    found_institutions = sorted(m for m in matched if m.lower() in institutions_lower)
    found_programmes = sorted(m for m in matched if m.lower() in programmes_lower)
    found_terms = sorted(m for m in matched if m.lower() in terms_lower)

    return {
        "institutions": found_institutions,
        "tech_programmes": found_programmes,
        "other_terms": found_terms,
        "all_matches": sorted(matched),
    }


# ---------------------------------------------------------------------
# Experience level estimation
# ---------------------------------------------------------------------

_EXPERIENCE_PATTERN = re.compile(
    r"(\d{1,2})\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)", re.IGNORECASE
)


def estimate_experience_level(text: str) -> str:
    matches = _EXPERIENCE_PATTERN.findall(text)
    if not matches:
        return "Not specified"

    years = max(int(m) for m in matches)
    if years < 1:
        return "Entry-level (0-1 yrs)"
    elif years < 3:
        return "Junior (1-3 yrs)"
    elif years < 6:
        return "Mid-level (3-6 yrs)"
    else:
        return "Senior (6+ yrs)"


# ---------------------------------------------------------------------
# Education tier classification
# ---------------------------------------------------------------------

_DEGREE_PATTERN = re.compile(
    r"\b(b\.?sc|b\.?eng|b\.?a|m\.?sc|m\.?eng|m\.?a|ph\.?d|bachelor|master|"
    r"undergraduate|postgraduate|degree)\b",
    re.IGNORECASE,
)


def classify_education_tier(text: str, regional_matches: dict) -> str:
    """
    Priority order when multiple signals are present: Graduate >
    Bootcamp > Self-Taught > Undisclosed. A candidate with both a
    degree and a bootcamp certificate is classified as Graduate here,
    but both facts remain visible in regional_terms and cv_skills —
    this field is a single-value summary tag, not the full picture.
    """
    has_degree_language = bool(_DEGREE_PATTERN.search(text))
    has_institution = bool(regional_matches.get("institutions"))
    has_bootcamp = bool(regional_matches.get("tech_programmes"))

    if has_degree_language or has_institution:
        return "Graduate"
    elif has_bootcamp:
        return "Bootcamp"
    elif len(text.strip()) > 200:
        # Substantial CV content but no formal-education signal detected
        # — treated as self-taught rather than penalised or excluded.
        return "Self-Taught"
    else:
        return "Undisclosed"


# ---------------------------------------------------------------------
# Project extraction (heuristic, section-based)
# ---------------------------------------------------------------------

_PROJECT_HEADER_PATTERN = re.compile(
    r"^\s*(projects?|personal projects?|key projects?|selected projects?)\s*:?\s*$",
    re.IGNORECASE,
)
_SECTION_HEADER_PATTERN = re.compile(
    r"^\s*(experience|education|skills|certifications?|awards?|references?|"
    r"summary|objective|contact)\s*:?\s*$",
    re.IGNORECASE,
)
_BULLET_PATTERN = re.compile(r"^\s*[-*•\u2022]\s*(.+)$")


def extract_projects(text: str) -> list[dict]:
    lines = [line.strip() for line in text.split("\n")]
    projects = []
    in_projects_section = False
    current_project_lines = []

    def flush_current():
        if current_project_lines:
            full_text = " ".join(current_project_lines).strip()
            if full_text:
                title = full_text.split(".")[0][:80].strip()
                if len(title) == 80 and " " in title:
                    title = title.rsplit(" ", 1)[0] + "..."
                projects.append({"title": title, "description": full_text})

    for line in lines:
        if not line:
            continue
        if _PROJECT_HEADER_PATTERN.match(line):
            in_projects_section = True
            continue
        if _SECTION_HEADER_PATTERN.match(line) and in_projects_section:
            flush_current()
            current_project_lines = []
            in_projects_section = False
            continue
        if in_projects_section:
            bullet_match = _BULLET_PATTERN.match(line)
            if bullet_match:
                flush_current()
                current_project_lines = [bullet_match.group(1)]
            else:
                current_project_lines.append(line)

    flush_current()
    return projects


# ---------------------------------------------------------------------
# Main entry point — orchestrates all of the above
# ---------------------------------------------------------------------

def parse_cv(file_bytes: bytes, filename: str) -> dict:
    text = extract_text(file_bytes, filename)

    if len(text.strip()) < 50:
        raise ValueError(
            "Could not extract meaningful text from this file. It may be a "
            "scanned image rather than a text-based document."
        )

    skills = extract_skills(text)
    regional = detect_regional_terms(text)
    experience_level = estimate_experience_level(text)
    education_tier = classify_education_tier(text, regional)
    projects = extract_projects(text)

    return {
        "raw_text": text,
        "raw_text_length": len(text),
        "skills": skills,
        "regional_terms": regional,
        "experience_level": experience_level,
        "education_tier": education_tier,
        "projects": projects,
    }
