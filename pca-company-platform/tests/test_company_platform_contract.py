import pytest

from phoenix_pca_company_platform.contracts.company_platform_contract import (
    CompanyPlatformContract,
    PcaCompanyPlatformContractError,
    get_company_platform_contract,
    validate_company_platform_contract,
)


def test_contract_has_expected_identity():

    contract = get_company_platform_contract()

    assert contract.name == "PCA Company Platform"
    assert contract.code == "pca_company_platform"
    assert contract.version == "1.0"


def test_contract_operates_at_company_scope():

    contract = get_company_platform_contract()

    assert contract.owner_scope == "COMPANY"


def test_pca_owns_company_configuration():

    contract = get_company_platform_contract()

    assert contract.owns_company_configuration is True
    assert contract.company_configuration_owner == (
        "PCA Company Platform"
    )


def test_inventory_owns_item_master():

    contract = get_company_platform_contract()

    assert contract.item_master_owner == "Inventory"


def test_pca_does_not_own_platform_licensing():

    contract = get_company_platform_contract()

    assert contract.owns_platform_licensing is False


def test_pca_does_not_own_core_authentication():

    contract = get_company_platform_contract()

    assert contract.owns_core_authentication is False


def test_pca_does_not_own_core_authorization():

    contract = get_company_platform_contract()

    assert contract.owns_core_authorization is False


def test_pca_does_not_own_platform_provisioning():

    contract = get_company_platform_contract()

    assert contract.owns_platform_provisioning is False


def test_pca_does_not_own_global_platform_configuration():

    contract = get_company_platform_contract()

    assert contract.owns_global_platform_configuration is False


def test_pca_does_not_access_core_database_directly():

    contract = get_company_platform_contract()

    assert contract.owns_direct_core_database_access is False


def test_contract_validates():

    assert validate_company_platform_contract() is True


def test_contract_is_immutable():

    contract = CompanyPlatformContract()

    with pytest.raises(Exception):

        contract.version = "2.0"


def test_platform_licensing_boundary_cannot_be_claimed():

    contract = CompanyPlatformContract(
        owns_platform_licensing=True
    )

    with pytest.raises(PcaCompanyPlatformContractError):

        validate_company_platform_contract(contract)


def test_core_authentication_boundary_cannot_be_claimed():

    contract = CompanyPlatformContract(
        owns_core_authentication=True
    )

    with pytest.raises(PcaCompanyPlatformContractError):

        validate_company_platform_contract(contract)


def test_core_authorization_boundary_cannot_be_claimed():

    contract = CompanyPlatformContract(
        owns_core_authorization=True
    )

    with pytest.raises(PcaCompanyPlatformContractError):

        validate_company_platform_contract(contract)


def test_direct_database_boundary_cannot_be_claimed():

    contract = CompanyPlatformContract(
        owns_direct_core_database_access=True
    )

    with pytest.raises(PcaCompanyPlatformContractError):

        validate_company_platform_contract(contract)


def test_inventory_item_master_boundary_is_locked():

    contract = CompanyPlatformContract(
        item_master_owner="PCA Company Platform"
    )

    with pytest.raises(PcaCompanyPlatformContractError):

        validate_company_platform_contract(contract)
