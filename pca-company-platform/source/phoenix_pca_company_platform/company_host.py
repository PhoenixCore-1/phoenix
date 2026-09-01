"""
Phoenix PCA Company Platform
Company Host / Bootstrap V1.0.

Framework-neutral PCA composition boundary.

The host owns construction and lifecycle only.

It does not own:

- authentication
- authorization
- platform licensing
- platform provisioning
- global platform configuration
- Core database access
- business-module domain logic

Phoenix Core remains authoritative for identity,
authentication and authorization.

The Phoenix Platform Control Plane remains authoritative
for platform-wide concerns.

PCA Company Platform operates at company scope.
"""

from typing import Any, Mapping, Optional

from .company_runtime_context import (
    CompanyRuntimeContext,
    CompanyRuntimeContextError,
)

from .company_operational_settings import (
    CompanyOperationalSettingsService,
    InMemoryCompanyOperationalSettingsProvider,
)


class CompanyHostError(RuntimeError):
    """Base PCA Company Host error."""


class CompanyHostState:
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    FAILED = "FAILED"


class PcaCompanyHost:
    """
    Framework-neutral PCA Company Platform bootstrap host.

    The host composes the PCA runtime context and future
    PCA services.

    It deliberately does not authenticate, authorize,
    or access a database.
    """

    def __init__(
        self,
        user: Optional[Mapping[str, Any]] = None,
        runtime_context: Optional[CompanyRuntimeContext] = None,
    ):
        self._user = user
        self._runtime_context = runtime_context

        self._state = CompanyHostState.CREATED

        self._services = {}
        self._company_context = None

        # ------------------------------------------------
        # Operational Settings provider
        #
        # Persistence remains outside the PCA Host.
        # The default provider is intentionally in-memory
        # until a persistence adapter is supplied.
        # ------------------------------------------------
        self._operational_settings_provider = (
            InMemoryCompanyOperationalSettingsProvider()
        )

    @property
    def state(self):
        return self._state

    @property
    def runtime_context(self):
        if self._state != CompanyHostState.READY:
            raise CompanyHostError(
                "PCA Company Host is not ready."
            )

        return self._company_context

    @property
    def services(self):
        if self._state != CompanyHostState.READY:
            raise CompanyHostError(
                "PCA Company Host is not ready."
            )

        return dict(self._services)

    def initialize(self):
        """
        Initialize the PCA company runtime.

        Existing runtime context is accepted when supplied.
        Otherwise it is constructed from the authenticated
        Core user.

        PCA does not create or replace identity.
        """

        if self._state == CompanyHostState.READY:
            return self

        self._state = CompanyHostState.INITIALIZING

        try:

            if self._runtime_context is not None:

                if not isinstance(
                    self._runtime_context,
                    CompanyRuntimeContext,
                ):
                    raise CompanyHostError(
                        "Invalid PCA Company Runtime Context."
                    )

                context = self._runtime_context

            else:

                if self._user is None:
                    raise CompanyHostError(
                        "Authenticated Core user is required."
                    )

                context = CompanyRuntimeContext(
                    self._user
                )

            self._company_context = context

            # ------------------------------------------------
            # PCA SERVICE COMPOSITION
            # ------------------------------------------------
            #
            # Services receive the immutable company runtime
            # context indirectly through the Host lifecycle.
            #
            # PCA does not authenticate, authorize, license,
            # provision, or access the Core database.
            # ------------------------------------------------

            operational_settings_service = (
                CompanyOperationalSettingsService(
                    self._operational_settings_provider
                )
            )

            self._services = {
                "operational_settings":
                    operational_settings_service,
            }

            self._state = CompanyHostState.READY

            return self

        except (
            CompanyRuntimeContextError,
            CompanyHostError,
        ):
            self._state = CompanyHostState.FAILED
            self._company_context = None
            self._services = {}
            raise

        except Exception as exc:

            self._state = CompanyHostState.FAILED
            self._company_context = None
            self._services = {}

            raise CompanyHostError(
                "PCA Company Host initialization failed."
            ) from exc

    def has_service(self, name: str) -> bool:

        if self._state != CompanyHostState.READY:
            raise CompanyHostError(
                "PCA Company Host is not ready."
            )

        return name in self._services

    def register_service(
        self,
        name: str,
        service: Any,
    ):
        """
        Register a PCA service.

        Service registration is composition only.
        """

        if self._state != CompanyHostState.READY:
            raise CompanyHostError(
                "PCA Company Host is not ready."
            )

        if not name:
            raise CompanyHostError(
                "Service name is required."
            )

        if service is None:
            raise CompanyHostError(
                "Service instance is required."
            )

        self._services[name] = service

        return service

