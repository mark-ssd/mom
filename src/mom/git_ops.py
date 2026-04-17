"""Local git operations: clone, orphan-reset rebuild, force-push."""

from __future__ import annotations
import json
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal
from mom.errors import NotOurRepoError
from mom.layout import Canvas, plan

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


def rebuild(
    *,
    work_dir: Path,
    remote_url: str,
    year: int,
    canvas: Canvas | None,
    action: Literal["upsert", "delete"],
    today: date,
) -> None:
    """Rebuild the repo's main branch deterministically from state, then force-push.

    action="upsert": write canvas.text for `year` into state (overwriting any prior).
    action="delete": remove `year` from state.
    canvas is used only for action="upsert"; for "delete", pass None.
    """
    ensure_local_clone(work_dir, remote_url)
    # Bring current main into the tree if it exists (so refuse_if_not_ours can check).
    try:
        _git(work_dir, "checkout", "main")
    except subprocess.CalledProcessError:
        pass   # branch doesn't exist yet (first run)

    repo_name = remote_url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    refuse_if_not_ours(work_dir, repo_name)

    state = read_state(work_dir)
    drawings = state.setdefault("drawings", {})
    if action == "upsert":
        assert canvas is not None
        drawings[str(year)] = {
            "text": canvas.text,
            "intensity": canvas.intensity,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    else:
        drawings.pop(str(year), None)

    # Regenerate every stored drawing into cells (pure).
    all_cells: list[tuple[date, int]] = []
    for y_str, d in drawings.items():
        c = plan(d["text"], int(y_str), today, d["intensity"])
        if isinstance(c, Canvas):
            all_cells.extend(c.cells)
    # else: skip years that no longer fit (could happen if current-year capacity shrunk)
    all_cells.sort(key=lambda t: t[0])

    # Orphan-reset
    _git(work_dir, "checkout", "--orphan", "_build")
    try:
        _git(work_dir, "rm", "-rf", ".")
    except subprocess.CalledProcessError:
        pass   # empty index is fine
    (work_dir / "README.md").write_text(_README_BODY)
    write_state(work_dir, state)
    _git(work_dir, "add", ".")

    # Initial commit, dated 1 day before earliest drawing (or today if no drawings).
    seed_date = (all_cells[0][0] if all_cells else today)
    seed_env = _date_env(seed_date)
    _git(work_dir, "commit", "-m", "rebuild", env=_merged_env(seed_env))

    # Per-cell empty commits, chronological.
    for d, count in all_cells:
        env = _merged_env(_date_env(d))
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
