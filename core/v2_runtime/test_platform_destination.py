"""Contract tests for Core platform destination routing."""

from platform_destination import PlatformDestination, resolve_platform_destination


def test_explicit_system_capability_routes_to_system_platform():
    route = resolve_platform_destination(
        session_id="session-1",
        organisation_id="org-1",
        context={"permissions": ["system.platform.access"]},
    )
    assert route.destination is PlatformDestination.SYSTEM_PLATFORM


def test_explicit_company_capability_routes_to_company_platform():
    route = resolve_platform_destination(
        session_id="session-1",
        organisation_id="org-1",
        context={"permissions": ["company.platform.access"]},
    )
    assert route.destination is PlatformDestination.COMPANY_PLATFORM


def test_default_organisation_user_routes_to_user_platform():
    route = resolve_platform_destination(
        session_id="session-1",
        organisation_id="org-1",
        context={"permissions": ["production.view"]},
    )
    assert route.destination is PlatformDestination.USER_PLATFORM


def test_client_cannot_select_destination_without_core_capability():
    route = resolve_platform_destination(
        session_id="session-1",
        organisation_id="org-1",
        context={"requested_destination": "SYSTEM_PLATFORM"},
    )
    assert route.destination is PlatformDestination.USER_PLATFORM
