import pytest

from phoenix_pca_company_platform.company_application import (
    CompanyApplication,
    create_company_application,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpRequest,
)

from phoenix_pca_company_platform.company_api_dispatch import (
    CompanyApiDispatcher,
)

from phoenix_pca_company_platform.company_api_validation import (
    CompanyApiRequestValidator,
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


def make_application():
    return create_company_application()


def test_application_creation():

    application = make_application()

    assert isinstance(
        application,
        CompanyApplication,
    )


def test_factory_returns_application():

    application = create_company_application()

    assert isinstance(
        application,
        CompanyApplication,
    )


def test_dispatcher_is_composed():

    application = make_application()

    assert isinstance(
        application.dispatcher,
        CompanyApiDispatcher,
    )


def test_request_validator_is_composed():

    application = make_application()

    assert isinstance(
        application.request_validator,
        CompanyApiRequestValidator,
    )


def test_valid_settings_list_request():

    application = make_application()

    response = application.handle(
        make_request()
    )

    assert response.status_code == 200
    assert "settings" in response.body


def test_valid_settings_get_request():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert response.status_code == 200
    assert "setting" in response.body


def test_company_identity_reaches_service():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/settings/timezone",
            user=make_user(
                organisation_id=501
            ),
        )
    )

    assert response.status_code == 200

    setting = response.body["setting"]

    assert setting.organisation_id == 501


def test_second_company_remains_isolated():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/settings/timezone",
            user=make_user(
                organisation_id=502
            ),
        )
    )

    assert response.status_code == 200

    setting = response.body["setting"]

    assert setting.organisation_id == 502


def test_platform_identity_is_preserved():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/settings/timezone",
            user=make_user(
                organisation_id=501,
                identity_scope="PLATFORM",
            ),
        )
    )

    assert response.status_code == 200

    setting = response.body["setting"]

    assert setting.organisation_id == 501


def test_invalid_method_returns_400():

    application = make_application()

    response = application.handle(
        make_request(
            method="TRACE"
        )
    )

    assert response.status_code == 400


def test_invalid_path_returns_400():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/core/settings"
        )
    )

    assert response.status_code == 400


def test_missing_identity_returns_400():

    application = make_application()

    request = make_request()

    request._user = None

    response = application.handle(
        request
    )

    assert response.status_code == 400


def test_missing_user_id_returns_400():

    application = make_application()

    response = application.handle(
        make_request(
            user={
                "organisation_id": 501,
                "identity_scope": "COMPANY",
            }
        )
    )

    assert response.status_code == 400


def test_missing_organisation_returns_400():

    application = make_application()

    response = application.handle(
        make_request(
            user={
                "user_id": 101,
                "identity_scope": "COMPANY",
            }
        )
    )

    assert response.status_code == 400


def test_unknown_pca_route_returns_404():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/not-found"
        )
    )

    assert response.status_code == 404


def test_query_string_returns_400():

    application = make_application()

    response = application.handle(
        make_request(
            path="/api/pca/settings?x=1"
        )
    )

    assert response.status_code == 400


def test_application_does_not_authenticate():

    application = make_application()

    assert not hasattr(
        application,
        "authenticate",
    )

    assert not hasattr(
        application,
        "login",
    )


def test_application_does_not_authorize():

    application = make_application()

    assert not hasattr(
        application,
        "authorize",
    )

    assert not hasattr(
        application,
        "has_permission",
    )


def test_application_has_no_database():

    application = make_application()

    assert not hasattr(
        application,
        "database",
    )

    assert not hasattr(
        application,
        "connection",
    )

    assert not hasattr(
        application,
        "db",
    )


def test_custom_validator_is_preserved():

    validator = CompanyApiRequestValidator()

    application = create_company_application(
        request_validator=validator
    )

    assert (
        application.request_validator
        is validator
    )


def test_host_is_optional():

    application = make_application()

    assert application.host is None


def test_end_to_end_response_object():

    application = make_application()

    response = application.handle(
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


def test_application_is_framework_neutral():

    application = make_application()

    assert not hasattr(
        application,
        "flask",
    )

    assert not hasattr(
        application,
        "fastapi",
    )

    assert not hasattr(
        application,
        "django",
    )
