"""
Phoenix System Platform
Application HTTP Integration Adapter V1.0.

Controlled boundary between the existing Phoenix HTTP
application and System Platform.

This adapter does not own:

- HTTP server lifecycle
- authentication
- authorization
- database access
- Core authority
- System Platform business logic
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .api.dispatch import (
    ApiDispatchError,
    DispatchContext,
    RouteNotFoundError,
)
from .application_host import SystemPlatformApplicationHost
from .core_adapter import CoreAdapter
from .errors import (
    CoreBoundaryError,
    PlatformAuthorizationError,
)


class ApplicationHttpIntegrationError(RuntimeError):
    """Base HTTP integration error."""


@dataclass(frozen=True)
class HttpResponse:
    """
    Transport-neutral HTTP response.

    The existing Phoenix HTTP layer remains responsible for
    converting this object into an actual HTTP response.
    """

    status: int
    payload: Mapping[str, Any]


class ApplicationHttpIntegrationAdapter:
    """
    Translate authenticated application requests into
    System Platform dispatcher calls.

    The adapter owns transport translation only.
    """

    def __init__(
        self,
        host: SystemPlatformApplicationHost,
    ):
        if host is None:
            raise ApplicationHttpIntegrationError(
                "System Platform Application Host is required."
            )

        self._host = host

    @property
    def host(self):
        return self._host

    def handle(
        self,
        method: str,
        path: str,
        user: Mapping[str, Any],
        body: Optional[Mapping[str, Any]] = None,
        path_parameters: Optional[Mapping[str, Any]] = None,
        query_parameters: Optional[Mapping[str, Any]] = None,
    ) -> HttpResponse:
        """
        Handle one already-authenticated application request.

        Authentication is deliberately outside this adapter.
        """

        if user is None:
            return HttpResponse(
                status=401,
                payload={
                    "error": "Authenticated Core user is required."
                },
            )

        if not isinstance(user, Mapping):
            return HttpResponse(
                status=400,
                payload={
                    "error": "Invalid authenticated user context."
                },
            )

        if self._host.state != "READY":
            return HttpResponse(
                status=503,
                payload={
                    "error": "System Platform is not ready."
                },
            )

        context = DispatchContext(
            user=user,
            body=body,
            path_parameters=path_parameters,
            query_parameters=query_parameters,
        )

        try:
            result = self._host.dispatcher.dispatch(
                method,
                path,
                context,
            )

            return HttpResponse(
                status=200,
                payload={
                    "ok": True,
                    "data": result,
                },
            )

        except RouteNotFoundError:
            return HttpResponse(
                status=404,
                payload={
                    "error": "System Platform route not found."
                },
            )

        except PlatformAuthorizationError:
            return HttpResponse(
                status=403,
                payload={
                    "error": "System Platform authorization denied."
                },
            )

        except CoreBoundaryError:
            return HttpResponse(
                status=503,
                payload={
                    "error": "Phoenix Core boundary failure."
                },
            )

        except ApiDispatchError:
            return HttpResponse(
                status=500,
                payload={
                    "error": "System Platform dispatch failure."
                },
            )

        except (KeyError, TypeError, ValueError):
            return HttpResponse(
                status=400,
                payload={
                    "error": "Invalid System Platform request."
                },
            )

        except Exception:
            return HttpResponse(
                status=500,
                payload={
                    "error": "System Platform request failed."
                },
            )


def create_http_adapter(
    host: SystemPlatformApplicationHost,
) -> ApplicationHttpIntegrationAdapter:
    """
    Construct the controlled HTTP integration adapter.
    """

    return ApplicationHttpIntegrationAdapter(host)
