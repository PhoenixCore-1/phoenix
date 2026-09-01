"""
Phoenix System Platform
API Dispatch V1.0.

Framework-neutral dispatch layer.

API dispatch selects the appropriate System Platform service.
Authorization and identity remain authoritative in Core.
No direct database access is permitted.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .routes import RouteDefinition, find_route
from ..services.health import SystemPlatformHealthService
from ..services.modules import ModuleAdministrationService
from ..services.organisations import OrganisationAdministrationService


class ApiDispatchError(RuntimeError):
    """Base API dispatch error."""


class RouteNotFoundError(ApiDispatchError):
    """Raised when no registered route matches the request."""


@dataclass(frozen=True)
class DispatchContext:
    """Request context supplied by the eventual HTTP integration."""

    user: Mapping[str, Any]
    body: Mapping[str, Any] | None = None
    path_parameters: Mapping[str, Any] | None = None
    query_parameters: Mapping[str, Any] | None = None


class ApiDispatcher:
    """
    Framework-neutral System Platform API dispatcher.

    The dispatcher owns route-to-service orchestration only.
    Core remains responsible for authorization and identity.
    """

    def __init__(
        self,
        module_service: ModuleAdministrationService,
        organisation_service: OrganisationAdministrationService,
        health_service: SystemPlatformHealthService,
    ):
        self._module_service = module_service
        self._organisation_service = organisation_service
        self._health_service = health_service

    def resolve(
        self,
        method: str,
        path: str,
    ) -> RouteDefinition:
        route = find_route(method, path)

        if route is None:
            raise RouteNotFoundError(
                f"Route not found: {method.upper()} {path}"
            )

        return route

    def dispatch(
        self,
        method: str,
        path: str,
        context: DispatchContext,
    ):
        route = self.resolve(method, path)

        handler = getattr(
            self,
            f"_dispatch_{route.handler_name}",
            None,
        )

        if handler is None:
            raise ApiDispatchError(
                f"No dispatcher handler registered for "
                f"{route.handler_name}"
            )

        return handler(context)

    # ------------------------------------------------------------
    # Health
    # ------------------------------------------------------------

    def _dispatch_get_health(self, context):
        return self._health_service.get_health()

    # ------------------------------------------------------------
    # Module Administration
    # ------------------------------------------------------------

    def _dispatch_get_module_catalog(self, context):
        return self._module_service.get_module_catalog()

    def _dispatch_get_enabled_modules(self, context):
        return self._module_service.get_enabled_modules()

    def _dispatch_get_module_entitlement(self, context):
        return self._module_service.get_module_entitlement()

    def _dispatch_check_module_access(self, context):
        body = context.body or {}
        module_id = body.get("module_id")

        return self._module_service.check_module_access(
            module_id
        )

    def _dispatch_get_licences(self, context):
        return self._module_service.get_licences()

    def _dispatch_enable_module(self, context):
        body = context.body or {}

        return self._module_service.enable_module(
            body["module_id"]
        )

    def _dispatch_disable_module(self, context):
        body = context.body or {}

        return self._module_service.disable_module(
            body["module_id"]
        )

    def _dispatch_set_licence(self, context):
        body = context.body or {}

        return self._module_service.set_licence(
            body
        )

    # ------------------------------------------------------------
    # Organisation Administration
    # ------------------------------------------------------------

    def _dispatch_list_organisations(self, context):
        return self._organisation_service.list_organisations()

    def _dispatch_get_organisation(self, context):
        params = context.path_parameters or {}

        return self._organisation_service.get_organisation(
            params.get("organisation_id")
        )

    def _dispatch_create_organisation(self, context):
        return self._organisation_service.create_organisation(
            context.body or {}
        )

    def _dispatch_update_organisation(self, context):
        params = context.path_parameters or {}

        return self._organisation_service.update_organisation(
            params.get("organisation_id"),
            context.body or {},
        )

    def _dispatch_set_organisation_status(self, context):
        params = context.path_parameters or {}
        body = context.body or {}

        return self._organisation_service.set_organisation_status(
            params.get("organisation_id"),
            body.get("active"),
        )
