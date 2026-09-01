"""
Phoenix PCA Company Platform
Company Application Bridge V1.0.

Framework-neutral boundary between an authenticated
application request and the PCA Company Platform.

The bridge:

- preserves Core identity
- requires a CompanyRuntimeContext
- constructs the PCA Company Host
- exposes company-scoped services
- does not authenticate
- does not authorize
- does not license
- does not access the Core database
- does not provision organisations
- does not create organisation/branch/location masters
"""

from typing import Any, Mapping, Optional

from .company_runtime_context import (
    CompanyRuntimeContext,
    CompanyRuntimeContextError,
)

from .company_host import (
    CompanyHostError,
    CompanyHostState,
    PcaCompanyHost,
)


class CompanyApplicationBridgeError(
    RuntimeError
):
    """Base PCA application bridge error."""


class CompanyApplicationRequestError(
    CompanyApplicationBridgeError
):
    """Invalid application request."""


class CompanyApplicationBridge:
    """
    PCA application composition boundary.

    The bridge accepts an already authenticated Core
    identity or an existing CompanyRuntimeContext.

    It does not perform authentication or authorization.
    """

    def __init__(
        self,
        user: Optional[Mapping[str, Any]] = None,
        runtime_context: Optional[
            CompanyRuntimeContext
        ] = None,
    ):

        self._user = user
        self._runtime_context = runtime_context
        self._host = None

    @property
    def host(self):

        return self._host

    @property
    def runtime_context(self):

        if self._host is None:
            raise CompanyApplicationBridgeError(
                "PCA application bridge is not initialized."
            )

        return self._host.runtime_context

    @property
    def services(self):

        if self._host is None:
            raise CompanyApplicationBridgeError(
                "PCA application bridge is not initialized."
            )

        return self._host.services

    @property
    def state(self):

        if self._host is None:
            return CompanyHostState.CREATED

        return self._host.state

    def initialize(self):

        if self._host is not None:

            if (
                self._host.state
                == CompanyHostState.READY
            ):
                return self

        try:

            if (
                self._runtime_context is not None
                and not isinstance(
                    self._runtime_context,
                    CompanyRuntimeContext,
                )
            ):
                raise CompanyApplicationRequestError(
                    "Invalid CompanyRuntimeContext."
                )

            self._host = PcaCompanyHost(
                user=self._user,
                runtime_context=self._runtime_context,
            )

            self._host.initialize()

            return self

        except (
            CompanyApplicationRequestError,
            CompanyRuntimeContextError,
            CompanyHostError,
        ):

            self._host = None
            raise

        except Exception as exc:

            self._host = None

            raise CompanyApplicationBridgeError(
                "PCA application bridge initialization failed."
            ) from exc

    def get_service(
        self,
        name: str,
    ):

        if self._host is None:
            raise CompanyApplicationBridgeError(
                "PCA application bridge is not initialized."
            )

        if not isinstance(name, str):
            raise CompanyApplicationRequestError(
                "Service name must be a string."
            )

        if not name.strip():
            raise CompanyApplicationRequestError(
                "Service name is required."
            )

        if not self._host.has_service(name):
            raise CompanyApplicationRequestError(
                f"PCA service is not available: {name}"
            )

        return self._host.services[name]

    def get_company_context(self):

        return self.runtime_context

    def is_ready(self):

        return (
            self._host is not None
            and self._host.state
            == CompanyHostState.READY
        )


def create_company_application_bridge(
    user: Optional[Mapping[str, Any]] = None,
    runtime_context: Optional[
        CompanyRuntimeContext
    ] = None,
):

    return CompanyApplicationBridge(
        user=user,
        runtime_context=runtime_context,
    )
