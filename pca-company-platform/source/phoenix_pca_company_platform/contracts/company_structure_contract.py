"""
Phoenix PCA Company Platform
Company Structure Contract V1.0.

Defines the ownership boundary for company organisational
structure used by PCA and downstream business modules.

This contract deliberately does NOT create a second
organisation, branch or location master.

Existing Phoenix/System Platform authority remains responsible
for authoritative organisational identity.

PCA owns company-level operational configuration that may be
associated with those authoritative organisational entities.

The contract separates:

1. authoritative organisational identity
2. PCA company operational configuration
"""

from dataclasses import dataclass


PCA_COMPANY_STRUCTURE_CONTRACT_VERSION = "1.0"


class CompanyStructureContractError(RuntimeError):
    """Base company structure contract error."""


@dataclass(frozen=True)
class CompanyStructureContract:
    """
    Immutable PCA company structure contract.
    """

    name: str = "PCA Company Structure"
    code: str = "pca_company_structure"
    version: str = PCA_COMPANY_STRUCTURE_CONTRACT_VERSION

    scope: str = "COMPANY"

    authoritative_organisation_owner: str = (
        "Phoenix System Platform"
    )

    authoritative_branch_owner: str = (
        "Phoenix System Platform"
    )

    authoritative_location_owner: str = (
        "Phoenix System Platform"
    )

    operational_configuration_owner: str = (
        "PCA Company Platform"
    )

    creates_organisation_master: bool = False

    creates_branch_master: bool = False

    creates_location_master: bool = False

    owns_platform_provisioning: bool = False

    owns_core_identity: bool = False

    owns_authentication: bool = False

    owns_authorization: bool = False

    owns_direct_database_access: bool = False


def get_company_structure_contract():
    """
    Return the immutable PCA company structure contract.
    """

    return CompanyStructureContract()


def validate_company_structure_contract(
    contract=None,
):
    """
    Validate the non-negotiable company structure boundary.
    """

    contract = (
        contract
        or CompanyStructureContract()
    )

    if contract.code != "pca_company_structure":
        raise CompanyStructureContractError(
            "Invalid PCA company structure contract code."
        )

    if contract.version != "1.0":
        raise CompanyStructureContractError(
            "Unsupported PCA company structure contract version."
        )

    if contract.scope != "COMPANY":
        raise CompanyStructureContractError(
            "PCA company structure must operate at COMPANY scope."
        )

    if contract.authoritative_organisation_owner != (
        "Phoenix System Platform"
    ):
        raise CompanyStructureContractError(
            "PCA must not replace authoritative organisation ownership."
        )

    if contract.authoritative_branch_owner != (
        "Phoenix System Platform"
    ):
        raise CompanyStructureContractError(
            "PCA must not replace authoritative branch ownership."
        )

    if contract.authoritative_location_owner != (
        "Phoenix System Platform"
    ):
        raise CompanyStructureContractError(
            "PCA must not replace authoritative location ownership."
        )

    if contract.creates_organisation_master:
        raise CompanyStructureContractError(
            "PCA must not create a second organisation master."
        )

    if contract.creates_branch_master:
        raise CompanyStructureContractError(
            "PCA must not create a second branch master."
        )

    if contract.creates_location_master:
        raise CompanyStructureContractError(
            "PCA must not create a second location master."
        )

    if contract.owns_platform_provisioning:
        raise CompanyStructureContractError(
            "PCA must not own platform provisioning."
        )

    if contract.owns_core_identity:
        raise CompanyStructureContractError(
            "PCA must not own Core identity."
        )

    if contract.owns_authentication:
        raise CompanyStructureContractError(
            "PCA must not own authentication."
        )

    if contract.owns_authorization:
        raise CompanyStructureContractError(
            "PCA must not own authorization."
        )

    if contract.owns_direct_database_access:
        raise CompanyStructureContractError(
            "PCA must not own direct database access."
        )

    if contract.operational_configuration_owner != (
        "PCA Company Platform"
    ):
        raise CompanyStructureContractError(
            "PCA must remain the operational configuration owner."
        )

    return True
