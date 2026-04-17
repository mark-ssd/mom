"""End-to-end test against a real GitHub sandbox account.

Gated behind `@pytest.mark.live`. Not run in CI. To run locally:

    export MOM_E2E_TOKEN=ghp_...
    export MOM_E2E_USER=<sandbox-login>
    export MOM_E2E_REPO=mom-canvas-sandbox
    pytest tests/test_e2e.py -m live -v

The test draws "HI" on year 2022 and then cleans it.
"""

import os
import pytest
from typer.testing import CliRunner
from mom.cli import app

runner = CliRunner()
pytestmark = pytest.mark.live


@pytest.fixture
def env():
    tok = os.environ.get("MOM_E2E_TOKEN")
    user = os.environ.get("MOM_E2E_USER")
    repo = os.environ.get("MOM_E2E_REPO", "mom-canvas-sandbox")
    if not tok or not user:
        pytest.skip("MOM_E2E_TOKEN and MOM_E2E_USER required")
    return tok, user, repo


def test_draw_and_clean_lifecycle(env):
    tok, user, repo = env
    # Draw.
    result = runner.invoke(app, [
        "draw", "HI", "--year", "2022", "--repo", repo,
        "--yes", "--format", "json", "--token", tok,
    ])
    assert result.exit_code == 0, result.output
    # Clean.
    result = runner.invoke(app, [
        "clean", "--year", "2022", "--repo", repo,
        "--yes", "--format", "json", "--token", tok,
    ])
    assert result.exit_code == 0, result.output
