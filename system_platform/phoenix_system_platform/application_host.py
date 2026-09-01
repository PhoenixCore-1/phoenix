"""
Phoenix System Platform
Application Host V1.0.

Framework-neutral bootstrap boundary.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .api.dispatch import ApiDispatcher
from .core_adapter import CoreAdapter
from .services.health import SystemPlatformHealthService
from .services.modules import ModuleAdministrationService
from .services.organisations import OrganisationAdministrationService


class ApplicationHostError(RuntimeError):
    """Base Application Host error."""


class ApplicationHostState:
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ApplicationContext:
    """Core-authenticated application context."""

    user: Mapping[str, Any]


class SystemPlatformApplicationHost:
    """
    Framework-neutral System Platform bootstrap host.

    The host owns construction only.
    Core remains authoritative for identity and authorization.
    """

    def __init__(
        self,
        core: Any = None,
        context: Optional[ApplicationContext] = None,
    ):
        self._core = core
        self._context = context
        self._state = ApplicationHostState.CREATED

        self._adapter = None
        self._health_service = None
        self._module_service = None
        self._organisation_service = None
        self._dispatcher = None

    @property
    def state(self):
        return self._state

    @property
    def dispatcher(self):
        if self._state != ApplicationHostState.READY:
            raise ApplicationHostError(
                "System Platform Application Host is not ready"
            )

        return self._dispatcher

    @property
    def adapter(self):
        if self._state != ApplicationHostState.READY:
            raise ApplicationHostError(
                "System Platform Application Host is not ready"
            )

        return self._adapter

    def initialize(self):
        if self._state == ApplicationHostState.READY:
            return self

        self._state = ApplicationHostState.INITIALIZING

        try:
            if self._core is None:
                raise ApplicationHostError(
                    "Core instance is required"
                )

            user = None

            if self._context is not None:
                user = self._context.user

            # ----------------------------------------------------
            # Core boundary
            # ----------------------------------------------------

            self._adapter = CoreAdapter(
                core=self._core,
                user=user,
            )

            # ----------------------------------------------------
            # System Platform services
            # ----------------------------------------------------

            self._health_service = SystemPlatformHealthService()

            self._module_service = ModuleAdministrationService(
                self._adapter
            )

            self._organisation_service = (
                OrganisationAdministrationService(
                    self._adapter
                )
            )

            # ----------------------------------------------------
            # API dispatcher
            # ----------------------------------------------------

            self._dispatcher = ApiDispatcher(
                self._module_service,
                self._organisation_service,
                self._health_service,
            )

            self._state = ApplicationHostState.READY

            return self

        except Exception:
            self._state = ApplicationHostState.FAILED

            self._adapter = None
            self._health_service = None
            self._module_service = None
            self._organisation_service = None
            self._dispatcher = None

            raise
