from core.v2_runtime import http_integration


class FakeAuth:
    def login(self, username, password, organisation_id=None):
        return {"data": {"session_id": "session-1", "token": "token-1"}}

    def session(self, session_id, organisation_id):
        return {
            "authenticated": True,
            "session_id": session_id,
            "organisation_id": organisation_id,
        }

    def platform_destination(self, session_id, organisation_id):
        return {"data": {"destination": "USER_PLATFORM"}}

    def logout(self, token):
        return {"data": {"revoked": True}}


def test_cookie_round_trip_and_expiry():
    cookie = http_integration.build_session_cookie("token-1", remember_me=True)
    assert http_integration.cookie_value(cookie, http_integration.V2_SESSION_COOKIE) == "token-1"
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Max-Age=2592000" in cookie

    session_cookie, organisation_cookie = http_integration.clear_v2_cookies()
    assert "Max-Age=0" in session_cookie
    assert "Max-Age=0" in organisation_cookie


def test_authenticate_v2_uses_core_destination(monkeypatch):
    monkeypatch.setattr(http_integration, "v2_enabled", lambda: True)
    monkeypatch.setattr(http_integration, "build_v2_auth", lambda: FakeAuth())

    result = http_integration.authenticate_v2(
        "jaco",
        "secret",
        "org-1",
        remember_me=True,
    )

    assert result["authenticated"] is True
    assert result["session_id"] == "session-1"
    assert result["organisation_id"] == "org-1"
    assert result["destination"] == "USER_PLATFORM"
    assert result["remember_me"] is True


def test_current_session_requires_both_session_and_organisation(monkeypatch):
    monkeypatch.setattr(http_integration, "v2_enabled", lambda: True)
    monkeypatch.setattr(http_integration, "build_v2_auth", lambda: FakeAuth())

    cookie = (
        "phoenix_v2_session=session-1; "
        "phoenix_v2_organisation=org-1"
    )
    result = http_integration.current_v2_session(cookie)

    assert result["session_id"] == "session-1"
    assert result["organisation_id"] == "org-1"
    assert result["platform"]["destination"] == "USER_PLATFORM"


def test_logout_revokes_token_and_clears_cookies(monkeypatch):
    monkeypatch.setattr(http_integration, "v2_enabled", lambda: True)

    calls = []

    class LogoutAuth(FakeAuth):
        def logout(self, token):
            calls.append(token)
            return {"data": {"revoked": True}}

    monkeypatch.setattr(http_integration, "build_v2_auth", lambda: LogoutAuth())

    ok, headers = http_integration.logout_v2(
        "phoenix_v2_session=token-1; phoenix_v2_organisation=org-1"
    )

    assert ok is True
    assert calls == ["token-1"]
    assert all("Max-Age=0" in header for header in headers)
