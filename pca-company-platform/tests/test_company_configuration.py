import pytest

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
)

from phoenix_pca_company_platform.company_configuration import (
    CompanyConfigurationError,
    CompanyConfigurationService,
)


def make_context(
    organisation_id=501,
    identity_scope="COMPANY",
):

    return CompanyRuntimeContext(
        {
            "user_id": 101,
            "organisation_id": organisation_id,
            "identity_scope": identity_scope,
        }
    )


def test_service_constructs():

    service = CompanyConfigurationService()

    assert service is not None


def test_missing_configuration_returns_empty_mapping():

    service = CompanyConfigurationService()

    context = make_context()

    assert service.get_configuration(
        context
    ) == {}


def test_configuration_is_company_scoped():

    service = CompanyConfigurationService()

    context_a = make_context(
        organisation_id=501
    )

    context_b = make_context(
        organisation_id=502
    )

    service.set_configuration(
        context_a,
        {
            "company_name": "Company A",
        },
    )

    service.set_configuration(
        context_b,
        {
            "company_name": "Company B",
        },
    )

    assert service.get_configuration(
        context_a
    )["company_name"] == "Company A"

    assert service.get_configuration(
        context_b
    )["company_name"] == "Company B"


def test_set_configuration():

    service = CompanyConfigurationService()

    context = make_context()

    result = service.set_configuration(
        context,
        {
            "company_name": "Phoenix Company",
            "currency": "ZAR",
        },
    )

    assert result["company_name"] == "Phoenix Company"
    assert result["currency"] == "ZAR"


def test_get_configuration_returns_copy():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "company_name": "Phoenix Company",
        },
    )

    result = service.get_configuration(
        context
    )

    result["company_name"] = "Changed"

    assert (
        service.get_configuration(
            context
        )["company_name"]
        == "Phoenix Company"
    )


def test_update_configuration_merges_values():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "company_name": "Phoenix",
            "currency": "ZAR",
        },
    )

    result = service.update_configuration(
        context,
        {
            "currency": "USD",
            "timezone": "Africa/Johannesburg",
        },
    )

    assert result["company_name"] == "Phoenix"
    assert result["currency"] == "USD"
    assert (
        result["timezone"]
        == "Africa/Johannesburg"
    )


def test_update_does_not_affect_other_company():

    service = CompanyConfigurationService()

    context_a = make_context(
        organisation_id=501
    )

    context_b = make_context(
        organisation_id=502
    )

    service.set_configuration(
        context_a,
        {
            "currency": "ZAR",
        },
    )

    service.set_configuration(
        context_b,
        {
            "currency": "USD",
        },
    )

    service.update_configuration(
        context_a,
        {
            "currency": "EUR",
        },
    )

    assert (
        service.get_configuration(
            context_a
        )["currency"]
        == "EUR"
    )

    assert (
        service.get_configuration(
            context_b
        )["currency"]
        == "USD"
    )


def test_remove_configuration():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "company_name": "Phoenix",
            "currency": "ZAR",
        },
    )

    result = service.remove_configuration(
        context,
        "currency",
    )

    assert "currency" not in result
    assert result["company_name"] == "Phoenix"


def test_has_configuration():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "currency": "ZAR",
        },
    )

    assert service.has_configuration(
        context,
        "currency",
    ) is True

    assert service.has_configuration(
        context,
        "missing",
    ) is False


def test_clear_configuration():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "company_name": "Phoenix",
        },
    )

    result = service.clear_configuration(
        context
    )

    assert result == {}

    assert service.get_configuration(
        context
    ) == {}


def test_configuration_keys():

    service = CompanyConfigurationService()

    context = make_context()

    service.set_configuration(
        context,
        {
            "company_name": "Phoenix",
            "currency": "ZAR",
        },
    )

    keys = service.configuration_keys(
        context
    )

    assert "company_name" in keys
    assert "currency" in keys


def test_requires_runtime_context():

    service = CompanyConfigurationService()

    with pytest.raises(
        CompanyConfigurationError
    ):
        service.get_configuration(None)


def test_requires_company_scope():

    service = CompanyConfigurationService()

    context = make_context(
        identity_scope="PLATFORM"
    )

    assert (
        context.company_scope
        == "COMPANY"
    )

    assert service.get_configuration(
        context
    ) == {}


def test_requires_organisation_identity():

    service = CompanyConfigurationService()

    context = CompanyRuntimeContext(
        {
            "user_id": 101,
        }
    )

    with pytest.raises(
        CompanyConfigurationError
    ):
        service.get_configuration(
            context
        )


def test_rejects_non_mapping_configuration():

    service = CompanyConfigurationService()

    context = make_context()

    with pytest.raises(
        CompanyConfigurationError
    ):
        service.set_configuration(
            context,
            "invalid",
        )


def test_rejects_invalid_update():

    service = CompanyConfigurationService()

    context = make_context()

    with pytest.raises(
        CompanyConfigurationError
    ):
        service.update_configuration(
            context,
            "invalid",
        )


def test_rejects_invalid_configuration_key():

    service = CompanyConfigurationService()

    context = make_context()

    with pytest.raises(
        CompanyConfigurationError
    ):
        service.has_configuration(
            context,
            "",
        )


def test_service_does_not_expose_database():

    service = CompanyConfigurationService()

    assert not hasattr(
        service,
        "connection",
    )

    assert not hasattr(
        service,
        "database",
    )

    assert not hasattr(
        service,
        "db",
    )

    assert not hasattr(
        service,
        "cursor",
    )


def test_service_does_not_authenticate():

    service = CompanyConfigurationService()

    assert not hasattr(
        service,
        "authenticate",
    )

    assert not hasattr(
        service,
        "login",
    )

    assert not hasattr(
        service,
        "verify_password",
    )


def test_service_does_not_authorize():

    service = CompanyConfigurationService()

    assert not hasattr(
        service,
        "authorize",
    )

    assert not hasattr(
        service,
        "has_permission",
    )

    assert not hasattr(
        service,
        "require_permission",
    )


def test_service_does_not_own_item_master():

    service = CompanyConfigurationService()

    assert not hasattr(
        service,
        "items",
    )

    assert not hasattr(
        service,
        "products",
    )

    assert not hasattr(
        service,
        "item_master",
    )


def test_service_does_not_own_business_transactions():

    service = CompanyConfigurationService()

    assert not hasattr(
        service,
        "create_order",
    )

    assert not hasattr(
        service,
        "create_quote",
    )

    assert not hasattr(
        service,
        "create_production_order",
    )
