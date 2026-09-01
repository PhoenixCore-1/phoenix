"""
Phoenix PCA Company Platform
Company API Routes V1.0.

Defines the PCA company-scoped API surface.

Routes are declarations only.
Authentication and authorization remain outside PCA.
"""

from dataclasses import dataclass


class CompanyApiRouteError(RuntimeError):
    """PCA API route definition error."""


@dataclass(frozen=True)
class CompanyApiRoute:
    method: str
    path: str
    service: str
    operation: str


COMPANY_API_ROUTES = (
    CompanyApiRoute(
        "GET",
        "/api/pca/settings",
        "operational_settings",
        "list",
    ),
    CompanyApiRoute(
        "GET",
        "/api/pca/settings/{key}",
        "operational_settings",
        "get",
    ),
)


def list_company_api_routes():
    return COMPANY_API_ROUTES


def find_company_api_route(
    method: str,
    path: str,
):

    if not isinstance(method, str):
        raise CompanyApiRouteError(
            "HTTP method must be a string."
        )

    if not isinstance(path, str):
        raise CompanyApiRouteError(
            "HTTP path must be a string."
        )

    method = method.upper()

    for route in COMPANY_API_ROUTES:

        if route.method != method:
            continue

        if route.path == path:
            return route

        if route.path.endswith("/{key}"):

            prefix = route.path[:-len("/{key}")]

            if (
                path.startswith(prefix + "/")
                and path[len(prefix) + 1:]
                and "/" not in path[len(prefix) + 1:]
            ):
                return route

    return None

