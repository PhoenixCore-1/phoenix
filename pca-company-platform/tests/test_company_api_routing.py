import pytest

from phoenix_pca_company_platform.company_api_routes import (
    CompanyApiRoute,
    CompanyApiRouteError,
    COMPANY_API_ROUTES,
    find_company_api_route,
    list_company_api_routes,
)

from phoenix_pca_company_platform.company_api_dispatch import (
    CompanyApiDispatchError,
    CompanyApiDispatcher,
    create_company_api_dispatcher,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpRequest,
    create_company_application_http_adapter,
)


def make_user():

    return {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "COMPANY",
    }


def make_request(
    method="GET",
    path="/api/pca/settings",
):

    return CompanyApplicationHttpRequest(
        method=method,
        path=path,
        user=make_user(),
    )


def make_dispatcher():

    adapter = (
        create_company_application_http_adapter()
    )

    return create_company_api_dispatcher(
        adapter
    )


def test_routes_are_defined():

    routes = list_company_api_routes()

    assert routes
    assert routes == COMPANY_API_ROUTES


def test_routes_are_immutable():

    routes = list_company_api_routes()

    assert isinstance(
        routes,
        tuple,
    )


def test_route_type():

    route = COMPANY_API_ROUTES[0]

    assert isinstance(
        route,
        CompanyApiRoute,
    )


def test_settings_list_route():

    route = find_company_api_route(
        "GET",
        "/api/pca/settings",
    )

    assert route is not None
    assert route.service == "operational_settings"
    assert route.operation == "list"


def test_settings_key_route():

    route = find_company_api_route(
        "GET",
        "/api/pca/settings/default_currency",
    )

    assert route is not None
    assert route.service == "operational_settings"
    assert route.operation == "get"


def test_unknown_route():

    assert (
        find_company_api_route(
            "GET",
            "/api/pca/unknown",
        )
        is None
    )


def test_method_must_be_string():

    with pytest.raises(
        CompanyApiRouteError
    ):

        find_company_api_route(
            123,
            "/api/pca/settings",
        )


def test_path_must_be_string():

    with pytest.raises(
        CompanyApiRouteError
    ):

        find_company_api_route(
            "GET",
            123,
        )


def test_dispatcher_creation():

    dispatcher = make_dispatcher()

    assert dispatcher is not None


def test_dispatcher_requires_adapter():

    with pytest.raises(
        CompanyApiDispatchError
    ):

        CompanyApiDispatcher(None)


def test_settings_list_dispatch():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request()
    )

    assert response.status_code == 200
    assert "settings" in response.body


def test_settings_get_dispatch():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert response.status_code == 200
    assert "setting" in response.body


def test_settings_get_returns_company():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    setting = response.body["setting"]

    assert setting.organisation_id == 501


def test_unknown_route_returns_404():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/not-found"
        )
    )

    assert response.status_code == 404


def test_company_identity_reaches_service():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/timezone"
        )
    )

    assert response.status_code == 200
    assert (
        response.body["setting"].organisation_id
        == 501
    )


def test_platform_identity_preserved():

    request = CompanyApplicationHttpRequest(
        method="GET",
        path="/api/pca/settings/timezone",
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
        response.body["setting"].organisation_id
        == 501
    )


def test_dispatcher_has_no_authentication():

    dispatcher = make_dispatcher()

    assert not hasattr(
        dispatcher,
        "authenticate",
    )

    assert not hasattr(
        dispatcher,
        "login",
    )


def test_dispatcher_has_no_authorization():

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


def test_dispatcher_uses_http_boundary():

    dispatcher = make_dispatcher()

    assert (
        dispatcher.http_adapter
        is not None
    )


def test_factory():

    adapter = (
        create_company_application_http_adapter()
    )

    dispatcher = (
        create_company_api_dispatcher(
            adapter
        )
    )

    assert isinstance(
        dispatcher,
        CompanyApiDispatcher,
    )


def test_post_not_accepted_for_get_route():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="POST",
            path="/api/pca/settings",
        )
    )

    assert response.status_code == 404

