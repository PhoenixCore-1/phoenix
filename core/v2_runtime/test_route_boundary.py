"""Tests for fail-closed V2 API route classification."""

from core.v2_runtime.route_boundary import decide_v2_route


def test_v2_auth_routes_are_owned_by_core():
    for method, path in (("GET", "/api/session"), ("POST", "/api/login"), ("POST", "/api/logout")):
        decision = decide_v2_route(method, path)
        assert decision.allowed is True
        assert decision.code == "V2_AUTH_ROUTE"


def test_unmigrated_api_routes_fail_closed():
    decision = decide_v2_route("GET", "/api/production/orders")
    assert decision.allowed is False
    assert decision.code == "V2_ROUTE_NOT_MIGRATED"


def test_non_api_transport_routes_remain_available():
    decision = decide_v2_route("GET", "/index.html")
    assert decision.allowed is True
    assert decision.code == "TRANSPORT_ROUTE"
