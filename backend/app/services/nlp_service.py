import spacy

nlp = spacy.load("en_core_web_sm")

# Regional term mappings — African tech terms to global equivalents
TERM_MAPPINGS = {
    # Nigerian Universities
    "university of lagos": "University of Lagos (UNILAG) — Top-ranked African University",
    "obafemi awolowo university": "Obafemi Awolowo University — Leading African STEM Institution",
    "university of nigeria nsukka": "University of Nigeria — Premier Research University",
    "covenant university": "Covenant University — Top-Ranked Private African University",
    "ahmadu bello university": "Ahmadu Bello University — Largest African University by Land Mass",

    # Grading Systems
    "first class": "First Class Honours (GPA equivalent: 4.0/4.0)",
    "second class upper": "Second Class Upper Honours (GPA equivalent: 3.5/4.0)",
    "second class lower": "Second Class Lower Honours (GPA equivalent: 3.0/4.0)",
    "distinction": "Distinction — Top Academic Achievement",
    "waec": "West African Senior School Certificate (equivalent to UK A-Levels / US High School Diploma)",
    "jamb": "Joint Admissions and Matriculation Board (National University Entrance Examination)",
    "nysc": "National Youth Service Corps (Mandatory 1-year National Service Program)",

    # Local Tech Terms
    "andela": "Andela — Globally recognized African software engineering talent network",
    "genesys": "Genesys Tech Hub — Leading African technology incubator",
    "semicolon": "Semicolon Africa — Accredited African software engineering bootcamp",
}

def detect_regional_terms(text: str) -> list:
    """Scan text for regional terms and return suggestions."""
    text_lower = text.lower()
    suggestions = []

    for term, global_equivalent in TERM_MAPPINGS.items():
        if term in text_lower:
            suggestions.append({
                "original": term,
                "suggestion": global_equivalent,
                "reason": "This term may have low visibility in global ATS systems"
            })

    return suggestions

def extract_skills(text: str) -> list:
    """Extract technical skills from resume text."""
    tech_skills = [
        "python", "javascript", "typescript", "react", "vue", "angular",
        "node.js", "fastapi", "django", "flask", "express",
        "postgresql", "mysql", "mongodb", "redis",
        "docker", "kubernetes", "aws", "azure", "gcp",
        "git", "github", "linux", "rest api", "graphql",
        "machine learning", "deep learning", "nlp", "tensorflow", "pytorch",
        "html", "css", "tailwind", "bootstrap",
        "java", "c++", "c#", "go", "rust", "php",
        "figma", "sql", "firebase", "supabase"
    ]

    text_lower = text.lower()
    found_skills = []

    for skill in tech_skills:
        if skill in text_lower:
            found_skills.append(skill)

    return found_skills

def extract_entities(text: str) -> dict:
    """Use spaCy NER to extract named entities."""
    doc = nlp(text)
    entities = {
        "organizations": [],
        "locations": [],
        "persons": [],
        "dates": []
    }

    for ent in doc.ents:
        if ent.label_ == "ORG" and ent.text not in entities["organizations"]:
            entities["organizations"].append(ent.text)
        elif ent.label_ == "GPE" and ent.text not in entities["locations"]:
            entities["locations"].append(ent.text)
        elif ent.label_ == "PERSON" and ent.text not in entities["persons"]:
            entities["persons"].append(ent.text)
        elif ent.label_ == "DATE" and ent.text not in entities["dates"]:
            entities["dates"].append(ent.text)

    return entities

def analyze_resume(text: str) -> dict:
    """Full BDIOF Vector 1 analysis pipeline."""
    skills = extract_skills(text)
    suggestions = detect_regional_terms(text)
    entities = extract_entities(text)

    visibility_score = 100
    if len(suggestions) > 0:
        visibility_score -= (len(suggestions) * 10)
    visibility_score = max(visibility_score, 0)

    return {
        "skills_detected": skills,
        "skill_count": len(skills),
        "regional_term_suggestions": suggestions,
        "suggestion_count": len(suggestions),
        "entities": entities,
        "visibility_score": visibility_score,
        "optimization_needed": len(suggestions) > 0
    }