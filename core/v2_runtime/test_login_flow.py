"""Contract tests for the shared V2 login flow."""

from login_flow import V2LoginFlowError, login


def test_login_requires_authoritative_organisation(monkeypatch):
    class FakeAuth:
        def login(self, username, password, organisation_id):
            return {"data": {"session_id": "session-1", "token": "token-1"}}

    monkeypatch.setattr("login_flow.build_v2_auth", lambda: FakeAuth())
    try:
        login("user", "password")
    except V2LoginFlowError as exc:
        assert "organisation context" in str(exc)
    else:
        raise AssertionError("login must reject a missing organisation context")


def test_login_returns_authoritative_destination(monkeypatch):
    class FakeAuth:
        def login(self, username, password, organisation_id):
            return {"data": {"session_id": "session-1", "token": "token-1", "organisation_id": "org-1"}}

        def session(self, session_id, organisation_id):
            return {"permissions": ["company.platform.access"], "organisation": {"id": organisation_id}}

    monkeypatch.setattr("login_flow.build_v2_auth", lambda: FakeAuth())
    result = login("user", "password", "org-1")
    assert result["authenticated"] is True
    assert result["destination"] == "COMPANY_PLATFORM"
    assert result["session_id"] == "session-1"
