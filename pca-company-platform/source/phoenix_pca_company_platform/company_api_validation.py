"""
Phoenix PCA Company Platform
API Request Validation V1.0.

Validates requests entering the PCA application API boundary.

This component does not authenticate, authorize, access a
database, or replace Phoenix Core identity.
"""

from dataclasses import dataclass

from .company_application_http import (
    CompanyApplicationHttpRequest,
)

from .company_runtime_context import (
    CompanyRuntimeContext,
)


class CompanyApiValidationError(ValueError):
    """Base PCA API request validation error."""


class CompanyApiMethodValidationError(
    CompanyApiValidationError
):
    """Invalid or unsupported HTTP method."""


class CompanyApiPathValidationError(
    CompanyApiValidationError
):
    """Invalid PCA API path."""


class CompanyApiIdentityValidationError(
    CompanyApiValidationError
):
    """Missing or invalid Core identity."""


class CompanyApiContextValidationError(
    CompanyApiValidationError
):
    """Invalid company runtime context."""


@dataclass(frozen=True)
class CompanyApiValidatedRequest:
    request: CompanyApplicationHttpRequest
    runtime_context: CompanyRuntimeContext


class CompanyApiRequestValidator:
    """
    PCA API request validation boundary.

    Authentication is assumed to have already occurred in Core.
    Authorization remains owned by Core.
    """

    ALLOWED_METHODS = frozenset(
        {
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
    )

    PCA_PREFIX = "/api/pca"

    def validate(
        self,
        request,
    ):

        self._validate_request_type(
            request
        )

        self._validate_method(
            request
        )

        self._validate_path(
            request
        )

        self._validate_identity(
            request
        )

        context = CompanyRuntimeContext(
            request.user
        )

        self._validate_context(
            context
        )

        return CompanyApiValidatedRequest(
            request=request,
            runtime_context=context,
        )

    def _validate_request_type(
        self,
        request,
    ):

        if not isinstance(
            request,
            CompanyApplicationHttpRequest,
        ):
            raise CompanyApiValidationError(
                "Valid PCA HTTP request is required."
            )

    def _validate_method(
        self,
        request,
    ):

        method = request.method

        if not isinstance(
            method,
            str,
        ):
            raise CompanyApiMethodValidationError(
                "HTTP method must be a string."
            )

        method = method.upper()

        if method not in self.ALLOWED_METHODS:
            raise CompanyApiMethodValidationError(
                f"Unsupported HTTP method: {method}"
            )

    def _validate_path(
        self,
        request,
    ):

        path = request.path

        if not isinstance(
            path,
            str,
        ):
            raise CompanyApiPathValidationError(
                "API path must be a string."
            )

        if not path:
            raise CompanyApiPathValidationError(
                "API path is required."
            )

        if not path.startswith(
            self.PCA_PREFIX
        ):
            raise CompanyApiPathValidationError(
                "PCA API path is required."
            )

        if "?" in path:
            raise CompanyApiPathValidationError(
                "Query strings are not accepted in "
                "the PCA request path."
            )

        if "//" in path:
            raise CompanyApiPathValidationError(
                "Invalid PCA API path."
            )

    def _validate_identity(
        self,
        request,
    ):

        user = request.user

        if not isinstance(
            user,
            dict,
        ):
            raise CompanyApiIdentityValidationError(
                "Authenticated Core identity is required."
            )

        if user.get("user_id") is None:
            raise CompanyApiIdentityValidationError(
                "Authenticated Core user_id is required."
            )

        if user.get("organisation_id") is None:
            raise CompanyApiIdentityValidationError(
                "Company organisation identity is required."
            )

    def _validate_context(
        self,
        context,
    ):

        if not isinstance(
            context,
            CompanyRuntimeContext,
        ):
            raise CompanyApiContextValidationError(
                "Valid company runtime context is required."
            )

        if context.company_scope != "COMPANY":
            raise CompanyApiContextValidationError(
                "PCA API requires COMPANY scope."
            )

        if context.organisation_id is None:
            raise CompanyApiContextValidationError(
                "PCA API requires company organisation identity."
            )


def create_company_api_request_validator():

    return CompanyApiRequestValidator()
