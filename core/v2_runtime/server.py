"""Single Phoenix application HTTP host for Core V2 and platform workspaces."""

from __future__ import annotations

import json
import mimetypes
import os
from http.server import ThreadingHTTPServer
from pathlib import Path

from core.app import Handler as LegacyHandler
from core.app import HOST, PORT, configure_production_module, init_db, read_json
from core.module_contract import module_catalog
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
from core.v2_runtime.platform_gateway import (
    PlatformGatewayError,
    authorize_platform_entry,
    requested_platform,
)
from core.v2_runtime.route_boundary import decide_v2_route

V2_SESSION_COOKIE = "phoenix_v2_session"
V2_ORGANISATION_COOKIE = "phoenix_v2_organisation"
PUBLIC_BASE_URL = os.getenv("PHOENIX_PUBLIC_BASE_URL", "https://corephoenix.co.za").rstrip("/")
APP_BASE_URL = os.getenv("PHOENIX_APP_BASE_URL", "https://app.corephoenix.co.za").rstrip("/")
USER_UI_ROOT = Path(__file__).resolve().parents[2] / "user_ui"
CORE_ROOT = Path(__file__).resolve().parents[1]


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


def _redirect(handler, location, status=302):
    handler.send_response(status)
    handler.send_header("Location", location)
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()


def _route_blocked(handler, decision):
    _send_json(handler, {"ok": False, "code": decision.code, "error": decision.message}, status=503)


def _module_catalog_for_entitlements(entitlements):
    """Return only registered modules authorised by the Core context."""
    allowed = {str(code) for code in (entitlements or [])}
    return [module for module in module_catalog() if module.get("code") in allowed]


def _is_configured_host(handler, expected_url):
    expected_host = expected_url.split("://", 1)[-1].split("/", 1)[0].lower()
    request_host = handler.headers.get("Host", "").lower()
    return request_host == expected_host or request_host.split(":", 1)[0] == expected_host


def _user_ui_file(path):
    """Resolve a /user/* URL strictly inside user_ui."""
    relative = path[len("/user/"):] if path.startswith("/user/") else ""
    if not relative:
        relative = "index.html"
    candidate = (USER_UI_ROOT / relative).resolve()
    try:
        candidate.relative_to(USER_UI_ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def _serve_file(handler, file_path):
    data = file_path.read_bytes()
    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class V2Handler(LegacyHandler):
    """Single HTTP doorway with V2 authentication and platform routing."""

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

    def _authenticated_context(self):
        cookie_header = self.headers.get("Cookie")
        session_id = cookie_value(cookie_header, V2_SESSION_COOKIE)
        organisation_id = cookie_value(cookie_header, V2_ORGANISATION_COOKIE)
        if not session_id or not organisation_id:
            raise V2HttpIntegrationError("Authenticated V2 session context is required.")
        integration = self._v2()
        context = integration.session(session_id, organisation_id)
        destination = integration.platform_destination(session_id, organisation_id)
        platform = destination.get("data") or destination
        return session_id, organisation_id, context, platform

    def _authorize_platform(self, path):
        requested = requested_platform(path)
        if requested is None:
            return None
        cookie_header = self.headers.get("Cookie")
        session_id = cookie_value(cookie_header, V2_SESSION_COOKIE)
        organisation_id = cookie_value(cookie_header, V2_ORGANISATION_COOKIE)
        if not session_id or not organisation_id:
            if path.rstrip("/") == "/user":
                _redirect(self, f"{PUBLIC_BASE_URL}/")
            else:
                _send_json(self, {"ok": False, "code": "AUTH_REQUIRED", "error": "Sign in required."}, 401)
            return False
        try:
            entry = authorize_platform_entry(self._v2(), requested, session_id, organisation_id)
        except PlatformGatewayError:
            _send_json(self, {"ok": False, "code": "PLATFORM_UNAVAILABLE", "error": "Phoenix platform authorization is unavailable."}, 503)
            return False
        if not entry.allowed:
            _send_json(self, {"ok": False, "code": entry.code, "error": entry.message}, entry.status)
            return False
        return entry

    def _serve_user_platform(self, path):
        entry = self._authorize_platform(path)
        if entry is False:
            return True
        if entry is None:
            return False
        file_path = _user_ui_file(path)
        if file_path is None:
            _send_json(self, {"ok": False, "code": "USER_UI_NOT_FOUND", "error": "User workspace resource not found."}, 404)
            return True
        _serve_file(self, file_path)
        return True

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        # Public origin is a presentation-only front door.
        if _is_configured_host(self, PUBLIC_BASE_URL) and path == "/":
            landing_page = CORE_ROOT / "landing.html"
            if landing_page.is_file():
                _serve_file(self, landing_page)
                return

        # Application origin is the sole authenticated application host.
        if _is_configured_host(self, APP_BASE_URL) and path == "/":
            try:
                self._authenticated_context()
                _redirect(self, "/user")
            except Exception:
                _redirect(self, f"{PUBLIC_BASE_URL}/")
            return

        if _is_configured_host(self, APP_BASE_URL) and path == "/login":
            login_page = CORE_ROOT / "index.html"
            if login_page.is_file():
                _serve_file(self, login_page)
                return

        if path == "/user" or path.startswith("/user/"):
            if not self._enforce_route_boundary("GET", "/user"):
                return
            self._serve_user_platform(path)
            return

        if not self._enforce_route_boundary("GET", path):
            return
        if path == "/api/session" and v2_enabled():
            try:
                session_id, organisation_id, context, platform = self._authenticated_context()
                _send_json(self, {
                    "authenticated": True,
                    "session_id": session_id,
                    "organisation_id": organisation_id,
                    "context": context,
                    "platform": platform,
                })
            except Exception:
                _send_json(self, {"error": "Authenticated V2 session context is unavailable.", "code": "V2_SESSION_UNAVAILABLE"}, 401)
            return

        if path == "/api/module-catalog" and v2_enabled():
            try:
                _, _, _, platform = self._authenticated_context()
                catalog = _module_catalog_for_entitlements(platform.get("entitlements", []))
                _send_json(self, {"ok": True, "catalog": catalog})
            except Exception:
                _send_json(self, {"error": "Authorized module catalog is unavailable.", "code": "V2_MODULE_CATALOG_UNAVAILABLE"}, 401)
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
            except Exception:
                _send_json(self, {"error": "Authentication failed.", "code": "AUTHENTICATION_FAILED"}, 401)
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
    """Create the one persistent Phoenix application HTTP doorway."""
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
        print(f"Phoenix application host running at {APP_BASE_URL}")
        server.serve_forever()
    finally:
        server.phoenix_v2_integration.close()
        server.server_close()


if __name__ == "__main__":
    run()
