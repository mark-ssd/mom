"""Local git operations: clone, orphan-reset rebuild, force-push."""

from __future__ import annotations
import json
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from mom.errors import AuthError, NotOurRepoError
from mom.layout import Canvas, plan, window_from_state

_STATE_FILE = ".mom-state.json"
_README_BODY = (
    "# mom-canvas\n\n"
    "This repository is managed by [mom](https://github.com/mark-ssd/mom).\n\n"
    "Its commits form pixel text on the owner's GitHub contribution graph.\n"
    "Do not push to this repository manually -- it will be rewritten on the next run.\n"
)


def _git(cwd: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True, env=env,
    )


def ensure_local_clone(work_dir: Path, remote_url: str) -> None:
    """Clone `remote_url` to `work_dir` if absent; otherwise fetch."""
    if (work_dir / ".git").is_dir():
        _git(work_dir, "fetch", "origin")
        return
    work_dir.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", remote_url, str(work_dir)],
        capture_output=True, text=True, check=True,
    )


def read_state(work_dir: Path) -> dict:
    p = work_dir / _STATE_FILE
    if not p.exists():
        return {"managed_by": "mom", "version": 1, "drawings": {}}
    return json.loads(p.read_text())


def write_state(work_dir: Path, state: dict) -> None:
    (work_dir / _STATE_FILE).write_text(json.dumps(state, indent=2, sort_keys=True))


def refuse_if_not_ours(work_dir: Path, repo_name: str) -> None:
    """Raise NotOurRepoError unless the dir has a well-formed .mom-state.json.

    Empty directories (fresh clone with no commits) are allowed -- the tool owns them
    from the first run. The refuse check only triggers if the dir is non-empty AND
    lacks our marker (i.e., someone else's repo).
    """
    state_file = work_dir / _STATE_FILE
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            if state.get("managed_by") == "mom":
                return
        except json.JSONDecodeError:
            pass
        raise NotOurRepoError(repo_name)
    # No state file: is the dir otherwise empty (aside from .git)?
    tracked = list(p for p in work_dir.iterdir() if p.name != ".git")
    if tracked:
        raise NotOurRepoError(repo_name)


def update_state(state: dict, canvas: Canvas | None,
                 action: Literal["upsert", "delete"], state_key: str) -> dict:
    drawings = state.setdefault("drawings", {})
    if action == "upsert":
        assert canvas is not None
        if canvas.window.mode == "trailing":
            # Only one trailing drawing at a time. Purge any existing trailing
            # entries (including legacy per-date keys like `trailing-2026-04-16`).
            for k in list(drawings):
                entry = drawings[k]
                if entry.get("mode") == "trailing" or k.startswith("trailing"):
                    del drawings[k]
        drawings[canvas.window.state_key] = {
            "mode": canvas.window.mode,
            "ref": canvas.window.ref,
            "text": canvas.text,
            "intensity": canvas.intensity,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        drawings.pop(state_key, None)
    return state


def read_existing_state(work_dir: Path, remote_url: str | None, repo_name: str) -> dict:
    """Clone the remote (if it exists), verify ownership, return state.
    Returns a fresh empty state if no remote yet."""
    if remote_url is None:
        return {"managed_by": "mom", "version": 1, "drawings": {}}
    ensure_local_clone(work_dir, remote_url)
    try:
        _git(work_dir, "checkout", "main")
    except subprocess.CalledProcessError:
        pass
    refuse_if_not_ours(work_dir, repo_name)
    return read_state(work_dir)


def _cells_from_state(state: dict, today: date) -> list[tuple[date, int]]:
    all_cells: list[tuple[date, int]] = []
    for _, d in state.get("drawings", {}).items():
        window = window_from_state(d["mode"], d["ref"], today)
        c = plan(d["text"], window, d["intensity"])
        if isinstance(c, Canvas):
            all_cells.extend(c.cells)
    all_cells.sort(key=lambda t: t[0])
    return all_cells


def build_and_push(
    *,
    work_dir: Path,
    remote_url: str,
    state: dict,
    today: date,
    author_name: str,
    author_email: str,
) -> None:
    """Initialise a fresh local repo from state and push to an empty remote.

    Use this after delete+create to avoid leaving force-push orphans on GitHub.
    """
    import shutil
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    _git(work_dir, "init", "-b", "main")
    _git(work_dir, "remote", "add", "origin", remote_url)

    (work_dir / "README.md").write_text(_README_BODY)
    write_state(work_dir, state)
    _git(work_dir, "add", ".")

    author_env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    }

    all_cells = _cells_from_state(state, today)
    seed_date = (all_cells[0][0] if all_cells else today)
    _git(work_dir, "commit", "-m", "rebuild",
         env=_merged_env({**_date_env(seed_date), **author_env}))

    for d, count in all_cells:
        env = _merged_env({**_date_env(d), **author_env})
        for n in range(count):
            _git(work_dir, "commit", "--allow-empty",
                 "-m", f"canvas {d.isoformat()} #{n + 1}", env=env)

    _git(work_dir, "push", "-u", "origin", "main")


def rebuild(
    *,
    work_dir: Path,
    remote_url: str,
    canvas: Canvas | None,
    action: Literal["upsert", "delete"],
    state_key: str,
    today: date,
    author_name: str,
    author_email: str,
) -> None:
    """Legacy force-push rebuild (fallback when delete_repo scope is missing).

    Force-pushes an orphan history onto `main`. Previously pushed commits
    are unreachable from refs but may linger in GitHub's contribution index
    for ~90 days, inflating counts. Prefer the delete-and-recreate flow
    in the CLI when the token has `delete_repo` scope.
    """
    ensure_local_clone(work_dir, remote_url)
    try:
        _git(work_dir, "checkout", "main")
    except subprocess.CalledProcessError:
        pass

    repo_name = remote_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    refuse_if_not_ours(work_dir, repo_name)

    state = update_state(read_state(work_dir), canvas, action, state_key)
    all_cells = _cells_from_state(state, today)

    # Orphan-reset
    _git(work_dir, "checkout", "--orphan", "_build")
    try:
        _git(work_dir, "rm", "-rf", ".")
    except subprocess.CalledProcessError:
        pass   # empty index is fine
    (work_dir / "README.md").write_text(_README_BODY)
    write_state(work_dir, state)
    _git(work_dir, "add", ".")

    author_env = {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": author_email,
    }

    seed_date = (all_cells[0][0] if all_cells else today)
    _git(work_dir, "commit", "-m", "rebuild",
         env=_merged_env({**_date_env(seed_date), **author_env}))

    for d, count in all_cells:
        env = _merged_env({**_date_env(d), **author_env})
        for n in range(count):
            _git(work_dir, "commit", "--allow-empty",
                 "-m", f"canvas {d.isoformat()} #{n + 1}", env=env)

    # Promote _build to main and force-push.
    try:
        _git(work_dir, "branch", "-D", "main")
    except subprocess.CalledProcessError:
        pass
    _git(work_dir, "branch", "-M", "_build", "main")
    _git(work_dir, "push", "--force", "origin", "main")


def _date_env(d: date) -> dict[str, str]:
    iso = f"{d.isoformat()}T12:00:00+0000"
    return {"GIT_AUTHOR_DATE": iso, "GIT_COMMITTER_DATE": iso}


def _merged_env(extra: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.update(extra)
    return env
