"""
Phoenix PCA Company Platform
Company Application HTTP Boundary V1.0.

Framework-neutral request adapter.

This layer translates an already authenticated application
request into the PCA Application Bridge.

It does not:

- authenticate
- authorize
- perform platform licensing
- access the Core database
- provision organisations
- create organisation masters
- create branch masters
- create location masters
- own the Inventory Item Master
"""

from typing import Any, Mapping, Optional

from .company_application_bridge import (
    CompanyApplicationBridge,
    CompanyApplicationBridgeError,
    CompanyApplicationRequestError,
)

from .company_runtime_context import (
    CompanyRuntimeContext,
)


class CompanyApplicationHttpError(
    RuntimeError
):
    """Base PCA application HTTP error."""


class CompanyApplicationHttpRequestError(
    CompanyApplicationHttpError
):
    """Invalid PCA application HTTP request."""


class CompanyApplicationHttpResponse:
    """
    Framework-neutral HTTP response representation.
    """

    __slots__ = (
        "_status_code",
        "_body",
        "_headers",
    )

    def __init__(
        self,
        status_code: int,
        body: Any,
        headers: Optional[
            Mapping[str, str]
        ] = None,
    ):

        if not isinstance(
            status_code,
            int,
        ):
            raise CompanyApplicationHttpError(
                "HTTP status code must be an integer."
            )

        if status_code < 100 or status_code > 599:
            raise CompanyApplicationHttpError(
                "Invalid HTTP status code."
            )

        object.__setattr__(
            self,
            "_status_code",
            status_code,
        )

        object.__setattr__(
            self,
            "_body",
            body,
        )

        object.__setattr__(
            self,
            "_headers",
            dict(headers or {}),
        )

    @property
    def status_code(self):
        return self._status_code

    @property
    def body(self):
        return self._body

    @property
    def headers(self):
        return dict(self._headers)


class CompanyApplicationHttpRequest:
    """
    Framework-neutral incoming request.

    The user is expected to have already been authenticated
    by Phoenix Core.
    """

    __slots__ = (
        "_method",
        "_path",
        "_user",
        "_runtime_context",
        "_body",
    )

    def __init__(
        self,
        method: str,
        path: str,
        user: Optional[
            Mapping[str, Any]
        ] = None,
        runtime_context: Optional[
            CompanyRuntimeContext
        ] = None,
        body: Any = None,
    ):

        if not isinstance(method, str):
            raise CompanyApplicationHttpRequestError(
                "HTTP method must be a string."
            )

        if not method.strip():
            raise CompanyApplicationHttpRequestError(
                "HTTP method is required."
            )

        if not isinstance(path, str):
            raise CompanyApplicationHttpRequestError(
                "HTTP path must be a string."
            )

        if not path.strip():
            raise CompanyApplicationHttpRequestError(
                "HTTP path is required."
            )

        object.__setattr__(
            self,
            "_method",
            method.upper(),
        )

        object.__setattr__(
            self,
            "_path",
            path,
        )

        object.__setattr__(
            self,
            "_user",
            user,
        )

        object.__setattr__(
            self,
            "_runtime_context",
            runtime_context,
        )

        object.__setattr__(
            self,
            "_body",
            body,
        )

    @property
    def method(self):
        return self._method

    @property
    def path(self):
        return self._path

    @property
    def user(self):
        return self._user

    @property
    def runtime_context(self):
        return self._runtime_context

    @property
    def body(self):
        return self._body


class CompanyApplicationHttpIntegrationAdapter:
    """
    PCA HTTP integration boundary.

    The adapter only creates/initializes the PCA application
    bridge. Actual endpoint routing remains above the service
    layer and below the HTTP framework.
    """

    def __init__(
        self,
        bridge_factory=CompanyApplicationBridge,
    ):

        if bridge_factory is None:
            raise CompanyApplicationHttpError(
                "Bridge factory is required."
            )

        self._bridge_factory = bridge_factory

    @property
    def bridge_factory(self):
        return self._bridge_factory

    def create_bridge(
        self,
        request: CompanyApplicationHttpRequest,
    ):

        if not isinstance(
            request,
            CompanyApplicationHttpRequest,
        ):
            raise CompanyApplicationHttpRequestError(
                "Valid PCA HTTP request is required."
            )

        try:

            bridge = self._bridge_factory(
                user=request.user,
                runtime_context=request.runtime_context,
            )

            bridge.initialize()

            return bridge

        except (
            CompanyApplicationRequestError,
            CompanyApplicationBridgeError,
        ):

            raise

        except Exception as exc:

            raise CompanyApplicationHttpError(
                "PCA application bridge creation failed."
            ) from exc

    def handle(
        self,
        request: CompanyApplicationHttpRequest,
    ):

        bridge = self.create_bridge(
            request
        )

        return CompanyApplicationHttpResponse(
            200,
            {
                "status": "READY",
                "method": request.method,
                "path": request.path,
                "user_id":
                    bridge.runtime_context.user_id,
                "organisation_id":
                    bridge.runtime_context.organisation_id,
                "identity_scope":
                    bridge.runtime_context.identity_scope,
                "company_scope":
                    bridge.runtime_context.company_scope,
                "services":
                    tuple(
                        bridge.services.keys()
                    ),
            },
            headers={
                "Content-Type":
                    "application/json",
            },
        )


def create_company_application_http_adapter():

    return CompanyApplicationHttpIntegrationAdapter()
