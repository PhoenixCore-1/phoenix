"""
Phoenix PCA Company Platform
Company API Dispatch V1.0.

Dispatches validated company requests through the PCA
Application Bridge and normalizes results through the
PCA API Response Boundary.

Authentication, authorization and database access remain
outside PCA.
"""

from .company_api_routes import (
    find_company_api_route,
)

from .company_api_response import (
    CompanyApiResponseBoundary,
)

from .company_api_validation import (
    CompanyApiRequestValidator,
)

from .company_application_http import (
    CompanyApplicationHttpRequest,
)


class CompanyApiDispatchError(RuntimeError):
    """PCA API dispatch error."""


class CompanyApiDispatcher:

    def __init__(
        self,
        http_adapter,
        response_boundary=None,
        request_validator=None,
    ):

        if http_adapter is None:
            raise CompanyApiDispatchError(
                "HTTP adapter is required."
            )

        self._http_adapter = http_adapter

        self._response_boundary = (
            response_boundary
            if response_boundary is not None
            else CompanyApiResponseBoundary()
        )

        self._request_validator = (
            request_validator
            if request_validator is not None
            else CompanyApiRequestValidator()
        )

    @property
    def http_adapter(self):
        return self._http_adapter

    @property
    def response_boundary(self):
        return self._response_boundary

    @property
    def request_validator(self):
        return self._request_validator

    def dispatch(
        self,
        request: CompanyApplicationHttpRequest,
    ):

        return self._response_boundary.execute(
            lambda: self._dispatch(
                request
            )
        )

    def _dispatch(
        self,
        request: CompanyApplicationHttpRequest,
    ):

        validated = (
            self._request_validator.validate(
                request
            )
        )

        route = find_company_api_route(
            validated.request.method,
            validated.request.path,
        )

        if route is None:

            return (
                404,
                {
                    "error": {
                        "code": "ROUTE_NOT_FOUND",
                        "message":
                            "PCA route not found.",
                    }
                },
            )

        bridge = (
            self._http_adapter.create_bridge(
                validated.request
            )
        )

        service = bridge.get_service(
            route.service
        )

        if route.service == "operational_settings":

            if route.operation == "list":

                values = service.get_all(
                    bridge.runtime_context
                )

                return (
                    200,
                    {
                        "settings": values,
                    },
                )

            if route.operation == "get":

                key = validated.request.path.rsplit(
                    "/",
                    1,
                )[-1]

                result = service.get(
                    bridge.runtime_context,
                    key,
                )

                return (
                    200,
                    {
                        "setting": result,
                    },
                )

        raise CompanyApiDispatchError(
            "Unsupported PCA API operation."
        )


def create_company_api_dispatcher(
    http_adapter,
    response_boundary=None,
    request_validator=None,
):

    return CompanyApiDispatcher(
        http_adapter,
        response_boundary=response_boundary,
        request_validator=request_validator,
    )
