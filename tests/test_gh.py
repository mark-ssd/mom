import pytest
import responses
from mom.gh import verify_token, verify_email, ensure_repo
from mom.errors import AuthError, NetworkError


API = "https://api.github.com"


@responses.activate
def test_verify_token_ok():
    responses.add(
        responses.GET, f"{API}/user",
        json={"login": "mark-ssd"}, status=200,
        headers={"X-OAuth-Scopes": "repo, read:user"},
    )
    user = verify_token("ghp_xyz")
    assert user == "mark-ssd"


@responses.activate
def test_verify_token_401_raises_auth_invalid():
    responses.add(responses.GET, f"{API}/user", json={}, status=401)
    with pytest.raises(AuthError) as excinfo:
        verify_token("bad")
    assert excinfo.value.kind == "auth_invalid"


@responses.activate
def test_verify_token_missing_repo_scope_raises():
    responses.add(
        responses.GET, f"{API}/user",
        json={"login": "x"}, status=200,
        headers={"X-OAuth-Scopes": "read:user"},
    )
    with pytest.raises(AuthError) as excinfo:
        verify_token("ghp_xyz")
    assert excinfo.value.kind == "auth_scope"


@responses.activate
def test_verify_email_match():
    responses.add(
        responses.GET, f"{API}/user/emails",
        json=[{"email": "a@b.com", "verified": True, "primary": True}],
        status=200,
    )
    # No exception -> pass.
    verify_email("ghp_xyz", "a@b.com")


@responses.activate
def test_verify_email_mismatch_raises():
    responses.add(
        responses.GET, f"{API}/user/emails",
        json=[{"email": "a@b.com", "verified": True, "primary": True}],
        status=200,
    )
    with pytest.raises(AuthError) as excinfo:
        verify_email("ghp_xyz", "other@x.com")
    assert excinfo.value.kind == "email_mismatch"


@responses.activate
def test_ensure_repo_existing_returns_url():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={"clone_url": "https://github.com/mark-ssd/mom-canvas.git",
              "html_url": "https://github.com/mark-ssd/mom-canvas"},
        status=200,
    )
    clone, html = ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
    assert clone == "https://github.com/mark-ssd/mom-canvas.git"
    assert html == "https://github.com/mark-ssd/mom-canvas"


@responses.activate
def test_ensure_repo_404_triggers_create():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={"message": "Not Found"}, status=404,
    )
    responses.add(
        responses.POST, f"{API}/user/repos",
        json={"clone_url": "https://github.com/mark-ssd/mom-canvas.git",
              "html_url": "https://github.com/mark-ssd/mom-canvas"},
        status=201,
    )
    clone, html = ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
    assert "mom-canvas.git" in clone


@responses.activate
def test_ensure_repo_server_error_raises_network():
    responses.add(
        responses.GET, f"{API}/repos/mark-ssd/mom-canvas",
        json={}, status=500,
    )
    with pytest.raises(NetworkError):
        ensure_repo("ghp_xyz", "mark-ssd", "mom-canvas")
