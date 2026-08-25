"""
Pipeline 3 (Community): Stack Overflow reputation, Dev.to articles,
self-reported certifications, and peer endorsements.

Produces a preliminary C_peer score (20% of the Evidence Score) from
whatever community evidence is available. As with G_act (GitHub
pipeline), this is a raw/preliminary signal — final Evidence Score
combination happens once all three pipelines exist, in the Competency
Engine phase.
"""
import math
from datetime import datetime, timezone

import httpx

from app.data.certification_registry import classify_certification_tier

STACKEXCHANGE_API_BASE = "https://api.stackexchange.com/2.3"
DEVTO_API_BASE = "https://dev.to/api"


class CommunityServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------------
# Stack Overflow
# ---------------------------------------------------------------------

async def fetch_stackoverflow_stats(user_id: str) -> dict:
    """
    user_id is Stack Overflow's numeric user ID (visible in their
    profile URL, e.g. stackoverflow.com/users/12345678/name — the
    number, not the display name). The Stack Exchange API is keyed by
    this numeric ID, not username, which is a common point of
    confusion worth flagging to candidates in the frontend form.
    """
    if not user_id.isdigit():
        raise CommunityServiceError(
            "Stack Overflow ID must be numeric — find it in your profile URL "
            "(stackoverflow.com/users/NUMBER/your-name), not your display name.",
            status_code=400,
        )

    url = f"{STACKEXCHANGE_API_BASE}/users/{user_id}"
    params = {"site": "stackoverflow"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)

    if response.status_code == 400:
        raise CommunityServiceError(f"No Stack Overflow user found with ID '{user_id}'", status_code=404)
    response.raise_for_status()
    data = response.json()

    items = data.get("items", [])
    if not items:
        raise CommunityServiceError(f"No Stack Overflow user found with ID '{user_id}'", status_code=404)

    user = items[0]
    return {
        "user_id": user_id,
        "display_name": user.get("display_name"),
        "reputation": user.get("reputation", 0),
        "badge_counts": user.get("badge_counts", {"bronze": 0, "silver": 0, "gold": 0}),
        "profile_url": user.get("link"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------
# Dev.to
# ---------------------------------------------------------------------

async def fetch_devto_stats(username: str) -> dict:
    url = f"{DEVTO_API_BASE}/articles"
    params = {"username": username}

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)

    response.raise_for_status()
    articles = response.json()

    if not isinstance(articles, list):
        raise CommunityServiceError(f"Could not retrieve Dev.to articles for '{username}'", status_code=404)

    total_reactions = sum(a.get("positive_reactions_count", 0) for a in articles)
    total_comments = sum(a.get("comments_count", 0) for a in articles)

    return {
        "username": username,
        "article_count": len(articles),
        "total_reactions": total_reactions,
        "total_comments": total_comments,
        "recent_titles": [a.get("title") for a in articles[:5]],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------
# Certifications (self-reported, classified against the tier registry)
# ---------------------------------------------------------------------

def classify_certification(name: str, issuer: str = "", date_earned: str = "") -> dict:
    combined_text = f"{name} {issuer}"
    tier = classify_certification_tier(combined_text)
    return {
        "name": name,
        "issuer": issuer,
        "date_earned": date_earned,
        "tier": tier,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------
# Peer endorsements
# ---------------------------------------------------------------------

def add_endorsement(existing_endorsements: list, endorser_id: str, skill: str) -> list:
    """
    Appends a new endorsement, guarding against duplicates (same
    endorser, same skill) at the data layer as a second line of
    defence — the router also checks this before calling, but
    keeping the check here too means this function is safe to call
    directly (e.g. from a future seed script) without relying on the
    router's validation.

    Note on anonymity: endorser_id IS stored here, because duplicate
    prevention and abuse detection require it. It must be stripped out
    before any recruiter-facing endpoint returns this data — recruiters
    should only ever see an aggregate endorsement count per skill, per
    the "anonymous to recruiters" requirement. That stripping happens
    in the recruiter-facing dossier endpoint (Competency Engine phase),
    not here.
    """
    existing_endorsements = existing_endorsements or []

    already_endorsed = any(
        e["endorser_id"] == endorser_id and e["skill"].lower() == skill.lower()
        for e in existing_endorsements
    )
    if already_endorsed:
        raise CommunityServiceError(
            f"You have already endorsed this candidate for '{skill}'.", status_code=400
        )

    existing_endorsements.append({
        "skill": skill,
        "endorser_id": endorser_id,
        "endorsed_at": datetime.now(timezone.utc).isoformat(),
    })
    return existing_endorsements


def summarize_endorsements_for_owner(endorsements: list) -> dict:
    """
    Candidate-facing summary (the candidate CAN see who endorsed
    them — anonymity is specifically towards recruiters, not the
    candidate themselves). Groups endorsement counts per skill.
    """
    endorsements = endorsements or []
    by_skill: dict[str, int] = {}
    for e in endorsements:
        by_skill[e["skill"]] = by_skill.get(e["skill"], 0) + 1
    return {"total_endorsements": len(endorsements), "by_skill": by_skill}


# ---------------------------------------------------------------------
# C_peer score (preliminary)
# ---------------------------------------------------------------------

def compute_c_peer_score(certifications: list, stackoverflow_data: dict | None, peer_endorsements: list) -> float:
    """
    Returns a 0.0-1.0 score combining all three community evidence
    types. Hand-calibrated caps, same limitation noted in the GitHub
    pipeline's G_act scoring — a properly validated version would fit
    these against labelled data rather than choosing thresholds by hand.
    """
    score = 0.0
    certifications = certifications or []
    peer_endorsements = peer_endorsements or []

    # Certifications (up to 0.40): Tier 1 worth more than Tier 2, both
    # worth more than an unrecognised entry, capped at 3 certifications
    # counted so a long list doesn't dominate the score.
    cert_points = 0.0
    for cert in certifications[:3]:
        tier = cert.get("tier", 0)
        if tier == 1:
            cert_points += 0.15
        elif tier == 2:
            cert_points += 0.08
        else:
            cert_points += 0.03
    score += min(cert_points, 0.40)

    # Stack Overflow reputation (up to 0.35): log-scaled since
    # reputation is extremely right-skewed (most users: single/double
    # digits; top users: hundreds of thousands) — a linear scale would
    # make the score meaningless for the vast majority of candidates.
    if stackoverflow_data:
        reputation = stackoverflow_data.get("reputation", 0)
        if reputation > 0:
            # log10(reputation) of 4 (10,000 rep) maps to the full 0.35
            so_score = min(math.log10(reputation + 1) / 4, 1.0) * 0.35
            score += so_score

    # Peer endorsements (up to 0.25): caps at 10 endorsements
    score += min(len(peer_endorsements) / 10, 1.0) * 0.25

    return round(min(score, 1.0), 3)
