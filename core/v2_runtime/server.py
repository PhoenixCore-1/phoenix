"""V2-aware HTTP server entry point for Phoenix User UI migration."""

from __future__ import annotations

import json
from http.server import ThreadingHTTPServer

from core.app import Handler as LegacyHandler
from core.app import HOST, PORT, configure_production_module, init_db, read_json
from core.v2_runtime.feature_switch import v2_enabled
from core.v2_runtime.http_integration import (
    V2HttpIntegration,
    V2HttpIntegrationError,
    build_organisation_cookie,
    build_session_cookie,
    build_token_cookie,
    clear_v2_cookies,
    cookie_value,
)
from core.v2_runtime.route_boundary import decide_v2_route

V2_SESSION_COOKIE = "phoenix_v2_session"
V2_ORGANISATION_COOKIE = "phoenix_v2_organisation"


def _send_json(handler, payload, status=200, cookies=()):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    for cookie in cookies:
        handler.send_header("Set-Cookie", cookie)
    handler.end_headers()
    handler.wfile.write(body)


def _route_blocked(handler, decision):
    _send_json(
        handler,
        {"ok": False, "code": decision.code, "error": decision.message},
        status=503,
    )


class V2Handler(LegacyHandler):
    """Existing HTTP doorway with V2-owned authentication/session routes."""

    def _v2(self):
        integration = getattr(self.server, "phoenix_v2_integration", None)
        if integration is None:
            raise V2HttpIntegrationError("Phoenix Core V2 runtime is unavailable.")
        return integration

    def _enforce_route_boundary(self, method, path):
        if not v2_enabled():
            return True
        decision = decide_v2_route(method, path)
        if decision.allowed:
            return True
        _route_blocked(self, decision)
        return False

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if not self._enforce_route_boundary("GET", path):
            return
        if path == "/api/session" and v2_enabled():
            try:
                cookie_header = self.headers.get("Cookie")
                session_id = cookie_value(cookie_header, V2_SESSION_COOKIE)
                organisation_id = cookie_value(cookie_header, V2_ORGANISATION_COOKIE)
                if not session_id or not organisation_id:
                    _send_json(self, {"authenticated": False, "code": "AUTH_REQUIRED"}, 401)
                    return
                integration = self._v2()
                context = integration.session(session_id, organisation_id)
                destination = integration.platform_destination(session_id, organisation_id)
                _send_json(self, {
                    "authenticated": True,
                    "session_id": session_id,
                    "organisation_id": organisation_id,
                    "context": context,
                    "platform": destination.get("data") or destination,
                })
            except Exception as exc:
                _send_json(self, {"error": str(exc), "code": "V2_SESSION_UNAVAILABLE"}, 401)
            return
        super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if not self._enforce_route_boundary("POST", path):
            return
        if path == "/api/login" and v2_enabled():
            data = read_json(self)
            try:
                integration = self._v2()
                result = integration.login(
                    str(data.get("username", "")).strip(),
                    data.get("password", ""),
                    data.get("organisation_id"),
                )
                payload = result.get("data") or result
                session_id = payload.get("session_id")
                token = payload.get("token")
                organisation_id = payload.get("organisation_id") or data.get("organisation_id")
                if not session_id or not token or not organisation_id:
                    raise V2HttpIntegrationError("Core V2 returned incomplete authentication state.")
                context = integration.session(str(session_id), str(organisation_id))
                destination = integration.platform_destination(str(session_id), str(organisation_id))
                platform = destination.get("data") or destination
                remember_me = bool(data.get("remember_me", False))
                cookies = (
                    build_session_cookie(str(session_id), remember_me=remember_me),
                    build_token_cookie(str(token), remember_me=remember_me),
                    build_organisation_cookie(str(organisation_id), remember_me=remember_me),
                )
                _send_json(self, {
                    "ok": True,
                    "authenticated": True,
                    "session_id": str(session_id),
                    "organisation_id": str(organisation_id),
                    "context": context,
                    "platform": platform,
                    "destination": platform.get("destination"),
                }, cookies=cookies)
            except Exception as exc:
                _send_json(self, {"error": str(exc), "code": "AUTHENTICATION_FAILED"}, 401)
            return

        if path == "/api/logout" and v2_enabled():
            token = cookie_value(self.headers.get("Cookie"), "phoenix_v2_token")
            if not token:
                _send_json(self, {"ok": True, "code": "NO_SESSION"}, cookies=clear_v2_cookies())
                return
            try:
                self._v2().logout(token)
            except Exception:
                _send_json(self, {"ok": False, "code": "LOGOUT_FAILED", "error": "Session termination failed."}, status=503)
                return
            _send_json(self, {"ok": True}, cookies=clear_v2_cookies())
            return
        super().do_POST()


def build_server():
    """Create the HTTP doorway with one persistent Core V2 integration."""
    if not v2_enabled():
        raise V2HttpIntegrationError("Phoenix Core V2 is not enabled.")
    integration = V2HttpIntegration.from_environment()
    try:
        server = ThreadingHTTPServer((HOST, PORT), V2Handler)
    except Exception:
        integration.close()
        raise
    server.phoenix_v2_integration = integration
    return server


def run():
    init_db()
    configure_production_module(
        r"C:\Users\Disa Lombard\OneDrive - Upat\Upat\Phoenix App\Phoenix_App_Production_Module1_V1.0\Phoenix_Production_Module1_V1"
    )
    server = build_server()
    try:
        print(f"Phoenix Core V2 host running at http://localhost:{PORT}")
        server.serve_forever()
    finally:
        server.phoenix_v2_integration.close()
        server.server_close()


if __name__ == "__main__":
    run()
