"""
Phoenix PCA Company Platform
API Response Boundary V1.0.

Provides stable response construction and controlled
exception translation for PCA API operations.
"""

from typing import Any, Mapping, Optional

from .company_api_errors import (
    CompanyApiErrorResponse,
    map_company_api_error,
)

from .company_application_http import (
    CompanyApplicationHttpResponse,
)


class CompanyApiResponseError(RuntimeError):
    """PCA API response boundary error."""


class CompanyApiResponseBoundary:
    """
    Stable PCA API response boundary.

    Domain and infrastructure exceptions must not leak
    directly through the external application boundary.
    """

    def success(
        self,
        body: Any,
        status: int = 200,
        headers: Optional[
            Mapping[str, str]
        ] = None,
    ):

        return CompanyApplicationHttpResponse(
            status,
            body,
            headers=headers or {
                "Content-Type":
                    "application/json",
            },
        )

    def error(
        self,
        error: Exception,
    ):

        mapped = map_company_api_error(
            error
        )

        return CompanyApplicationHttpResponse(
            mapped.status,
            {
                "error": {
                    "code": mapped.code,
                    "message": mapped.message,
                }
            },
            headers={
                "Content-Type":
                    "application/json",
            },
        )

    def execute(
        self,
        operation,
    ):

        if operation is None:
            raise CompanyApiResponseError(
                "API operation is required."
            )

        try:

            result = operation()

            if isinstance(
                result,
                CompanyApplicationHttpResponse,
            ):
                return result

            if (
                isinstance(result, tuple)
                and len(result) == 2
                and isinstance(result[0], int)
            ):
                return self.success(
                    result[1],
                    status=result[0],
                )

            return self.success(
                result
            )

        except Exception as exc:

            return self.error(
                exc
            )


def create_company_api_response_boundary():

    return CompanyApiResponseBoundary()
