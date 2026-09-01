import pytest

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
)

from phoenix_pca_company_platform.company_operational_settings import (
    CompanyOperationalSettingsError,
    CompanyOperationalSettingsProvider,
    CompanyOperationalSettingsService,
    CompanyOperationalSetting,
    InMemoryCompanyOperationalSettingsProvider,
    OperationalSettingNotFoundError,
    OperationalSettingValidationError,
    OperationalSettingsContextError,
    OperationalSettingsProviderError,
)


def make_context(
    organisation_id=501,
):

    return CompanyRuntimeContext(
        user={
            "user_id": 101,
            "organisation_id": organisation_id,
            "identity_scope": "COMPANY",
        }
    )


def make_provider():

    return InMemoryCompanyOperationalSettingsProvider(
        settings={
            501: {
                "default_currency": "ZAR",
                "timezone": "Africa/Johannesburg",
                "date_format": "YYYY-MM-DD",
                "number_decimal_places": 2,
                "first_day_of_week": "MONDAY",
            }
        }
    )


def make_service():

    return CompanyOperationalSettingsService(
        make_provider()
    )


def test_provider_required():

    with pytest.raises(
        CompanyOperationalSettingsError
    ):

        CompanyOperationalSettingsService(None)


def test_contract_exposed():

    service = make_service()

    assert (
        service.contract.code
        == "pca_company_operational_settings"
    )

    assert service.contract.version == "1.0"


def test_provider_exposed():

    provider = make_provider()

    service = CompanyOperationalSettingsService(
        provider
    )

    assert service.provider is provider


def test_context_required():

    service = make_service()

    with pytest.raises(
        OperationalSettingsContextError
    ):

        service.get_all(None)


def test_context_type_required():

    service = make_service()

    with pytest.raises(
        OperationalSettingsContextError
    ):

        service.get_all({})


def test_get_all():

    service = make_service()

    result = service.get_all(
        make_context()
    )

    assert result["default_currency"] == "ZAR"
    assert (
        result["timezone"]
        == "Africa/Johannesburg"
    )
    assert result["date_format"] == "YYYY-MM-DD"
    assert result["number_decimal_places"] == 2
    assert result["first_day_of_week"] == "MONDAY"


def test_defaults():

    provider = (
        InMemoryCompanyOperationalSettingsProvider()
    )

    service = CompanyOperationalSettingsService(
        provider
    )

    result = service.get_all(
        make_context()
    )

    assert result["default_currency"] == "ZAR"
    assert (
        result["timezone"]
        == "Africa/Johannesburg"
    )


def test_get_single():

    service = make_service()

    result = service.get(
        make_context(),
        "default_currency",
    )

    assert isinstance(
        result,
        CompanyOperationalSetting,
    )

    assert result.organisation_id == 501
    assert result.key == "default_currency"
    assert result.value == "ZAR"


def test_unknown_setting_rejected():

    service = make_service()

    with pytest.raises(
        OperationalSettingNotFoundError
    ):

        service.get(
            make_context(),
            "unknown",
        )


def test_invalid_key_rejected():

    service = make_service()

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.get(
            make_context(),
            123,
        )


def test_empty_key_rejected():

    service = make_service()

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.get(
            make_context(),
            "",
        )


def test_set_string():

    service = make_service()

    result = service.set(
        make_context(),
        "default_currency",
        "USD",
    )

    assert result.value == "USD"

    assert (
        service.get(
            make_context(),
            "default_currency",
        ).value
        == "USD"
    )


def test_set_integer():

    service = make_service()

    result = service.set(
        make_context(),
        "number_decimal_places",
        3,
    )

    assert result.value == 3


def test_invalid_string_value():

    service = make_service()

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.set(
            make_context(),
            "default_currency",
            123,
        )


def test_invalid_integer_value():

    service = make_service()

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.set(
            make_context(),
            "number_decimal_places",
            "2",
        )


def test_boolean_not_integer():

    service = make_service()

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.set(
            make_context(),
            "number_decimal_places",
            True,
        )


def test_reset():

    service = make_service()

    service.set(
        make_context(),
        "default_currency",
        "USD",
    )

    result = service.reset(
        make_context(),
        "default_currency",
    )

    assert result.value == "ZAR"


def test_company_isolation():

    provider = (
        InMemoryCompanyOperationalSettingsProvider(
            settings={
                501: {
                    "default_currency": "ZAR",
                },
                502: {
                    "default_currency": "USD",
                },
            }
        )
    )

    service = CompanyOperationalSettingsService(
        provider
    )

    a = service.get(
        make_context(501),
        "default_currency",
    )

    b = service.get(
        make_context(502),
        "default_currency",
    )

    assert a.organisation_id == 501
    assert b.organisation_id == 502
    assert a.value == "ZAR"
    assert b.value == "USD"


def test_company_update_isolated():

    provider = (
        InMemoryCompanyOperationalSettingsProvider(
            settings={
                501: {
                    "default_currency": "ZAR",
                },
                502: {
                    "default_currency": "USD",
                },
            }
        )
    )

    service = CompanyOperationalSettingsService(
        provider
    )

    service.set(
        make_context(501),
        "default_currency",
        "EUR",
    )

    assert (
        service.get(
            make_context(501),
            "default_currency",
        ).value
        == "EUR"
    )

    assert (
        service.get(
            make_context(502),
            "default_currency",
        ).value
        == "USD"
    )


def test_provider_mapping_required():

    class BadProvider(
        CompanyOperationalSettingsProvider
    ):

        def get_settings(
            self,
            organisation_id,
        ):

            return []

        def set_setting(
            self,
            organisation_id,
            key,
            value,
        ):

            pass

    service = CompanyOperationalSettingsService(
        BadProvider()
    )

    with pytest.raises(
        OperationalSettingsProviderError
    ):

        service.get_all(
            make_context()
        )


def test_provider_values_validated():

    provider = (
        InMemoryCompanyOperationalSettingsProvider(
            settings={
                501: {
                    "number_decimal_places": "2",
                }
            }
        )
    )

    service = CompanyOperationalSettingsService(
        provider
    )

    with pytest.raises(
        OperationalSettingValidationError
    ):

        service.get(
            make_context(),
            "number_decimal_places",
        )


def test_no_database_access():

    service = make_service()

    assert not hasattr(service, "connection")
    assert not hasattr(service, "database")
    assert not hasattr(service, "db")
    assert not hasattr(service, "cursor")


def test_no_authentication():

    service = make_service()

    assert not hasattr(service, "authenticate")
    assert not hasattr(service, "login")


def test_no_authorization():

    service = make_service()

    assert not hasattr(service, "authorize")
    assert not hasattr(service, "has_permission")


def test_result_immutable():

    service = make_service()

    result = service.get(
        make_context(),
        "default_currency",
    )

    with pytest.raises(Exception):

        result.value = "USD"


def test_context_identity_controls_company():

    provider = (
        InMemoryCompanyOperationalSettingsProvider(
            settings={
                501: {
                    "default_currency": "ZAR",
                },
                502: {
                    "default_currency": "USD",
                },
            }
        )
    )

    service = CompanyOperationalSettingsService(
        provider
    )

    result = service.get(
        make_context(502),
        "default_currency",
    )

    assert result.organisation_id == 502
    assert result.value == "USD"
