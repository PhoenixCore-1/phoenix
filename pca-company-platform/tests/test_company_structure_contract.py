import pytest

from phoenix_pca_company_platform.contracts.company_structure_contract import (
    CompanyStructureContract,
    CompanyStructureContractError,
    get_company_structure_contract,
    validate_company_structure_contract,
)


def test_contract_identity():

    contract = get_company_structure_contract()

    assert contract.name == "PCA Company Structure"
    assert contract.code == "pca_company_structure"
    assert contract.version == "1.0"


def test_contract_scope_is_company():

    contract = get_company_structure_contract()

    assert contract.scope == "COMPANY"


def test_organisation_authority_is_system_platform():

    contract = get_company_structure_contract()

    assert (
        contract.authoritative_organisation_owner
        == "Phoenix System Platform"
    )


def test_branch_authority_is_system_platform():

    contract = get_company_structure_contract()

    assert (
        contract.authoritative_branch_owner
        == "Phoenix System Platform"
    )


def test_location_authority_is_system_platform():

    contract = get_company_structure_contract()

    assert (
        contract.authoritative_location_owner
        == "Phoenix System Platform"
    )


def test_pca_owns_operational_configuration():

    contract = get_company_structure_contract()

    assert (
        contract.operational_configuration_owner
        == "PCA Company Platform"
    )


def test_pca_does_not_create_organisation_master():

    contract = get_company_structure_contract()

    assert (
        contract.creates_organisation_master
        is False
    )


def test_pca_does_not_create_branch_master():

    contract = get_company_structure_contract()

    assert (
        contract.creates_branch_master
        is False
    )


def test_pca_does_not_create_location_master():

    contract = get_company_structure_contract()

    assert (
        contract.creates_location_master
        is False
    )


def test_pca_does_not_own_platform_provisioning():

    contract = get_company_structure_contract()

    assert (
        contract.owns_platform_provisioning
        is False
    )


def test_pca_does_not_own_core_identity():

    contract = get_company_structure_contract()

    assert (
        contract.owns_core_identity
        is False
    )


def test_pca_does_not_own_authentication():

    contract = get_company_structure_contract()

    assert (
        contract.owns_authentication
        is False
    )


def test_pca_does_not_own_authorization():

    contract = get_company_structure_contract()

    assert (
        contract.owns_authorization
        is False
    )


def test_pca_does_not_access_database_directly():

    contract = get_company_structure_contract()

    assert (
        contract.owns_direct_database_access
        is False
    )


def test_contract_validates():

    assert (
        validate_company_structure_contract()
        is True
    )


def test_contract_is_immutable():

    contract = CompanyStructureContract()

    with pytest.raises(Exception):

        contract.version = "2.0"


def test_second_organisation_master_is_rejected():

    contract = CompanyStructureContract(
        creates_organisation_master=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_second_branch_master_is_rejected():

    contract = CompanyStructureContract(
        creates_branch_master=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_second_location_master_is_rejected():

    contract = CompanyStructureContract(
        creates_location_master=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_wrong_organisation_authority_is_rejected():

    contract = CompanyStructureContract(
        authoritative_organisation_owner=(
            "PCA Company Platform"
        )
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_wrong_branch_authority_is_rejected():

    contract = CompanyStructureContract(
        authoritative_branch_owner=(
            "PCA Company Platform"
        )
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_wrong_location_authority_is_rejected():

    contract = CompanyStructureContract(
        authoritative_location_owner=(
            "PCA Company Platform"
        )
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_direct_database_ownership_is_rejected():

    contract = CompanyStructureContract(
        owns_direct_database_access=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_authentication_ownership_is_rejected():

    contract = CompanyStructureContract(
        owns_authentication=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )


def test_authorization_ownership_is_rejected():

    contract = CompanyStructureContract(
        owns_authorization=True
    )

    with pytest.raises(
        CompanyStructureContractError
    ):

        validate_company_structure_contract(
            contract
        )
