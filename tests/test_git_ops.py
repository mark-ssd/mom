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
from mom.layout import plan, calendar_window, trailing_window
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
    w = calendar_window(2024, today)
    canvas = plan("A", w, intensity=1)  # intensity 1 -> 5 commits/cell
    rebuild(
        work_dir=work,
        remote_url=f"file://{bare_origin}",
        canvas=canvas,
        action="upsert",
        state_key=canvas.window.state_key,
        today=today,
        author_name="Test User",
        author_email="12345+test@users.noreply.github.com",
    )
    # A has 10 on-pixels (1+2+3+2+2) x 5 commits + 1 initial "rebuild" commit = 51.
    log = subprocess.run(
        ["git", "-C", str(work), "log", "--format=%H", "main"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert len(log) == 10 * 5 + 1


def test_rebuild_trailing_window_creates_cross_year_commits(tmp_path, bare_origin, author_env):
    """Trailing drawings span 2 calendar years; commits should land in both."""
    work = tmp_path / "work"
    today = date(2026, 4, 16)
    w = trailing_window(today)
    canvas = plan("SSD TECH", w, intensity=1)
    rebuild(
        work_dir=work,
        remote_url=f"file://{bare_origin}",
        canvas=canvas,
        action="upsert",
        state_key=canvas.window.state_key,
        today=today,
        author_name="Test User",
        author_email="12345+test@users.noreply.github.com",
    )
    # Verify state file contains mode=trailing and ref=today under the fixed key.
    import json
    state = json.loads((work / ".mom-state.json").read_text())
    assert "trailing" in state["drawings"]
    d = state["drawings"]["trailing"]
    assert d["mode"] == "trailing"
    assert d["ref"] == "2026-04-16"
    assert d["text"] == "SSD TECH"


def test_update_state_trailing_replaces_stale_entries():
    """A new trailing upsert should purge any legacy per-date trailing keys."""
    from mom.git_ops import update_state
    today = date(2026, 4, 17)
    w = trailing_window(today)
    canvas = plan("HI", w, intensity=1)
    state = {
        "managed_by": "mom", "version": 1,
        "drawings": {
            "trailing-2026-04-16": {"mode": "trailing", "ref": "2026-04-16",
                                    "text": "OLD", "intensity": 4,
                                    "updated_at": "2026-04-16T00:00:00Z"},
            "trailing-2026-04-15": {"mode": "trailing", "ref": "2026-04-15",
                                    "text": "OLDER", "intensity": 4,
                                    "updated_at": "2026-04-15T00:00:00Z"},
            "calendar-2024": {"mode": "calendar", "ref": "2024",
                              "text": "KEEP", "intensity": 4,
                              "updated_at": "2024-01-01T00:00:00Z"},
        },
    }
    out = update_state(state, canvas, "upsert", canvas.window.state_key)
    # All trailing-* entries and the legacy keys should be gone; only one
    # "trailing" entry remains. Calendar entry untouched.
    assert set(out["drawings"].keys()) == {"trailing", "calendar-2024"}
    assert out["drawings"]["trailing"]["text"] == "HI"
    assert out["drawings"]["calendar-2024"]["text"] == "KEEP"


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
    w = calendar_window(2024, today)
    canvas = plan("A", w, intensity=1)
    with pytest.raises(NotOurRepoError):
        rebuild(
            work_dir=work,
            remote_url=f"file://{bare_origin}",
            canvas=canvas,
            action="upsert",
            state_key=canvas.window.state_key,
            today=today,
            author_name="Test User",
            author_email="12345+test@users.noreply.github.com",
        )
