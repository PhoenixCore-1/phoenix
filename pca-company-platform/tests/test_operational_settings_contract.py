import pytest

from phoenix_pca_company_platform.contracts.operational_settings_contract import (
    CONTRACT_CODE,
    CONTRACT_NAME,
    CONTRACT_VERSION,
    COMPANY_SCOPE,
    ORGANISATION_AUTHORITY,
    BRANCH_AUTHORITY,
    LOCATION_AUTHORITY,
    ITEM_MASTER_AUTHORITY,
    OPERATIONAL_SETTINGS_OWNER,
    OperationalSettingDefinition,
    OperationalSettingsContract,
    OperationalSettingsContractError,
    create_operational_settings_contract,
    get_operational_setting_definition,
    operational_setting_keys,
    validate_operational_settings_contract,
)


def test_contract_name():

    contract = create_operational_settings_contract()

    assert contract.name == CONTRACT_NAME


def test_contract_code():

    contract = create_operational_settings_contract()

    assert contract.code == CONTRACT_CODE


def test_contract_version():

    contract = create_operational_settings_contract()

    assert contract.version == CONTRACT_VERSION


def test_company_scope():

    contract = create_operational_settings_contract()

    assert contract.company_scope == COMPANY_SCOPE
    assert contract.owner_scope == COMPANY_SCOPE


def test_pca_owns_operational_settings():

    contract = create_operational_settings_contract()

    assert (
        contract.settings_owner
        == OPERATIONAL_SETTINGS_OWNER
    )


def test_system_platform_owns_structure():

    contract = create_operational_settings_contract()

    assert (
        contract.organisation_authority
        == ORGANISATION_AUTHORITY
    )

    assert (
        contract.branch_authority
        == BRANCH_AUTHORITY
    )

    assert (
        contract.location_authority
        == LOCATION_AUTHORITY
    )


def test_inventory_owns_item_master():

    contract = create_operational_settings_contract()

    assert (
        contract.item_master_authority
        == ITEM_MASTER_AUTHORITY
    )


def test_core_authentication_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.core_authentication_ownership
        is False
    )


def test_core_authorization_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.core_authorization_ownership
        is False
    )


def test_platform_licensing_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.platform_licensing_ownership
        is False
    )


def test_direct_database_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.direct_core_database_ownership
        is False
    )


def test_business_transactions_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.business_transaction_ownership
        is False
    )


def test_duplicate_masters_not_owned():

    contract = create_operational_settings_contract()

    assert (
        contract.organisation_master_ownership
        is False
    )

    assert (
        contract.branch_master_ownership
        is False
    )

    assert (
        contract.location_master_ownership
        is False
    )

    assert (
        contract.item_master_ownership
        is False
    )


def test_contract_validates():

    assert (
        validate_operational_settings_contract()
        is True
    )


def test_setting_keys_are_unique():

    keys = operational_setting_keys()

    assert len(keys) == len(set(keys))


def test_setting_keys_are_available():

    keys = operational_setting_keys()

    assert "default_currency" in keys
    assert "timezone" in keys
    assert "date_format" in keys
    assert "number_decimal_places" in keys
    assert "first_day_of_week" in keys


def test_setting_definition_lookup():

    definition = (
        get_operational_setting_definition(
            "default_currency"
        )
    )

    assert isinstance(
        definition,
        OperationalSettingDefinition,
    )

    assert definition.value_type == "string"
    assert definition.default == "ZAR"


def test_unknown_setting_definition():

    assert (
        get_operational_setting_definition(
            "does_not_exist"
        )
        is None
    )


def test_invalid_owner_scope_is_rejected():

    contract = OperationalSettingsContract(
        owner_scope="PLATFORM"
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_invalid_company_scope_is_rejected():

    contract = OperationalSettingsContract(
        company_scope="PLATFORM"
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_invalid_structure_authority_is_rejected():

    contract = OperationalSettingsContract(
        organisation_authority="PCA"
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_prohibited_core_ownership_is_rejected():

    contract = OperationalSettingsContract(
        core_authentication_ownership=True
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_prohibited_database_ownership_is_rejected():

    contract = OperationalSettingsContract(
        direct_core_database_ownership=True
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_prohibited_transaction_ownership_is_rejected():

    contract = OperationalSettingsContract(
        business_transaction_ownership=True
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_duplicate_setting_keys_are_rejected():

    definition = OperationalSettingDefinition(
        key="duplicate",
        value_type="string",
    )

    contract = OperationalSettingsContract(
        setting_definitions=(
            definition,
            definition,
        )
    )

    with pytest.raises(
        OperationalSettingsContractError
    ):
        contract.validate()


def test_contract_is_immutable():

    contract = create_operational_settings_contract()

    with pytest.raises(Exception):
        contract.version = "2.0"
