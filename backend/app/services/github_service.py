"""
Pipeline 2 (Informal): GitHub analysis.

Given a GitHub username, this module fetches public profile and
repository data via GitHub's REST API and derives:
  - language distribution
  - activity metrics (stars, forks, repo count, recency)
  - learning trajectory (increasing / stable / declining activity)
  - skills inferred from repo descriptions and topics
  - a preliminary G_act score (the GitHub-activity component of the
    Evidence Score formula — final combination happens once all three
    pipelines exist)

Design notes:
- Forked repositories are excluded from activity/skill scoring by
  default. Forking someone else's repo is not evidence of the
  candidate's own work — including it would let anyone inflate their
  profile by forking popular projects without contributing to them.
- README content is NOT fetched per-repo. Each README fetch is a
  separate API call, and with GitHub's unauthenticated rate limit of
  60 requests/hour, a candidate with 30 repos would burn most of the
  hourly quota on one profile link. Repo description + topics fields
  (included free in the repo list response) are used instead as a
  reasonable proxy — a real limitation worth naming in Chapter 5.
- This module has NOT been tested against the live GitHub API in this
  environment (no network access here). Test it yourself against a
  real account before relying on it, and tell me the exact error if
  anything fails — GitHub's API is well-documented and stable, but I
  cannot rule out a field name or edge case I've gotten wrong without
  seeing real response data.
"""
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.services.nlp_service import find_phrase_matches
from app.data.skill_taxonomy import SKILL_LOOKUP, ALL_SKILLS

GITHUB_API_BASE = "https://api.github.com"


class GitHubServiceError(Exception):
    """Raised for any GitHub API failure, carrying the HTTP status
    code the router should respond with — avoids the router having to
    guess the right status from parsing error message text."""
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _auth_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
    return headers


# ---------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------

async def fetch_github_profile(username: str) -> dict:
    url = f"{GITHUB_API_BASE}/users/{username}"
    # Imported per call, not at module scope — see the note in
    # ai_service._call_gemini for why httpx is deferred.
    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=_auth_headers())

    if response.status_code == 404:
        raise GitHubServiceError(f"No GitHub user found with username '{username}'", status_code=404)
    if response.status_code == 403:
        raise GitHubServiceError(
            "GitHub API rate limit exceeded. Add a GITHUB_TOKEN to your .env "
            "file to raise the limit from 60 to 5000 requests/hour.",
            status_code=429,
        )
    response.raise_for_status()
    return response.json()


async def fetch_github_repos(username: str, max_repos: int = 100) -> list[dict]:
    url = f"{GITHUB_API_BASE}/users/{username}/repos"
    params = {"per_page": min(max_repos, 100), "sort": "updated", "type": "owner"}

    import httpx

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, headers=_auth_headers(), params=params)

    if response.status_code == 403:
        raise GitHubServiceError(
            "GitHub API rate limit exceeded. Add a GITHUB_TOKEN to your .env "
            "file to raise the limit from 60 to 5000 requests/hour.",
            status_code=429,
        )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------

def filter_original_repos(repos: list[dict]) -> list[dict]:
    """Excludes forks — see module docstring for why."""
    return [r for r in repos if not r.get("fork", False)]


# ---------------------------------------------------------------------
# Language distribution
# ---------------------------------------------------------------------

def compute_language_distribution(repos: list[dict]) -> dict:
    """
    Returns {language: repo_count} for original (non-fork) repos with
    a detected primary language. Note this counts repos-per-language,
    not lines-of-code-per-language (the latter needs a separate,
    expensive per-repo API call to the /languages endpoint) — coarser,
    but free in terms of API budget.
    """
    counts: dict[str, int] = {}
    for repo in repos:
        lang = repo.get("language")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


# ---------------------------------------------------------------------
# Activity metrics
# ---------------------------------------------------------------------

def compute_activity_metrics(repos: list[dict]) -> dict:
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks_received = sum(r.get("forks_count", 0) for r in repos)
    repo_count = len(repos)

    now = datetime.now(timezone.utc)
    twelve_months_ago = now - timedelta(days=365)
    recently_active = [
        r for r in repos
        if r.get("pushed_at") and _parse_iso(r["pushed_at"]) >= twelve_months_ago
    ]

    return {
        "total_repos": repo_count,
        "total_stars": total_stars,
        "total_forks_received": total_forks_received,
        "repos_active_last_12mo": len(recently_active),
        "distinct_languages": len({r.get("language") for r in repos if r.get("language")}),
    }


def _parse_iso(timestamp_str: str) -> datetime:
    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))


# ---------------------------------------------------------------------
# Learning trajectory
# ---------------------------------------------------------------------

def estimate_learning_trajectory(repos: list[dict]) -> dict:
    """
    Compares repo activity (pushed_at) in the most recent 12 months
    against the 12 months before that, as a coarse proxy for whether
    the candidate's engagement is growing, steady, or tapering off.
    """
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(days=365)
    older_cutoff = now - timedelta(days=730)

    recent_count = 0
    prior_count = 0
    for repo in repos:
        pushed_at = repo.get("pushed_at")
        if not pushed_at:
            continue
        pushed = _parse_iso(pushed_at)
        if pushed >= recent_cutoff:
            recent_count += 1
        elif pushed >= older_cutoff:
            prior_count += 1

    if recent_count == 0 and prior_count == 0:
        trend = "Insufficient data"
    elif prior_count == 0:
        trend = "Increasing"
    elif recent_count > prior_count * 1.2:
        trend = "Increasing"
    elif recent_count < prior_count * 0.8:
        trend = "Declining"
    else:
        trend = "Stable"

    return {
        "trend": trend,
        "repos_active_last_12mo": recent_count,
        "repos_active_prior_12mo": prior_count,
    }


# ---------------------------------------------------------------------
# Skill inference from repo metadata (no README fetch — see docstring)
# ---------------------------------------------------------------------

def extract_skills_from_repos(repos: list[dict]) -> list[str]:
    from app.services.nlp_service import build_phrase_matcher

    text_parts = []
    for repo in repos:
        if repo.get("description"):
            text_parts.append(repo["description"])
        if repo.get("topics"):
            text_parts.append(" ".join(repo["topics"]))
        if repo.get("language"):
            text_parts.append(repo["language"])

    combined_text = " ".join(text_parts)
    if not combined_text.strip():
        return []

    matcher = build_phrase_matcher(ALL_SKILLS)
    matched = find_phrase_matches(combined_text, matcher)
    canonical = {SKILL_LOOKUP.get(m.lower(), m) for m in matched}
    return sorted(canonical)


# ---------------------------------------------------------------------
# G_act score (preliminary — final Evidence Score combination happens
# once all three pipelines exist)
# ---------------------------------------------------------------------

def compute_g_act_score(profile: dict, activity: dict, trajectory: dict) -> float:
    """
    Returns a 0.0-1.0 score. Heuristic and capped/normalised by hand
    rather than statistically fitted — appropriate for a final-year
    project's scope, but worth naming as a limitation: a properly
    validated version would calibrate these caps against a labelled
    dataset rather than hand-chosen thresholds.
    """
    score = 0.0

    # Repo count (up to 0.25): rewards having a body of work, caps at 15 repos
    score += min(activity["total_repos"] / 15, 1.0) * 0.25

    # Stars received (up to 0.20): caps at 50 total stars across repos
    score += min(activity["total_stars"] / 50, 1.0) * 0.20

    # Recency (up to 0.30): rewards active, current engagement over a
    # large dormant repo count
    if activity["total_repos"] > 0:
        recency_ratio = activity["repos_active_last_12mo"] / activity["total_repos"]
        score += recency_ratio * 0.30

    # Language diversity (up to 0.15): caps at 5 distinct languages
    score += min(activity["distinct_languages"] / 5, 1.0) * 0.15

    # Trajectory bonus (up to 0.10)
    if trajectory["trend"] == "Increasing":
        score += 0.10
    elif trajectory["trend"] == "Stable":
        score += 0.05

    return round(min(score, 1.0), 3)


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

async def analyze_github_profile(username: str) -> dict:
    profile = await fetch_github_profile(username)
    all_repos = await fetch_github_repos(username)
    original_repos = filter_original_repos(all_repos)

    languages = compute_language_distribution(original_repos)
    activity = compute_activity_metrics(original_repos)
    trajectory = estimate_learning_trajectory(original_repos)
    skills = extract_skills_from_repos(original_repos)
    g_act_score = compute_g_act_score(profile, activity, trajectory)

    repo_summary = [
        {
            "name": r["name"],
            "description": r.get("description"),
            "language": r.get("language"),
            "stars": r.get("stargazers_count", 0),
            "url": r.get("html_url"),
            "pushed_at": r.get("pushed_at"),
            "created_at": r.get("created_at"),
        }
        for r in sorted(original_repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:20]
    ]

    return {
        "github_username": username,
        "profile_summary": {
            "name": profile.get("name"),
            "bio": profile.get("bio"),
            "public_repos": profile.get("public_repos"),
            "followers": profile.get("followers"),
            "account_created": profile.get("created_at"),
        },
        "repos": repo_summary,
        "languages": languages,
        "activity": activity,
        "learning_trajectory": trajectory,
        "inferred_skills": skills,
        "g_act_score": g_act_score,
    }
