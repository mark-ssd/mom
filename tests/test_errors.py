import pytest
from mom.errors import (
    MomError,
    UnsupportedCharError,
    FitError,
    AuthError,
    NotOurRepoError,
    NetworkError,
)


def test_all_errors_inherit_from_mom_error():
    for cls in (UnsupportedCharError, FitError, AuthError, NotOurRepoError, NetworkError):
        assert issubclass(cls, MomError)


def test_unsupported_char_carries_char():
    err = UnsupportedCharError("❤")
    assert err.char == "❤"
    assert "❤" in str(err)


def test_fit_error_carries_numbers():
    err = FitError(required=43, available=14, year=2026)
    assert err.required == 43
    assert err.available == 14
    assert err.year == 2026
    assert "43" in str(err) and "14" in str(err)


def test_auth_error_has_kind():
    err = AuthError(kind="auth_missing", message="No token.")
    assert err.kind == "auth_missing"
    assert str(err) == "No token."
