"""Contract tests for the V2 HTTP adapter.

These tests use a fake runtime boundary so they verify translation without
requiring a live database or HTTP server.
"""

from dataclasses import dataclass
from uuid import UUID

from http_adapter import V2HttpAdapter


@dataclass
class Response:
    data: object
    request_id: str


class FakeApi:
    def authenticate(self, **kwargs):
        return Response({"token": "token-1", "session_id": "session-1"}, kwargs["request_id"])

    def get_current_identity(self, **kwargs):
        assert isinstance(kwargs["session_id"], UUID)
        assert isinstance(kwargs["organisation_id"], UUID)
        return Response({"id": "identity-1", "type": "HUMAN", "status": "ACTIVE"}, kwargs["request_id"])

    def get_current_user(self, **kwargs):
        return Response({"id": "user-1", "username": "jaco", "display_name": "Jaco"}, kwargs["request_id"])

    def get_current_organisation(self, **kwargs):
        return Response({"id": "org-1", "code": "ORG", "name": "Organisation"}, kwargs["request_id"])

    def revoke_session(self, **kwargs):
        return Response({"revoked": True}, kwargs["request_id"])


class FakeRuntime:
    def __init__(self):
        self.api = FakeApi()


def test_authenticate_translates_to_v2_api():
    adapter = V2HttpAdapter(FakeRuntime())
    result = adapter.authenticate(username="jaco", password="secret")
    assert result["data"]["token"] == "token-1"


def test_current_context_requires_and_forwards_tenant_context():
    adapter = V2HttpAdapter(FakeRuntime())
    result = adapter.current_context(
        session_id="11111111-1111-1111-1111-111111111111",
        organisation_id="22222222-2222-2222-2222-222222222222",
    )
    assert result["authenticated"] is True
    assert result["user"]["username"] == "jaco"
    assert result["organisation"]["code"] == "ORG"


def test_revoke_session_returns_authoritative_result():
    adapter = V2HttpAdapter(FakeRuntime())
    result = adapter.revoke_session(token="token-1")
    assert result["data"]["revoked"] is True
