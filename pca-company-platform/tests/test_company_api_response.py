import pytest

from phoenix_pca_company_platform.company_api_errors import (
    CompanyApiErrorResponse,
    map_company_api_error,
)

from phoenix_pca_company_platform.company_api_response import (
    CompanyApiResponseBoundary,
    CompanyApiResponseError,
    create_company_api_response_boundary,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpResponse,
)


def test_error_mapping_returns_response():

    result = map_company_api_error(
        ValueError("bad request")
    )

    assert isinstance(
        result,
        CompanyApiErrorResponse,
    )


def test_unknown_error_maps_to_500():

    result = map_company_api_error(
        RuntimeError("unexpected")
    )

    assert result.status == 500
    assert result.code == "INTERNAL_ERROR"


def test_validation_error_maps_to_400():

    error = type(
        "OperationalSettingValidationError",
        (Exception,),
        {},
    )("invalid")

    result = map_company_api_error(
        error
    )

    assert result.status == 400
    assert result.code == "INVALID_REQUEST"


def test_not_found_maps_to_404():

    error = type(
        "OperationalSettingNotFoundError",
        (Exception,),
        {},
    )("missing")

    result = map_company_api_error(
        error
    )

    assert result.status == 404
    assert result.code == "SETTING_NOT_FOUND"


def test_context_error_maps_to_400():

    error = type(
        "OperationalSettingsContextError",
        (Exception,),
        {},
    )("invalid context")

    result = map_company_api_error(
        error
    )

    assert result.status == 400
    assert result.code == "INVALID_COMPANY_CONTEXT"


def test_boundary_creation():

    boundary = (
        CompanyApiResponseBoundary()
    )

    assert boundary is not None


def test_factory():

    boundary = (
        create_company_api_response_boundary()
    )

    assert isinstance(
        boundary,
        CompanyApiResponseBoundary,
    )


def test_success_response():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.success(
        {"status": "OK"}
    )

    assert isinstance(
        response,
        CompanyApplicationHttpResponse,
    )

    assert response.status_code == 200
    assert response.body["status"] == "OK"


def test_success_custom_status():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.success(
        {"created": True},
        status=201,
    )

    assert response.status_code == 201


def test_success_content_type():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.success(
        {}
    )

    assert (
        response.headers["Content-Type"]
        == "application/json"
    )


def test_error_response():

    boundary = (
        CompanyApiResponseBoundary()
    )

    error = type(
        "OperationalSettingNotFoundError",
        (Exception,),
        {},
    )("missing setting")

    response = boundary.error(
        error
    )

    assert response.status_code == 404
    assert (
        response.body["error"]["code"]
        == "SETTING_NOT_FOUND"
    )


def test_error_message():

    boundary = (
        CompanyApiResponseBoundary()
    )

    error = type(
        "OperationalSettingValidationError",
        (Exception,),
        {},
    )("invalid value")

    response = boundary.error(
        error
    )

    assert (
        response.body["error"]["message"]
        == "invalid value"
    )


def test_execute_success():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.execute(
        lambda: {
            "status": "READY"
        }
    )

    assert response.status_code == 200
    assert (
        response.body["status"]
        == "READY"
    )


def test_execute_tuple_response():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.execute(
        lambda: (
            201,
            {"created": True},
        )
    )

    assert response.status_code == 201
    assert (
        response.body["created"]
        is True
    )


def test_execute_existing_response():

    boundary = (
        CompanyApiResponseBoundary()
    )

    existing = CompanyApplicationHttpResponse(
        204,
        {},
    )

    response = boundary.execute(
        lambda: existing
    )

    assert response is existing


def test_execute_translates_exception():

    boundary = (
        CompanyApiResponseBoundary()
    )

    error = type(
        "OperationalSettingNotFoundError",
        (Exception,),
        {},
    )("missing")

    response = boundary.execute(
        lambda: (_ for _ in ()).throw(error)
    )

    assert response.status_code == 404


def test_execute_unknown_exception():

    boundary = (
        CompanyApiResponseBoundary()
    )

    response = boundary.execute(
        lambda: (_ for _ in ()).throw(
            RuntimeError("failure")
        )
    )

    assert response.status_code == 500
    assert (
        response.body["error"]["code"]
        == "INTERNAL_ERROR"
    )


def test_execute_requires_operation():

    boundary = (
        CompanyApiResponseBoundary()
    )

    with pytest.raises(
        CompanyApiResponseError
    ):

        boundary.execute(None)


def test_no_authentication():

    boundary = (
        CompanyApiResponseBoundary()
    )

    assert not hasattr(
        boundary,
        "authenticate",
    )

    assert not hasattr(
        boundary,
        "login",
    )


def test_no_authorization():

    boundary = (
        CompanyApiResponseBoundary()
    )

    assert not hasattr(
        boundary,
        "authorize",
    )

    assert not hasattr(
        boundary,
        "has_permission",
    )


def test_no_database():

    boundary = (
        CompanyApiResponseBoundary()
    )

    assert not hasattr(
        boundary,
        "database",
    )

    assert not hasattr(
        boundary,
        "connection",
    )

    assert not hasattr(
        boundary,
        "db",
    )
