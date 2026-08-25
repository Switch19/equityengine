"""
Curated list of African universities, community tech programmes, and
regional terminology.

This list exists specifically to demonstrate the study's core claim:
that these terms carry real signal about a candidate's background and
training, but are unrecognised by conventional keyword-matching ATS
tools built around Western institution names. Detecting them here is
part of the Evidence Score's contribution to the education_tier and
regional_terms fields, NOT a bonus applied to ranking — detection
itself is the fairness-relevant act, not extra credit for having
attended one of these institutions specifically. A candidate whose CV
matches none of these terms is not penalised; the GitHub and community
pipelines exist precisely to serve candidates with no formal
institution to list at all.

This list is necessarily incomplete — extending it is one of the more
valuable, low-effort improvements you could make if you have time
before your defence.
"""

AFRICAN_INSTITUTIONS = [
    # Nigeria
    "University of Lagos", "University of Ibadan", "University of Nigeria Nsukka",
    "Ahmadu Bello University", "Obafemi Awolowo University", "Covenant University",
    "Delta State University", "University of Benin", "Federal University of Technology Akure",
    "Lagos State University", "University of Port Harcourt", "Nnamdi Azikiwe University",
    "Federal University of Technology Minna", "Babcock University",
    # Kenya
    "University of Nairobi", "Kenyatta University", "Strathmore University",
    "Jomo Kenyatta University of Agriculture and Technology",
    # Ghana
    "University of Ghana", "Kwame Nkrumah University of Science and Technology",
    "Ashesi University",
    # South Africa
    "University of Cape Town", "University of the Witwatersrand", "Stellenbosch University",
    "University of Pretoria", "University of Johannesburg",
    # Others
    "Makerere University", "Cairo University", "University of Nairobi",
    "Addis Ababa University", "University of Dar es Salaam",
]

AFRICAN_TECH_PROGRAMMES = [
    "Andela", "ALX", "ALX Africa", "Genesys Hub", "Decagon", "Semicolon Africa",
    "CcHub", "Co-Creation Hub", "iHub", "Moringa School", "Utiva",
    "AltSchool Africa", "Zuri Innovation Hub", "Google Africa Developer Scholarship",
    "She Code Africa", "GDG (Google Developer Group)",
]

REGIONAL_TERMS = [
    "NYSC", "National Youth Service Corps", "WAEC", "JAMB", "Corps Member",
    "West African Examinations Council", "KCSE", "KCPE", "WASSCE",
    "Corper", "Youth Corper",
]


def all_regional_phrases():
    """Flat list of every phrase to match against, for building the PhraseMatcher."""
    return AFRICAN_INSTITUTIONS + AFRICAN_TECH_PROGRAMMES + REGIONAL_TERMS
