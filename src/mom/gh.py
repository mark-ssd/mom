"""GitHub REST API client."""

from __future__ import annotations
import requests
from mom.errors import AuthError, NetworkError

_API = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def verify_token(token: str) -> dict:
    """Verify the token and return {"login": str, "id": int}. Checks `repo` scope.
    Raises AuthError(kind="auth_invalid"|"auth_scope") or NetworkError.
    """
    try:
        r = requests.get(f"{_API}/user", headers=_headers(token), timeout=10)
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e

    if r.status_code == 401:
        raise AuthError(
            "auth_invalid",
            "PAT rejected (401). Regenerate at github.com/settings/tokens with 'repo' scope.",
        )
    if r.status_code >= 500:
        raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    scopes_hdr = r.headers.get("X-OAuth-Scopes", "")
    scopes = {s.strip() for s in scopes_hdr.split(",") if s.strip()}
    if "repo" not in scopes and "public_repo" not in scopes:
        raise AuthError(
            "auth_scope",
            "Token lacks 'repo' scope. Re-issue with that scope checked.",
        )
    data = r.json()
    return {"login": data["login"], "id": data["id"]}


def noreply_email(user_id: int, login: str) -> str:
    """GitHub's always-recognized-as-yours email.

    Commits authored with this address count toward the contribution graph
    without needing the `user:email` scope or any specific verified email.
    """
    return f"{user_id}+{login}@users.noreply.github.com"


def verify_email(token: str, git_email: str) -> str | None:
    """Verify that git_email is one of the user's verified GitHub emails.

    Returns None on match or when the check can't run (token lacks `user:email`
    scope -- /user/emails returns 403/404 in that case). Returns a warning
    string when the check was skipped so the caller can surface it.
    Raises AuthError(kind="email_mismatch") on a definitive mismatch.
    """
    try:
        r = requests.get(f"{_API}/user/emails", headers=_headers(token), timeout=10)
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e

    if r.status_code in (403, 404):
        return (
            f"skipped email verification: token lacks `user:email` scope "
            f"(add it at github.com/settings/tokens if you want commits to be "
            f"verified against your GitHub-verified emails)"
        )
    if r.status_code >= 500:
        raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
    r.raise_for_status()

    verified = {e["email"].lower() for e in r.json() if e.get("verified")}
    if git_email.lower() not in verified:
        raise AuthError(
            "email_mismatch",
            f"git config user.email '{git_email}' isn't on your verified GitHub emails -- "
            f"commits won't count. Fix with `git config user.email <verified>` and retry.",
        )
    return None


def ensure_repo(token: str, owner: str, name: str) -> tuple[str, str]:
    """Return (clone_url, html_url). Create the repo if it doesn't exist."""
    try:
        r = requests.get(
            f"{_API}/repos/{owner}/{name}", headers=_headers(token), timeout=10
        )
    except requests.RequestException as e:
        raise NetworkError(str(e)) from e

    if r.status_code == 200:
        data = r.json()
        return data["clone_url"], data["html_url"]
    if r.status_code == 404:
        try:
            cr = requests.post(
                f"{_API}/user/repos",
                headers=_headers(token),
                json={
                    "name": name,
                    "private": False,
                    "auto_init": False,
                    "description": "Managed by mom -- pixel text on my contribution graph.",
                },
                timeout=10,
            )
        except requests.RequestException as e:
            raise NetworkError(str(e)) from e
        if cr.status_code not in (201, 422):
            raise NetworkError(f"repo create failed ({cr.status_code}): {cr.text[:200]}")
        data = cr.json()
        return data["clone_url"], data["html_url"]

    raise NetworkError(f"GitHub API {r.status_code}: {r.text[:200]}")
