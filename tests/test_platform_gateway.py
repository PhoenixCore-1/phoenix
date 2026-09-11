from core.v2_runtime.platform_gateway import (
    PlatformGatewayError,
    authorize_platform_entry,
    requested_platform,
)


class FakeIntegration:
    def __init__(self, destination="USER_PLATFORM", fail=False):
        self.destination = destination
        self.fail = fail
        self.calls = []

    def session(self, session_id, organisation_id):
        self.calls.append(("session", session_id, organisation_id))
        if self.fail:
            raise RuntimeError("session failure")
        return {"ok": True}

    def platform_destination(self, session_id, organisation_id):
        self.calls.append(("destination", session_id, organisation_id))
        if self.fail:
            raise RuntimeError("destination failure")
        return {"data": {"destination": self.destination, "entitlements": []}}


def test_requested_platform_accepts_exact_and_child_routes():
    assert requested_platform("/user") == "USER_PLATFORM"
    assert requested_platform("/user/") == "USER_PLATFORM"
    assert requested_platform("/user/core/app.js?x=1") == "USER_PLATFORM"
    assert requested_platform("/company/settings") == "COMPANY_PLATFORM"
    assert requested_platform("/system/admin") == "SYSTEM_PLATFORM"
    assert requested_platform("/unknown") is None


def test_authorized_entry_is_granted_by_core_destination():
    integration = FakeIntegration("USER_PLATFORM")
    result = authorize_platform_entry(
        integration,
        "USER_PLATFORM",
        "session-1",
        "org-1",
    )

    assert result.allowed is True
    assert result.status == 200
    assert result.code == "PLATFORM_ACCESS_GRANTED"
    assert result.destination == "USER_PLATFORM"
    assert [call[0] for call in integration.calls] == ["session", "destination"]


def test_wrong_platform_is_denied():
    integration = FakeIntegration("COMPANY_PLATFORM")
    result = authorize_platform_entry(
        integration,
        "USER_PLATFORM",
        "session-1",
        "org-1",
    )

    assert result.allowed is False
    assert result.status == 403
    assert result.code == "PLATFORM_ACCESS_DENIED"
    assert result.destination == "COMPANY_PLATFORM"


def test_missing_session_context_requires_authentication():
    integration = FakeIntegration()
    result = authorize_platform_entry(integration, "USER_PLATFORM", "", "org-1")

    assert result.allowed is False
    assert result.status == 401
    assert result.code == "AUTH_REQUIRED"
    assert integration.calls == []


def test_unknown_platform_returns_not_found():
    integration = FakeIntegration()
    result = authorize_platform_entry(integration, "NOT_A_PLATFORM", "s", "o")

    assert result.allowed is False
    assert result.status == 404
    assert result.code == "PLATFORM_NOT_FOUND"
    assert integration.calls == []


def test_core_failure_is_not_converted_to_access_granted():
    integration = FakeIntegration(fail=True)

    try:
        authorize_platform_entry(integration, "USER_PLATFORM", "s", "o")
    except PlatformGatewayError as exc:
        assert "could not resolve the platform destination" in str(exc)
    else:
        raise AssertionError("Expected PlatformGatewayError")
