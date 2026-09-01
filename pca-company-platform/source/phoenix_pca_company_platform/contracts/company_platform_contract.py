"""
Phoenix PCA Company Platform
Company Platform Contract V1.0.

Authoritative architectural boundary between Phoenix
Platform/System authority and the PCA Company Platform.

PCA Company Platform is the company/tenant-level control
and configuration layer.

It is NOT a second Phoenix Platform Control Plane.

It does not own:

- platform-wide tenant provisioning
- platform licensing
- global platform security
- Core authentication
- Core authorization
- global platform configuration
- direct database access to Phoenix Core
"""

from dataclasses import dataclass
from typing import Optional


PCA_COMPANY_PLATFORM_CONTRACT_VERSION = "1.0"


class PcaCompanyPlatformContractError(RuntimeError):
    """Base PCA Company Platform contract error."""


@dataclass(frozen=True)
class CompanyPlatformContract:
    """
    Immutable PCA Company Platform contract descriptor.
    """

    name: str = "PCA Company Platform"
    code: str = "pca_company_platform"
    version: str = PCA_COMPANY_PLATFORM_CONTRACT_VERSION

    owner_scope: str = "COMPANY"

    core_authority: str = "Phoenix Core"
    platform_authority: str = "Phoenix Platform Control Plane"

    company_configuration_owner: str = "PCA Company Platform"
    item_master_owner: str = "Inventory"

    owns_company_configuration: bool = True
    owns_platform_licensing: bool = False
    owns_core_authentication: bool = False
    owns_core_authorization: bool = False
    owns_platform_provisioning: bool = False
    owns_global_platform_configuration: bool = False
    owns_direct_core_database_access: bool = False


def get_company_platform_contract() -> CompanyPlatformContract:
    """
    Return the immutable PCA Company Platform contract.
    """

    return CompanyPlatformContract()


def validate_company_platform_contract(
    contract: Optional[CompanyPlatformContract] = None,
) -> bool:
    """
    Validate the non-negotiable PCA ownership boundaries.
    """

    contract = contract or CompanyPlatformContract()

    if contract.code != "pca_company_platform":
        raise PcaCompanyPlatformContractError(
            "Invalid PCA Company Platform code."
        )

    if contract.version != "1.0":
        raise PcaCompanyPlatformContractError(
            "Unsupported PCA Company Platform contract version."
        )

    if contract.owner_scope != "COMPANY":
        raise PcaCompanyPlatformContractError(
            "PCA Company Platform must operate at COMPANY scope."
        )

    if contract.owns_platform_licensing:
        raise PcaCompanyPlatformContractError(
            "PCA must not own platform licensing."
        )

    if contract.owns_core_authentication:
        raise PcaCompanyPlatformContractError(
            "PCA must not own Core authentication."
        )

    if contract.owns_core_authorization:
        raise PcaCompanyPlatformContractError(
            "PCA must not own Core authorization."
        )

    if contract.owns_platform_provisioning:
        raise PcaCompanyPlatformContractError(
            "PCA must not own platform provisioning."
        )

    if contract.owns_global_platform_configuration:
        raise PcaCompanyPlatformContractError(
            "PCA must not own global platform configuration."
        )

    if contract.owns_direct_core_database_access:
        raise PcaCompanyPlatformContractError(
            "PCA must not access the Core database directly."
        )

    if contract.company_configuration_owner != (
        "PCA Company Platform"
    ):
        raise PcaCompanyPlatformContractError(
            "PCA must remain the company configuration owner."
        )

    if contract.item_master_owner != "Inventory":
        raise PcaCompanyPlatformContractError(
            "Inventory must remain the authoritative company Item Master."
        )

    return True
