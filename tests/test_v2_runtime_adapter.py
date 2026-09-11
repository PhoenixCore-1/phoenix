from types import SimpleNamespace
from uuid import UUID

from core.v2_runtime.adapter import V2RuntimeAdapter, V2RuntimeUnavailable
from core.v2_runtime.contracts import V2Request


class FakeIntegration:
    def __init__(self):
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        return SimpleNamespace(success=True, data={"ok": True})


class FakeApi:
    def __init__(self):
        self.auth_calls = []
        self.revoke_calls = []

    def authenticate(self, **kwargs):
        self.auth_calls.append(kwargs)
        return {"token": "v2-token"}

    def revoke_session(self, **kwargs):
        self.revoke_calls.append(kwargs)
        return {"revoked": True}


class FakeRuntime:
    def __init__(self):
        self.integration = FakeIntegration()
        self.api = FakeApi()
        self.closed = False

    def close(self):
        self.closed = True


def test_handle_forwards_v2_context_and_payload():
    runtime = FakeRuntime()
    adapter = V2RuntimeAdapter(runtime)
    organisation_id = UUID("11111111-1111-1111-1111-111111111111")
    session_id = UUID("22222222-2222-2222-2222-222222222222")

    result = adapter.handle(
        V2Request(
            request_id="req-1",
            operation="identity.current",
            session_id=session_id,
            organisation_id=organisation_id,
            payload={"source": "test"},
        )
    )

    request = runtime.integration.requests[0]
    assert result.success is True
    assert request.request_id == "req-1"
    assert request.operation == "identity.current"
    assert request.session_id == session_id
    assert request.organisation_id == organisation_id
    assert request.payload == {"source": "test"}


def test_authenticate_and_revoke_use_v2_api():
    runtime = FakeRuntime()
    adapter = V2RuntimeAdapter(runtime)

    assert adapter.authenticate(
        request_id="req-auth",
        username="user@example.com",
        password="secret",
    ) == {"token": "v2-token"}
    assert runtime.api.auth_calls[0]["request_id"] == "req-auth"
    assert runtime.api.auth_calls[0]["username"] == "user@example.com"

    assert adapter.revoke_session(
        request_id="req-revoke",
        token="v2-token",
    ) == {"revoked": True}
    assert runtime.api.revoke_calls[0]["request_id"] == "req-revoke"
    assert runtime.api.revoke_calls[0]["token"] == "v2-token"


def test_close_releases_owned_runtime():
    runtime = FakeRuntime()
    V2RuntimeAdapter(runtime).close()
    assert runtime.closed is True


def test_environment_requires_v2_path(monkeypatch):
    monkeypatch.delenv("PHOENIX_CORE_V2_PATH", raising=False)
    monkeypatch.delenv("PHOENIX_CORE_V2_DATABASE", raising=False)

    try:
        V2RuntimeAdapter.from_environment()
    except V2RuntimeUnavailable as exc:
        assert "PHOENIX_CORE_V2_PATH" in str(exc)
    else:
        raise AssertionError("Expected V2RuntimeUnavailable")
