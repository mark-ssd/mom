import json
import subprocess
from datetime import date
from pathlib import Path
import pytest
from mom.git_ops import (
    ensure_local_clone,
    read_state,
    write_state,
    refuse_if_not_ours,
    rebuild,
)
from mom.layout import plan
from mom.errors import NotOurRepoError


def _run(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


@pytest.fixture
def bare_origin(tmp_path):
    """Create a bare repo to act as 'origin'."""
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    return origin


@pytest.fixture
def author_env(monkeypatch):
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Mark SSD")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "aveyurov@gmail.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Mark SSD")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "aveyurov@gmail.com")


def test_ensure_local_clone_creates_dir(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    ensure_local_clone(work, f"file://{bare_origin}")
    assert (work / ".git").is_dir()


def test_read_state_missing_returns_default(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    ensure_local_clone(work, f"file://{bare_origin}")
    state = read_state(work)
    assert state == {"managed_by": "mom", "version": 1, "drawings": {}}


def test_refuse_if_not_ours_raises_when_file_missing(tmp_path):
    # Dir exists but no .mom-state.json -> should raise.
    d = tmp_path / "not_ours"
    d.mkdir()
    (d / "random.txt").write_text("not ours")
    with pytest.raises(NotOurRepoError):
        refuse_if_not_ours(d, "somename")


def test_refuse_if_not_ours_raises_on_bad_marker(tmp_path):
    d = tmp_path / "fake"
    d.mkdir()
    (d / ".mom-state.json").write_text(json.dumps({"managed_by": "someone_else"}))
    with pytest.raises(NotOurRepoError):
        refuse_if_not_ours(d, "fake")


def test_refuse_if_not_ours_passes_on_good_marker(tmp_path):
    d = tmp_path / "good"
    d.mkdir()
    (d / ".mom-state.json").write_text(json.dumps({"managed_by": "mom", "version": 1}))
    refuse_if_not_ours(d, "good")   # no raise


def test_rebuild_creates_expected_commits(tmp_path, bare_origin, author_env):
    work = tmp_path / "work"
    today = date(2026, 4, 16)
    canvas = plan("A", year=2024, today=today, intensity=1)  # intensity 1 -> 5 commits/cell
    rebuild(
        work_dir=work,
        remote_url=f"file://{bare_origin}",
        year=2024,
        canvas=canvas,
        action="upsert",
        today=today,
    )
    # A has 10 on-pixels (1+2+3+2+2) x 5 commits + 1 initial "rebuild" commit = 51.
    log = subprocess.run(
        ["git", "-C", str(work), "log", "--format=%H", "main"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert len(log) == 10 * 5 + 1


def test_rebuild_refuses_repo_missing_state(tmp_path, bare_origin, author_env):
    """When the remote has commits but no .mom-state.json, rebuild refuses."""
    # Put a random file in the remote.
    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(["git", "-C", str(seed), "init", "-b", "main"], check=True)
    (seed / "README.md").write_text("not ours")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-m", "seed"], check=True)
    subprocess.run(["git", "-C", str(seed), "push", f"file://{bare_origin}", "main"], check=True)

    work = tmp_path / "work"
    today = date(2026, 4, 16)
    canvas = plan("A", year=2024, today=today, intensity=1)
    with pytest.raises(NotOurRepoError):
        rebuild(
            work_dir=work,
            remote_url=f"file://{bare_origin}",
            year=2024,
            canvas=canvas,
            action="upsert",
            today=today,
        )
