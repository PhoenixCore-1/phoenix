import pytest

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
    CompanyRuntimeContextError,
)


def make_user():

    return {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "COMPANY",
    }


def test_context_accepts_authenticated_core_user():

    context = CompanyRuntimeContext(
        make_user()
    )

    assert context.user_id == 101
    assert context.organisation_id == 501
    assert context.identity_scope == "COMPANY"
    assert context.company_scope == "COMPANY"


def test_context_preserves_original_core_user():

    user = make_user()

    context = CompanyRuntimeContext(user)

    assert context.as_user() is user
    assert context.user is user


def test_context_requires_user():

    with pytest.raises(
        CompanyRuntimeContextError
    ):
        CompanyRuntimeContext(None)


def test_context_requires_mapping():

    with pytest.raises(
        CompanyRuntimeContextError
    ):
        CompanyRuntimeContext("invalid")


def test_context_requires_user_id():

    with pytest.raises(
        CompanyRuntimeContextError
    ):
        CompanyRuntimeContext({
            "organisation_id": 501,
        })


def test_context_rejects_null_user_id():

    with pytest.raises(
        CompanyRuntimeContextError
    ):
        CompanyRuntimeContext({
            "user_id": None,
            "organisation_id": 501,
        })


def test_context_allows_missing_organisation_id():

    context = CompanyRuntimeContext({
        "user_id": 101,
    })

    assert context.user_id == 101
    assert context.organisation_id is None
    assert context.company_scope == "COMPANY"


def test_context_normalises_identity_scope():

    context = CompanyRuntimeContext({
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "company",
    })

    assert context.identity_scope == "COMPANY"


def test_context_defaults_identity_scope_to_company():

    context = CompanyRuntimeContext({
        "user_id": 101,
        "organisation_id": 501,
    })

    assert context.identity_scope == "COMPANY"


def test_context_accepts_platform_identity_from_core():

    context = CompanyRuntimeContext({
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "PLATFORM",
    })

    assert context.identity_scope == "PLATFORM"
    assert context.company_scope == "COMPANY"


def test_context_rejects_unknown_identity_scope():

    with pytest.raises(
        CompanyRuntimeContextError
    ):
        CompanyRuntimeContext({
            "user_id": 101,
            "organisation_id": 501,
            "identity_scope": "INVALID",
        })


def test_context_is_immutable():

    context = CompanyRuntimeContext(
        make_user()
    )

    with pytest.raises(
        AttributeError
    ):
        context.user_id = 999


def test_context_does_not_expose_database_connection():

    context = CompanyRuntimeContext(
        make_user()
    )

    assert not hasattr(
        context,
        "connection",
    )

    assert not hasattr(
        context,
        "database",
    )

    assert not hasattr(
        context,
        "db",
    )

    assert not hasattr(
        context,
        "cursor",
    )


def test_context_does_not_authenticate():

    context = CompanyRuntimeContext(
        make_user()
    )

    assert not hasattr(
        context,
        "authenticate",
    )

    assert not hasattr(
        context,
        "login",
    )

    assert not hasattr(
        context,
        "verify_password",
    )


def test_context_does_not_authorize():

    context = CompanyRuntimeContext(
        make_user()
    )

    assert not hasattr(
        context,
        "has_permission",
    )

    assert not hasattr(
        context,
        "require_permission",
    )

    assert not hasattr(
        context,
        "authorize",
    )


def test_context_has_fixed_company_scope():

    context = CompanyRuntimeContext(
        make_user()
    )

    assert context.company_scope == "COMPANY"

    with pytest.raises(
        AttributeError
    ):
        context.company_scope = "PLATFORM"
