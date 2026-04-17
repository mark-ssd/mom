"""Config file + auth resolution."""

from __future__ import annotations
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from mom.errors import AuthError


@dataclass
class Config:
    repo: str = "mom-canvas"
    github_user: str = ""
    token: str | None = None


def _config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg) / "mom" / "config.json"


def load() -> Config:
    p = _config_path()
    if not p.exists():
        return Config()
    data = json.loads(p.read_text())
    return Config(
        repo=data.get("repo", "mom-canvas"),
        github_user=data.get("github_user", ""),
        token=data.get("token"),
    )


def save(cfg: Config) -> None:
    p = _config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(cfg), indent=2))
    os.chmod(p, 0o600)


def resolve_token(explicit: str | None) -> str:
    """Resolve a GitHub token. Precedence (highest first):

    1. --token flag (explicit override for any call site)
    2. gh CLI session (primary; `gh auth token`)
    3. GITHUB_TOKEN env var (useful in CI / scripted environments)
    4. Config file PAT (mom config set-token ...)

    Raises AuthError(kind="auth_missing") if nothing is available.
    """
    if explicit:
        return explicit
    try:
        res = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, check=False
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except FileNotFoundError:
        pass
    env_tok = os.environ.get("GITHUB_TOKEN")
    if env_tok:
        return env_tok
    cfg = load()
    if cfg.token:
        return cfg.token
    raise AuthError(
        kind="auth_missing",
        message=(
            "No GitHub authentication found. Recommended: `gh auth login "
            "-s repo -s delete_repo`. Alternatives: set GITHUB_TOKEN, "
            "pass --token, or run `mom config set-token <PAT>`."
        ),
    )
