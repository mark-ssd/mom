import json
import os
import subprocess
from pathlib import Path
import pytest
from mom.config import Config, load, save, resolve_token
from mom.errors import AuthError


@pytest.fixture
def tmp_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    return tmp_path


def test_save_and_load_round_trip(tmp_xdg):
    cfg = Config(repo="mom-canvas", github_user="mark-ssd", token="ghp_xyz")
    save(cfg)
    loaded = load()
    assert loaded == cfg


def test_save_sets_chmod_600(tmp_xdg):
    cfg = Config(repo="x", github_user="y", token="ghp_xyz")
    save(cfg)
    path = tmp_xdg / "mom" / "config.json"
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600


def test_load_missing_file_returns_default(tmp_xdg):
    cfg = load()
    assert cfg.repo == "mom-canvas"
    assert cfg.github_user == ""
    assert cfg.token is None


def test_resolve_token_explicit_beats_all(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit="flag_token") == "flag_token"


def test_resolve_token_env_beats_config(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env_token")
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit=None) == "env_token"


def test_resolve_token_config_when_no_env(tmp_xdg):
    save(Config(repo="x", github_user="y", token="config_token"))
    assert resolve_token(explicit=None) == "config_token"


def test_resolve_token_falls_back_to_gh_cli(tmp_xdg, monkeypatch):
    # Mock subprocess to simulate `gh auth token`.
    def fake_run(cmd, *a, **kw):
        if list(cmd[:3]) == ["gh", "auth", "token"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gh_token\n", stderr="")
        raise FileNotFoundError
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert resolve_token(explicit=None) == "gh_token"


def test_resolve_token_raises_when_nothing_works(tmp_xdg, monkeypatch):
    def fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")
    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(AuthError) as excinfo:
        resolve_token(explicit=None)
    assert excinfo.value.kind == "auth_missing"
