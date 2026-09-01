import pytest

from phoenix_pca_company_platform.company_api_dispatch import (
    CompanyApiDispatcher,
    CompanyApiDispatchError,
    create_company_api_dispatcher,
)

from phoenix_pca_company_platform.company_api_response import (
    CompanyApiResponseBoundary,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpRequest,
    create_company_application_http_adapter,
)


def make_user(
    organisation_id=501,
):

    return {
        "user_id": 101,
        "organisation_id": organisation_id,
        "identity_scope": "COMPANY",
    }


def make_request(
    method="GET",
    path="/api/pca/settings",
    organisation_id=501,
):

    return CompanyApplicationHttpRequest(
        method=method,
        path=path,
        user=make_user(
            organisation_id
        ),
    )


def make_dispatcher(
    response_boundary=None,
):

    adapter = (
        create_company_application_http_adapter()
    )

    return create_company_api_dispatcher(
        adapter,
        response_boundary=response_boundary,
    )


def test_dispatcher_creates_response_boundary():

    dispatcher = make_dispatcher()

    assert isinstance(
        dispatcher.response_boundary,
        CompanyApiResponseBoundary,
    )


def test_custom_response_boundary_is_preserved():

    boundary = (
        CompanyApiResponseBoundary()
    )

    dispatcher = make_dispatcher(
        response_boundary=boundary
    )

    assert (
        dispatcher.response_boundary
        is boundary
    )


def test_settings_list_returns_http_response():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request()
    )

    assert response.status_code == 200
    assert "settings" in response.body


def test_settings_get_returns_http_response():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert response.status_code == 200
    assert "setting" in response.body


def test_not_found_is_normalized():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/not-found"
        )
    )

    assert response.status_code == 404
    assert (
        response.body["error"]["code"]
        == "ROUTE_NOT_FOUND"
    )


def test_unknown_setting_is_normalized():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/not_a_real_setting"
        )
    )

    assert response.status_code == 404
    assert (
        response.body["error"]["code"]
        == "SETTING_NOT_FOUND"
    )


def test_invalid_setting_is_normalized():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/"
        )
    )

    assert response.status_code in (
        400,
        404,
    )


def test_company_identity_is_preserved():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency",
            organisation_id=501,
        )
    )

    assert response.status_code == 200

    setting = (
        response.body["setting"]
    )

    assert setting.organisation_id == 501


def test_second_company_remains_isolated():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency",
            organisation_id=502,
        )
    )

    assert response.status_code == 200

    setting = (
        response.body["setting"]
    )

    assert setting.organisation_id == 502


def test_platform_identity_can_be_forwarded():

    request = CompanyApplicationHttpRequest(
        method="GET",
        path="/api/pca/settings/default_currency",
        user={
            "user_id": 1,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        },
    )

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        request
    )

    assert response.status_code == 200

    assert (
        response.body["setting"]
        .organisation_id
        == 501
    )


def test_response_boundary_contains_unexpected_errors():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="PATCH",
            path="/api/pca/settings",
        )
    )

    assert response.status_code == 404
    assert (
        response.body["error"]["code"]
        == "ROUTE_NOT_FOUND"
    )


def test_dispatcher_does_not_authenticate():

    dispatcher = make_dispatcher()

    assert not hasattr(
        dispatcher,
        "authenticate",
    )

    assert not hasattr(
        dispatcher,
        "login",
    )


def test_dispatcher_does_not_authorize():

    dispatcher = make_dispatcher()

    assert not hasattr(
        dispatcher,
        "authorize",
    )

    assert not hasattr(
        dispatcher,
        "has_permission",
    )


def test_dispatcher_has_no_database():

    dispatcher = make_dispatcher()

    assert not hasattr(
        dispatcher,
        "database",
    )

    assert not hasattr(
        dispatcher,
        "connection",
    )

    assert not hasattr(
        dispatcher,
        "db",
    )


def test_response_boundary_is_composition_only():

    dispatcher = make_dispatcher()

    assert (
        dispatcher.response_boundary
        is not None
    )


def test_factory_returns_dispatcher():

    dispatcher = make_dispatcher()

    assert isinstance(
        dispatcher,
        CompanyApiDispatcher,
    )


def test_dispatcher_requires_http_adapter():

    with pytest.raises(
        CompanyApiDispatchError
    ):

        CompanyApiDispatcher(
            None
        )


def test_dispatcher_returns_no_python_exception_for_missing_setting():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/unknown"
        )
    )

    assert response.status_code == 404
    assert isinstance(
        response.body,
        dict,
    )


def test_error_response_has_stable_shape():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/unknown"
        )
    )

    assert "error" in response.body
    assert "code" in response.body["error"]
    assert "message" in response.body["error"]


def test_success_response_has_stable_shape():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert response.status_code == 200
    assert "setting" in response.body


def test_dispatch_has_single_response_boundary():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request()
    )

    assert response is not None
    assert hasattr(
        response,
        "status_code",
    )
    assert hasattr(
        response,
        "body",
    )

