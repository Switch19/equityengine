"""
Recognised certifications and community fellowships, with tiers.

The core fairness decision in this file: Tier 1 explicitly includes
BOTH formal cloud-platform certifications (AWS, Google, Microsoft)
AND African community tech fellowships (Andela, ALX, Genesys Hub,
Decagon). This is a deliberate design choice, not an oversight — the
whole thesis of this project is that community-based training
represents genuine, verifiable competency, not a lesser substitute for
formal credentials (see Chapter 2, Section 2.3.7, Atiase et al., 2020).
Putting them in separate tiers would quietly reproduce the exact
credential hierarchy this system exists to dismantle.

Matching is substring-based against what the candidate types in
(free text), not a fixed dropdown — candidates should be able to enter
certifications this registry doesn't recognise without being blocked;
unrecognised entries are simply stored without a tier bonus, not
rejected. An unrecognised certification is a registry gap, not
evidence the candidate lacks a real credential.
"""

TIER_1_CERTIFICATIONS = [
    # Cloud / platform certifications
    "aws certified", "aws solutions architect", "aws developer associate",
    "google cloud certified", "google cloud professional", "gcp certified",
    "microsoft certified", "azure fundamentals", "azure developer", "azure solutions architect",
    # African community tech fellowships — deliberately Tier 1, see module docstring
    "andela", "alx", "alx africa", "genesys hub", "decagon", "semicolon africa",
]

TIER_2_CERTIFICATIONS = [
    "coursera", "udacity", "freecodecamp", "edx", "meta certified",
    "cisco certified", "comptia", "oracle certified",
]


def classify_certification_tier(certification_text: str) -> int:
    """
    Returns 1, 2, or 0 (unrecognised — still stored, no tier bonus).
    Matches on substring, case-insensitive, so "AWS Certified Solutions
    Architect - Associate (2024)" matches "aws certified".
    """
    text_lower = certification_text.lower()
    if any(term in text_lower for term in TIER_1_CERTIFICATIONS):
        return 1
    if any(term in text_lower for term in TIER_2_CERTIFICATIONS):
        return 2
    return 0
