"""
Phoenix PCA Company Platform
API Error Boundary V1.0.

Converts known PCA application/domain errors into
stable API error representations.

This layer does not authenticate, authorize, access
the database, or determine platform authority.
"""

from dataclasses import dataclass
from typing import Any

from .company_api_validation import (
    CompanyApiValidationError,
)


@dataclass(frozen=True)
class CompanyApiErrorResponse:
    status: int
    code: str
    message: str


def map_company_api_error(
    error: Exception,
) -> CompanyApiErrorResponse:

    name = type(error).__name__

    if name in (
        "CompanyApplicationHttpRequestError",
        "CompanyApiRouteError",
        "OperationalSettingValidationError",
        "CompanyApiValidationError",
        "CompanyApiMethodValidationError",
        "CompanyApiPathValidationError",
        "CompanyApiIdentityValidationError",
        "CompanyApiContextValidationError",
    ):
        return CompanyApiErrorResponse(
            status=400,
            code="INVALID_REQUEST",
            message=str(error),
        )

    if name in (
        "OperationalSettingNotFoundError",
    ):
        return CompanyApiErrorResponse(
            status=404,
            code="SETTING_NOT_FOUND",
            message=str(error),
        )

    if name in (
        "OperationalSettingsContextError",
    ):
        return CompanyApiErrorResponse(
            status=400,
            code="INVALID_COMPANY_CONTEXT",
            message=str(error),
        )

    if name in (
        "CompanyApplicationBridgeError",
        "CompanyApplicationHttpError",
        "CompanyHostError",
    ):
        return CompanyApiErrorResponse(
            status=500,
            code="PCA_APPLICATION_ERROR",
            message="PCA application processing failed.",
        )

    return CompanyApiErrorResponse(
        status=500,
        code="INTERNAL_ERROR",
        message="Internal PCA application error.",
    )

