"""Tests for Core-authorized User UI module discovery."""

from __future__ import annotations

import json
from types import SimpleNamespace

from core.v2_runtime import server


class FakeIntegration:
    def __init__(self, entitlements):
        self.calls = []
        self.entitlements = entitlements

    def session(self, session_id, organisation_id):
        self.calls.append(("session", session_id, organisation_id))
        return {"data": {"authenticated": True}}

    def platform_destination(self, session_id, organisation_id):
        self.calls.append(("destination", session_id, organisation_id))
        return {"data": {"destination": "user-platform", "entitlements": self.entitlements}}


def test_module_catalog_is_filtered_by_core_entitlements(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    integration = FakeIntegration(["production"])
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace(phoenix_v2_integration=integration)
    handler.path = "/api/module-catalog"
    handler.headers = {"Cookie": "phoenix_v2_session=session-1; phoenix_v2_organisation=org-1"}
    handler.wfile = SimpleNamespace(write=lambda value: setattr(handler, "body", value))
    statuses = []
    handler.send_response = lambda status: statuses.append(status)
    handler.send_header = lambda *_: None
    handler.end_headers = lambda: None

    handler.do_GET()

    payload = json.loads(handler.body)
    assert statuses == [200]
    assert [item["code"] for item in payload["catalog"]] == ["production"]
    assert integration.calls == [("session", "session-1", "org-1"), ("destination", "session-1", "org-1")]


def test_module_catalog_requires_authenticated_context(monkeypatch):
    monkeypatch.setattr(server, "v2_enabled", lambda: True)
    integration = FakeIntegration(["production"])
    handler = object.__new__(server.V2Handler)
    handler.server = SimpleNamespace(phoenix_v2_integration=integration)
    handler.path = "/api/module-catalog"
    handler.headers = {"Cookie": ""}
    handler.wfile = SimpleNamespace(write=lambda _: None)
    statuses = []
    handler.send_response = lambda status: statuses.append(status)
    handler.send_header = lambda *_: None
    handler.end_headers = lambda: None

    handler.do_GET()

    assert statuses == [401]
    assert integration.calls == []
