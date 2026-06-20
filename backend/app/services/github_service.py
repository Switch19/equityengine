import requests

def analyze_github_profile(github_url: str) -> dict:
    """
    BDIOF Vector 1 — GitHub Profile Analysis
    Extracts tech stack, languages, and project data
    from a candidate's public GitHub profile.
    """
    try:
        # Extract username from URL
        username = github_url.rstrip('/').split('/')[-1]

        headers = {'Accept': 'application/vnd.github.v3+json'}

        # Get user profile
        user_res = requests.get(
            f"https://api.github.com/users/{username}",
            headers=headers, timeout=10
        )

        if user_res.status_code != 200:
            return {"error": "GitHub profile not found or private"}

        user = user_res.json()

        # Get repositories
        repos_res = requests.get(
            f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
            headers=headers, timeout=10
        )

        repos = repos_res.json() if repos_res.status_code == 200 else []

        # Extract languages
        languages = {}
        for repo in repos:
            if repo.get('language'):
                lang = repo['language'].lower()
                languages[lang] = languages.get(lang, 0) + 1

        top_languages = sorted(languages.keys(), key=lambda x: languages[x], reverse=True)

        # Extract project names and descriptions
        projects = []
        for repo in repos[:5]:
            if not repo.get('fork'):
                projects.append({
                    "name": repo.get('name', ''),
                    "description": repo.get('description', ''),
                    "stars": repo.get('stargazers_count', 0),
                    "language": repo.get('language', '')
                })

        return {
            "username": username,
            "name": user.get('name', username),
            "public_repos": user.get('public_repos', 0),
            "followers": user.get('followers', 0),
            "top_languages": top_languages[:8],
            "projects": projects,
            "github_score": min(100, (user.get('public_repos', 0) * 3) + (user.get('followers', 0) * 2)),
            "profile_url": github_url
        }

    except Exception as e:
        return {"error": f"Failed to analyze GitHub profile: {str(e)}"}