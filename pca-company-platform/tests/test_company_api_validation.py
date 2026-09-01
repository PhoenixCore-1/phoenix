import pytest

from phoenix_pca_company_platform.company_api_validation import (
    CompanyApiContextValidationError,
    CompanyApiIdentityValidationError,
    CompanyApiMethodValidationError,
    CompanyApiPathValidationError,
    CompanyApiRequestValidator,
    CompanyApiValidatedRequest,
    CompanyApiValidationError,
    create_company_api_request_validator,
)

from phoenix_pca_company_platform.company_application_http import (
    CompanyApplicationHttpRequest,
)


_DEFAULT_USER = {
    "user_id": 101,
    "organisation_id": 501,
    "identity_scope": "COMPANY",
}

_MISSING = object()


def make_request(
    method="GET",
    path="/api/pca/settings",
    user=_MISSING,
):

    if user is _MISSING:
        user = dict(_DEFAULT_USER)

    return CompanyApplicationHttpRequest(
        method=method,
        path=path,
        user=user,
    )


def test_validator_creation():

    validator = CompanyApiRequestValidator()

    assert validator is not None


def test_factory():

    validator = (
        create_company_api_request_validator()
    )

    assert isinstance(
        validator,
        CompanyApiRequestValidator,
    )


def test_valid_request():

    validator = CompanyApiRequestValidator()

    result = validator.validate(
        make_request()
    )

    assert isinstance(
        result,
        CompanyApiValidatedRequest,
    )

    assert (
        result.runtime_context.organisation_id
        == 501
    )


def test_company_scope():

    validator = CompanyApiRequestValidator()

    result = validator.validate(
        make_request()
    )

    assert (
        result.runtime_context.company_scope
        == "COMPANY"
    )


def test_core_identity_is_preserved():

    request = make_request()

    result = (
        CompanyApiRequestValidator()
        .validate(request)
    )

    assert (
        result.runtime_context.user["user_id"]
        == 101
    )


def test_platform_identity_is_not_replaced():

    request = make_request(
        user={
            "user_id": 1,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        }
    )

    result = (
        CompanyApiRequestValidator()
        .validate(request)
    )

    assert (
        result.runtime_context.identity_scope
        == "PLATFORM"
    )


def test_missing_request_rejected():

    with pytest.raises(
        CompanyApiValidationError
    ):

        CompanyApiRequestValidator().validate(
            None
        )


def test_non_request_rejected():

    with pytest.raises(
        CompanyApiValidationError
    ):

        CompanyApiRequestValidator().validate(
            {}
        )


def test_missing_method_rejected():

    request = make_request()

    request._method = None

    with pytest.raises(
        CompanyApiMethodValidationError
    ):

        CompanyApiRequestValidator().validate(
            request
        )


def test_unsupported_method_rejected():

    with pytest.raises(
        CompanyApiMethodValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                method="TRACE"
            )
        )


def test_method_case_normalization():

    result = (
        CompanyApiRequestValidator()
        .validate(
            make_request(
                method="get"
            )
        )
    )

    assert result is not None


def test_missing_path_rejected():

    request = make_request()

    request._path = None

    with pytest.raises(
        CompanyApiPathValidationError
    ):

        CompanyApiRequestValidator().validate(
            request
        )


def test_empty_path_rejected():

    request = make_request()

    request._path = ""

    with pytest.raises(
        CompanyApiPathValidationError
    ):

        CompanyApiRequestValidator().validate(
            request
        )


def test_non_pca_path_rejected():

    with pytest.raises(
        CompanyApiPathValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                path="/api/core/settings"
            )
        )


def test_query_string_rejected():

    with pytest.raises(
        CompanyApiPathValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                path="/api/pca/settings?x=1"
            )
        )


def test_double_slash_rejected():

    with pytest.raises(
        CompanyApiPathValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                path="/api/pca//settings"
            )
        )


def test_missing_user_rejected():

    with pytest.raises(
        CompanyApiIdentityValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                user=None
            )
        )


def test_missing_user_id_rejected():

    with pytest.raises(
        CompanyApiIdentityValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                user={
                    "organisation_id": 501,
                    "identity_scope": "COMPANY",
                }
            )
        )


def test_missing_organisation_rejected():

    with pytest.raises(
        CompanyApiIdentityValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                user={
                    "user_id": 101,
                    "identity_scope": "COMPANY",
                }
            )
        )


def test_invalid_identity_type_rejected():

    with pytest.raises(
        CompanyApiIdentityValidationError
    ):

        CompanyApiRequestValidator().validate(
            make_request(
                user=[]
            )
        )


def test_platform_identity_does_not_become_company_identity():

    request = make_request(
        user={
            "user_id": 101,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        }
    )

    result = (
        CompanyApiRequestValidator()
        .validate(request)
    )

    assert (
        result.runtime_context.identity_scope
        == "PLATFORM"
    )


def test_no_authentication_method():

    validator = CompanyApiRequestValidator()

    assert not hasattr(
        validator,
        "authenticate",
    )

    assert not hasattr(
        validator,
        "login",
    )


def test_no_authorization_method():

    validator = CompanyApiRequestValidator()

    assert not hasattr(
        validator,
        "authorize",
    )

    assert not hasattr(
        validator,
        "has_permission",
    )


def test_no_database_attribute():

    validator = CompanyApiRequestValidator()

    assert not hasattr(
        validator,
        "database",
    )

    assert not hasattr(
        validator,
        "connection",
    )

    assert not hasattr(
        validator,
        "db",
    )


def test_valid_pca_route():

    validator = CompanyApiRequestValidator()

    result = validator.validate(
        make_request(
            path="/api/pca/settings/default_currency"
        )
    )

    assert result is not None

