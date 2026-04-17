import json
import subprocess
import pytest
from typer.testing import CliRunner
from mom.cli import app

runner = CliRunner()


@pytest.fixture
def tmp_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_draw_dry_run_json_fit(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HI", "--year", "2024", "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "preview"
    assert data["fit"]["ok"] is True
    assert data["fit"]["required_cols"] == 7
    assert data["commits"]["total"] == 11 * 20 + 9 * 20   # H(11)+I(9) pixels * 20 = 400
    assert "preview_ascii" in data


def test_draw_dry_run_fit_fail_exits_3(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HELLO WORLD", "--year", "2026",
        "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 3
    data = json.loads(result.output)
    assert data["status"] == "error"
    assert data["error"]["kind"] == "fit_fail"


def test_draw_dry_run_unsupported_char_exits_2(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake_for_dry_run")
    result = runner.invoke(app, [
        "draw", "HI\u2764", "--year", "2024",
        "--dry-run", "--format", "json",
    ])
    assert result.exit_code == 2
    data = json.loads(result.output)
    assert data["error"]["kind"] == "unsupported_char"


def test_preview_is_alias_for_dry_run(tmp_xdg, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake")
    r1 = runner.invoke(app, ["preview", "HI", "--year", "2024", "--format", "json"])
    r2 = runner.invoke(app, ["draw", "HI", "--year", "2024", "--dry-run", "--format", "json"])
    assert r1.exit_code == 0
    d1, d2 = json.loads(r1.output), json.loads(r2.output)
    assert d1["fit"] == d2["fit"]
    assert d1["preview_ascii"] == d2["preview_ascii"]


def test_config_set_token_persists(tmp_xdg):
    result = runner.invoke(app, ["config", "set-token", "ghp_new"])
    assert result.exit_code == 0
    result2 = runner.invoke(app, ["config", "show"])
    assert "ghp_new" not in result2.output   # redacted
    assert "(set)" in result2.output or "***" in result2.output


def test_config_check_auth_missing(tmp_xdg, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Mock gh CLI to fail.
    def fake_run(cmd, *a, **kw):
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="not logged in")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = runner.invoke(app, ["config", "check", "--format", "json"])
    assert result.exit_code == 4
    data = json.loads(result.output)
    assert data["error"]["kind"] == "auth_missing"
