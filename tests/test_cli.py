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
