from unittest.mock import Mock, patch

import pytest

from core.v2_runtime.host_auth_adapter import (
    V2HostAuthenticationError,
    authenticate,
    build_host_authentication,
    current_session,
    logout,
)


def test_build_host_authentication_requires_v2(monkeypatch):
    monkeypatch.setenv("PHOENIX_CORE_V2_ENABLED", "0")
    with pytest.raises(V2HostAuthenticationError):
        build_host_authentication()


def test_build_host_authentication_wraps_initialisation_failure(monkeypatch):
    monkeypatch.setenv("PHOENIX_CORE_V2_ENABLED", "1")
    with patch(
        "core.v2_runtime.host_auth_adapter.V2HostMiddleware.from_environment",
        side_effect=RuntimeError("runtime unavailable"),
    ):
        with pytest.raises(V2HostAuthenticationError):
            build_host_authentication()


def test_authenticate_delegates_to_host_middleware():
    middleware = Mock()
    middleware.login.return_value = {"authenticated": True, "destination": "user"}
    result = authenticate(middleware, "alice", "secret", "org-1", True)
    middleware.login.assert_called_once_with(
        username="alice",
        password="secret",
        organisation_id="org-1",
        remember_me=True,
    )
    assert result["authenticated"] is True


def test_current_session_delegates_to_host_middleware():
    middleware = Mock()
    middleware.session.return_value = {"session_id": "s1"}
    assert current_session(middleware, "s1", "org-1") == {"session_id": "s1"}
    middleware.session.assert_called_once_with("s1", "org-1")


def test_logout_delegates_to_host_middleware():
    middleware = Mock()
    middleware.logout.return_value = {"revoked": True}
    assert logout(middleware, "token") == {"revoked": True}
    middleware.logout.assert_called_once_with("token")
