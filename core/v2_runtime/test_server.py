"""Tests for the V2-aware HTTP host boundary."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from core.v2_runtime import server


class FakeIntegration:
    def __init__(self):
        self.calls = []
        self.closed = False

    def login(self, username, password, organisation_id=None):
        self.calls.append(("login", username, password, organisation_id))
        return {
            "data": {
                "session_id": "session-1",
                "token": "token-1",
                "organisation_id": "org-1",
            }
        }

    def session(self, session_id, organisation_id):
        self.calls.append(("session", session_id, organisation_id))
        return {"data": {"identity_id": "user-1", "organisation_id": organisation_id}}

    def platform_destination(self, session_id, organisation_id):
        self.calls.append(("destination", session_id, organisation_id))
        return {"data": {"destination": "user-platform"}}

    def logout(self, token):
        self.calls.append(("logout", token))
        return {"data": {"revoked": True}}

    def close(self):
        self.closed = True


def test_v2_server_requires_feature_flag(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: False)
    with pytest.raises(server.V2HttpIntegrationError):
        server.build_server()


def test_v2_handler_login_uses_v2(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    integration = FakeIntegration()
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace(phoenix_v2_integration=integration)
    handler.path = "/api/login"
    handler.headers = {"Cookie": ""}

    class FakeWFile:
        def __init__(self):
            self.value = b""
        def write(self, value):
            self.value += value

    handler.wfile = FakeWFile()
    responses = []
    handler.send_response = lambda status: responses.append(("status", status))
    handler.send_header = lambda name, value: responses.append((name, value))
    handler.end_headers = lambda: responses.append(("end", None))
    monkeypatch.setattr(server, "read_json", lambda _: {
        "username": "user@example.com",
        "password": "secret",
        "organisation_id": "org-1",
        "remember_me": True,
    })

    handler.do_POST()

    assert integration.calls == [
        ("login", "user@example.com", "secret", "org-1"),
        ("session", "session-1", "org-1"),
        ("destination", "session-1", "org-1"),
    ]
    assert any(item == ("status", 200) for item in responses)
    assert sum(1 for name, _ in responses if name == "Set-Cookie") == 3
    payload = json.loads(handler.wfile.value)
    assert payload["destination"] == "user-platform"


def test_v2_handler_session_requires_context(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    integration = FakeIntegration()
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace(phoenix_v2_integration=integration)
    handler.path = "/api/session"
    handler.headers = {"Cookie": ""}
    handler.wfile = SimpleNamespace(write=lambda _: None)
    responses = []
    handler.send_response = lambda status: responses.append(status)
    handler.send_header = lambda *_: None
    handler.end_headers = lambda: None

    handler.do_GET()

    assert responses == [401]
    assert integration.calls == []


def test_v2_handler_logout_revokes_and_clears(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    integration = FakeIntegration()
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace(phoenix_v2_integration=integration)
    handler.path = "/api/logout"
    handler.headers = {"Cookie": "phoenix_v2_token=token-1"}
    handler.wfile = SimpleNamespace(write=lambda _: None)
    responses = []
    handler.send_response = lambda status: responses.append(("status", status))
    handler.send_header = lambda name, value: responses.append((name, value))
    handler.end_headers = lambda: None

    handler.do_POST()

    assert integration.calls == [("logout", "token-1")]
    assert responses.count(("status", 200)) == 1
    assert sum(1 for name, _ in responses if name == "Set-Cookie") == 3


def test_v2_handler_does_not_fallback_when_v2_runtime_missing(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace()
    with pytest.raises(server.V2HttpIntegrationError):
        handler._v2()
