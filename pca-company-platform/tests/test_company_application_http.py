import pytest

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpError,
    CompanyApplicationHttpIntegrationAdapter,
    CompanyApplicationHttpRequest,
    CompanyApplicationHttpRequestError,
    CompanyApplicationHttpResponse,
    create_company_application_http_adapter,
)

from phoenix_pca_company_platform.company_application_bridge import (
    CompanyApplicationBridge,
)

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
)


def make_user():

    return {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "COMPANY",
    }


def make_request(
    method="GET",
    path="/api/pca",
):

    return CompanyApplicationHttpRequest(
        method=method,
        path=path,
        user=make_user(),
    )


def test_request_requires_method():

    with pytest.raises(
        CompanyApplicationHttpRequestError
    ):

        CompanyApplicationHttpRequest(
            method="",
            path="/api/pca",
            user=make_user(),
        )


def test_request_requires_path():

    with pytest.raises(
        CompanyApplicationHttpRequestError
    ):

        CompanyApplicationHttpRequest(
            method="GET",
            path="",
            user=make_user(),
        )


def test_request_normalizes_method():

    request = CompanyApplicationHttpRequest(
        method="get",
        path="/api/pca",
        user=make_user(),
    )

    assert request.method == "GET"


def test_request_preserves_path():

    request = make_request(
        path="/api/pca/settings"
    )

    assert (
        request.path
        == "/api/pca/settings"
    )


def test_request_preserves_user():

    request = make_request()

    assert request.user == make_user()


def test_response_creation():

    response = CompanyApplicationHttpResponse(
        200,
        {"status": "OK"},
    )

    assert response.status_code == 200
    assert response.body["status"] == "OK"


def test_response_headers():

    response = CompanyApplicationHttpResponse(
        200,
        {},
        headers={
            "Content-Type":
                "application/json",
        },
    )

    assert (
        response.headers["Content-Type"]
        == "application/json"
    )


def test_invalid_response_status():

    with pytest.raises(
        CompanyApplicationHttpError
    ):

        CompanyApplicationHttpResponse(
            99,
            {},
        )


def test_adapter_creation():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    assert adapter is not None


def test_factory():

    adapter = (
        create_company_application_http_adapter()
    )

    assert isinstance(
        adapter,
        CompanyApplicationHttpIntegrationAdapter,
    )


def test_adapter_bridge_factory():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    assert (
        adapter.bridge_factory
        is CompanyApplicationBridge
    )


def test_create_bridge():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    bridge = adapter.create_bridge(
        make_request()
    )

    assert isinstance(
        bridge,
        CompanyApplicationBridge,
    )

    assert bridge.is_ready() is True


def test_bridge_preserves_identity():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    bridge = adapter.create_bridge(
        make_request()
    )

    assert (
        bridge.runtime_context.user_id
        == 101
    )

    assert (
        bridge.runtime_context.organisation_id
        == 501
    )

    assert (
        bridge.runtime_context.identity_scope
        == "COMPANY"
    )

    assert (
        bridge.runtime_context.company_scope
        == "COMPANY"
    )


def test_handle_returns_ready_response():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    response = adapter.handle(
        make_request()
    )

    assert response.status_code == 200
    assert response.body["status"] == "READY"


def test_handle_returns_request_identity():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    response = adapter.handle(
        make_request(
            method="POST",
            path="/api/pca/settings",
        )
    )

    assert response.body["method"] == "POST"
    assert (
        response.body["path"]
        == "/api/pca/settings"
    )

    assert (
        response.body["user_id"]
        == 101
    )

    assert (
        response.body["organisation_id"]
        == 501
    )


def test_handle_exposes_company_scope():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    response = adapter.handle(
        make_request()
    )

    assert (
        response.body["company_scope"]
        == "COMPANY"
    )


def test_handle_exposes_services():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    response = adapter.handle(
        make_request()
    )

    assert (
        "operational_settings"
        in response.body["services"]
    )


def test_invalid_request_rejected():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    with pytest.raises(
        CompanyApplicationHttpRequestError
    ):

        adapter.create_bridge({})


def test_runtime_context_can_be_supplied():

    context = CompanyRuntimeContext(
        make_user()
    )

    request = CompanyApplicationHttpRequest(
        method="GET",
        path="/api/pca",
        runtime_context=context,
    )

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    bridge = adapter.create_bridge(
        request
    )

    assert (
        bridge.runtime_context
        is context
    )


def test_platform_identity_preserves_company_scope():

    request = CompanyApplicationHttpRequest(
        method="GET",
        path="/api/pca",
        user={
            "user_id": 1,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        },
    )

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    bridge = adapter.create_bridge(
        request
    )

    assert (
        bridge.runtime_context.identity_scope
        == "PLATFORM"
    )

    assert (
        bridge.runtime_context.company_scope
        == "COMPANY"
    )


def test_no_authentication():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    assert not hasattr(
        adapter,
        "authenticate",
    )

    assert not hasattr(
        adapter,
        "login",
    )


def test_no_authorization():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    assert not hasattr(
        adapter,
        "authorize",
    )

    assert not hasattr(
        adapter,
        "has_permission",
    )


def test_no_database():

    adapter = (
        CompanyApplicationHttpIntegrationAdapter()
    )

    assert not hasattr(
        adapter,
        "database",
    )

    assert not hasattr(
        adapter,
        "connection",
    )

    assert not hasattr(
        adapter,
        "db",
    )

    assert not hasattr(
        adapter,
        "cursor",
    )
