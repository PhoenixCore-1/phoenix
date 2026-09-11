"""Static contract checks for the V2 HTTP host boundary."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_v2_host_has_fail_closed_switch():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    assert 'if not v2_enabled()' in source
    assert 'raise V2HttpIntegrationError' in source


def test_v2_host_owns_authentication_routes_when_enabled():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    assert 'path == "/api/login" and v2_enabled()' in source
    assert 'path == "/api/session" and v2_enabled()' in source
    assert 'path == "/api/logout" and v2_enabled()' in source


def test_v2_host_has_no_legacy_fallback_inside_v2_routes():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    login_block = source.split('if path == "/api/login" and v2_enabled():', 1)[1]
    login_block = login_block.split('if path == "/api/logout" and v2_enabled():', 1)[0]
    assert 'super().do_POST()' not in login_block


def test_v2_host_sets_all_three_context_cookies():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "build_session_cookie" in source
    assert "build_token_cookie" in source
    assert "build_organisation_cookie" in source


def test_v2_host_reuses_persistent_integration():
    source = (ROOT / "server.py").read_text(encoding="utf-8")
    assert "phoenix_v2_integration" in source
    assert "server.serve_forever()" in source
    assert "server.phoenix_v2_integration.close()" in source
