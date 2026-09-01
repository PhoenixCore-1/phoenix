import pytest

from phoenix_pca_company_platform.company_api_dispatch import (
    CompanyApiDispatcher,
    CompanyApiDispatchError,
    create_company_api_dispatcher,
)

from phoenix_pca_company_platform.company_api_validation import (
    CompanyApiRequestValidator,
    CompanyApiValidationError,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpRequest,
    create_company_application_http_adapter,
)


def make_user(
    organisation_id=501,
    identity_scope="COMPANY",
):

    return {
        "user_id": 101,
        "organisation_id": organisation_id,
        "identity_scope": identity_scope,
    }


def make_request(
    method="GET",
    path="/api/pca/settings",
    user=None,
):

    if user is None:
        user = make_user()

    return CompanyApplicationHttpRequest(
        method=method,
        path=path,
        user=user,
    )


def make_dispatcher(
    request_validator=None,
):

    adapter = (
        create_company_application_http_adapter()
    )

    return create_company_api_dispatcher(
        adapter,
        request_validator=request_validator,
    )


def test_dispatcher_composes_request_validator():

    dispatcher = make_dispatcher()

    assert isinstance(
        dispatcher.request_validator,
        CompanyApiRequestValidator,
    )


def test_custom_validator_is_preserved():

    validator = CompanyApiRequestValidator()

    dispatcher = make_dispatcher(
        request_validator=validator
    )

    assert (
        dispatcher.request_validator
        is validator
    )


def test_valid_request_reaches_service():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert response.status_code == 200
    assert "setting" in response.body


def test_list_request_reaches_service():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request()
    )

    assert response.status_code == 200
    assert "settings" in response.body


def test_missing_identity_is_rejected_before_service():

    dispatcher = make_dispatcher()

    request = make_request(
        user=None
    )

    request._user = None

    response = dispatcher.dispatch(
        request
    )

    assert response.status_code == 400


def test_missing_user_id_is_rejected_before_service():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            user={
                "organisation_id": 501,
                "identity_scope": "COMPANY",
            }
        )
    )

    assert response.status_code == 400


def test_missing_organisation_is_rejected_before_service():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            user={
                "user_id": 101,
                "identity_scope": "COMPANY",
            }
        )
    )

    assert response.status_code == 400


def test_invalid_method_is_rejected_before_dispatch():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="TRACE"
        )
    )

    assert response.status_code == 400


def test_invalid_path_is_rejected_before_dispatch():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/core/settings"
        )
    )

    assert response.status_code == 400


def test_query_string_is_rejected():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings?x=1"
        )
    )

    assert response.status_code == 400


def test_double_slash_is_rejected():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca//settings"
        )
    )

    assert response.status_code == 400


def test_unknown_valid_pca_route_remains_404():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/not-found"
        )
    )

    assert response.status_code == 404


def test_company_identity_reaches_runtime_context():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency",
            user=make_user(
                organisation_id=501
            ),
        )
    )

    assert response.status_code == 200

    setting = (
        response.body["setting"]
    )

    assert setting.organisation_id == 501


def test_second_company_identity_is_preserved():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/default_currency",
            user=make_user(
                organisation_id=502
            ),
        )
    )

    assert response.status_code == 200

    setting = (
        response.body["setting"]
    )

    assert setting.organisation_id == 502


def test_platform_identity_is_preserved():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            path="/api/pca/settings/timezone",
            user=make_user(
                organisation_id=501,
                identity_scope="PLATFORM",
            ),
        )
    )

    assert response.status_code == 200

    setting = (
        response.body["setting"]
    )

    assert setting.organisation_id == 501


def test_validation_error_has_stable_shape():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="TRACE"
        )
    )

    assert response.status_code == 400
    assert "error" in response.body
    assert "code" in response.body["error"]
    assert "message" in response.body["error"]


def test_validation_occurs_before_route_lookup():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="TRACE",
            path="/api/pca/not-found",
        )
    )

    assert response.status_code == 400


def test_validation_occurs_before_service_resolution():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="TRACE",
            path="/api/pca/settings/default_currency",
        )
    )

    assert response.status_code == 400


def test_validator_can_be_injected():

    class RecordingValidator:

        def __init__(self):

            self.called = False

        def validate(
            self,
            request,
        ):

            self.called = True

            return (
                CompanyApiRequestValidator()
                .validate(request)
            )

    validator = RecordingValidator()

    dispatcher = make_dispatcher(
        request_validator=validator
    )

    response = dispatcher.dispatch(
        make_request()
    )

    assert response.status_code == 200
    assert validator.called is True


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


def test_factory_returns_dispatcher():

    dispatcher = make_dispatcher()

    assert isinstance(
        dispatcher,
        CompanyApiDispatcher,
    )


def test_invalid_request_does_not_escape_as_python_exception():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request(
            method="TRACE"
        )
    )

    assert response.status_code == 400


def test_valid_request_returns_http_response_object():

    dispatcher = make_dispatcher()

    response = dispatcher.dispatch(
        make_request()
    )

    assert hasattr(
        response,
        "status_code",
    )

    assert hasattr(
        response,
        "body",
    )
