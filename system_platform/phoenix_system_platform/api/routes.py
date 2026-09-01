"""
Phoenix System Platform
API Route Contract V1.0.

This module defines the System Platform API surface.
HTTP/framework integration is intentionally separate.

Routes delegate to System Platform services.
Services delegate to CoreAdapter.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass(frozen=True)
class RouteDefinition:
    method: str
    path: str
    handler_name: str
    permission: Optional[str] = None


SYSTEM_PLATFORM_ROUTES = (
    # ------------------------------------------------------------
    # System Platform Health
    # ------------------------------------------------------------

    RouteDefinition(
        "GET",
        "/api/system-platform/health",
        "get_health",
        None,
    ),

    # ------------------------------------------------------------
    # Module administration
    # ------------------------------------------------------------

    RouteDefinition(
        "GET",
        "/api/system-platform/modules",
        "get_module_catalog",
        "modules.view",
    ),

    RouteDefinition(
        "GET",
        "/api/system-platform/modules/enabled",
        "get_enabled_modules",
        "modules.view",
    ),

    RouteDefinition(
        "GET",
        "/api/system-platform/modules/entitlement",
        "get_module_entitlement",
        "modules.view",
    ),

    RouteDefinition(
        "GET",
        "/api/system-platform/modules/access",
        "check_module_access",
        "modules.view",
    ),

    RouteDefinition(
        "GET",
        "/api/system-platform/licences",
        "get_licences",
        "licensing.manage",
    ),

    RouteDefinition(
        "POST",
        "/api/system-platform/modules/enable",
        "enable_module",
        "licensing.manage",
    ),

    RouteDefinition(
        "POST",
        "/api/system-platform/modules/disable",
        "disable_module",
        "licensing.manage",
    ),

    RouteDefinition(
        "POST",
        "/api/system-platform/licences",
        "set_licence",
        "licensing.manage",
    ),

    # ------------------------------------------------------------
    # Organisation administration
    # ------------------------------------------------------------

    RouteDefinition(
        "GET",
        "/api/system-platform/organisations",
        "list_organisations",
        "tenant.view",
    ),

    RouteDefinition(
        "GET",
        "/api/system-platform/organisations/{organisation_id}",
        "get_organisation",
        "tenant.view",
    ),

    RouteDefinition(
        "POST",
        "/api/system-platform/organisations",
        "create_organisation",
        "tenant.create",
    ),

    RouteDefinition(
        "PUT",
        "/api/system-platform/organisations/{organisation_id}",
        "update_organisation",
        "tenant.manage",
    ),

    RouteDefinition(
        "POST",
        "/api/system-platform/organisations/{organisation_id}/status",
        "set_organisation_status",
        "tenant.status.manage",
    ),
)


def get_routes():
    """Return the immutable System Platform route contract."""
    return SYSTEM_PLATFORM_ROUTES


def find_route(
    method: str,
    path: str,
) -> Optional[RouteDefinition]:
    """
    Find an exact route definition.

    Parameterised route matching is intentionally left to the
    eventual HTTP integration layer.
    """
    method = method.upper()

    for route in SYSTEM_PLATFORM_ROUTES:
        if (
            route.method == method
            and route.path == path
        ):
            return route

    return None

