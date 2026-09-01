"""
Phoenix PCA Company Platform
Application Entry Point V1.0.

Authoritative PCA application composition boundary.

The application composes the existing PCA HTTP, validation,
bridge, dispatcher and response layers.

Authentication and authorization remain owned by Phoenix Core.
Platform-wide concerns remain outside PCA.
"""

from typing import Optional

from .company_api_dispatch import (
    CompanyApiDispatcher,
    create_company_api_dispatcher,
)

from .company_application_http import (
    CompanyApplicationHttpRequest,
    create_company_application_http_adapter,
)

from .company_api_response import (
    CompanyApiResponseBoundary,
)

from .company_api_validation import (
    CompanyApiRequestValidator,
)

from .company_host import (
    PcaCompanyHost,
)


class CompanyApplicationError(RuntimeError):
    """Base PCA application error."""


class CompanyApplication:

    def __init__(
        self,
        host: Optional[PcaCompanyHost] = None,
        http_adapter=None,
        request_validator=None,
        response_boundary=None,
        dispatcher=None,
    ):

        self._host = host

        self._http_adapter = (
            http_adapter
            if http_adapter is not None
            else create_company_application_http_adapter()
        )

        self._request_validator = (
            request_validator
            if request_validator is not None
            else CompanyApiRequestValidator()
        )

        self._response_boundary = (
            response_boundary
            if response_boundary is not None
            else CompanyApiResponseBoundary()
        )

        self._dispatcher = (
            dispatcher
            if dispatcher is not None
            else create_company_api_dispatcher(
                self._http_adapter,
                response_boundary=self._response_boundary,
                request_validator=self._request_validator,
            )
        )

    @property
    def host(self):

        return self._host

    @property
    def http_adapter(self):

        return self._http_adapter

    @property
    def request_validator(self):

        return self._request_validator

    @property
    def response_boundary(self):

        return self._response_boundary

    @property
    def dispatcher(self):

        return self._dispatcher

    def handle(
        self,
        request: CompanyApplicationHttpRequest,
    ):

        return self._dispatcher.dispatch(
            request
        )


def create_company_application(
    host=None,
    http_adapter=None,
    request_validator=None,
    response_boundary=None,
    dispatcher=None,
):

    return CompanyApplication(
        host=host,
        http_adapter=http_adapter,
        request_validator=request_validator,
        response_boundary=response_boundary,
        dispatcher=dispatcher,
    )
