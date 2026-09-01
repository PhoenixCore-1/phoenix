"""
Phoenix PCA Company Platform
Company Operational Settings Contract V1.0.

Defines the ownership and structural boundary for
company-level operational settings.

PCA Company Platform owns company operational preferences.

This contract does NOT grant PCA ownership of:

- Core authentication
- Core authorization
- Platform licensing
- Organisation master data
- Branch master data
- Location master data
- Inventory Item Master
- Business transactions
- Direct Core database access
"""

from dataclasses import dataclass
from typing import Any, Mapping


CONTRACT_NAME = "PCA Company Operational Settings"

CONTRACT_CODE = "pca_company_operational_settings"

CONTRACT_VERSION = "1.0"

COMPANY_SCOPE = "COMPANY"

OWNER_SCOPE = "COMPANY"

OPERATIONAL_SETTINGS_OWNER = "PCA Company Platform"

ORGANISATION_AUTHORITY = "Phoenix System Platform"

BRANCH_AUTHORITY = "Phoenix System Platform"

LOCATION_AUTHORITY = "Phoenix System Platform"

ITEM_MASTER_AUTHORITY = "Inventory"

PLATFORM_LICENSING_OWNERSHIP = False

CORE_AUTHENTICATION_OWNERSHIP = False

CORE_AUTHORIZATION_OWNERSHIP = False

DIRECT_CORE_DATABASE_OWNERSHIP = False

BUSINESS_TRANSACTION_OWNERSHIP = False

ORGANISATION_MASTER_OWNERSHIP = False

BRANCH_MASTER_OWNERSHIP = False

LOCATION_MASTER_OWNERSHIP = False

ITEM_MASTER_OWNERSHIP = False


@dataclass(frozen=True)
class OperationalSettingDefinition:
    """
    Definition of one PCA-owned operational setting.

    The definition describes the setting contract only.
    It does not persist or mutate company data.
    """

    key: str
    value_type: str
    default: Any = None
    required: bool = False


OPERATIONAL_SETTING_DEFINITIONS = (
    OperationalSettingDefinition(
        key="default_currency",
        value_type="string",
        default="ZAR",
        required=True,
    ),
    OperationalSettingDefinition(
        key="timezone",
        value_type="string",
        default="Africa/Johannesburg",
        required=True,
    ),
    OperationalSettingDefinition(
        key="date_format",
        value_type="string",
        default="YYYY-MM-DD",
        required=True,
    ),
    OperationalSettingDefinition(
        key="number_decimal_places",
        value_type="integer",
        default=2,
        required=True,
    ),
    OperationalSettingDefinition(
        key="first_day_of_week",
        value_type="string",
        default="MONDAY",
        required=True,
    ),
)


class OperationalSettingsContractError(
    ValueError
):
    """Raised when the contract is invalid."""


@dataclass(frozen=True)
class OperationalSettingsContract:
    """
    Immutable operational settings contract descriptor.
    """

    name: str = CONTRACT_NAME
    code: str = CONTRACT_CODE
    version: str = CONTRACT_VERSION
    owner_scope: str = OWNER_SCOPE
    settings_owner: str = OPERATIONAL_SETTINGS_OWNER
    company_scope: str = COMPANY_SCOPE

    organisation_authority: str = ORGANISATION_AUTHORITY
    branch_authority: str = BRANCH_AUTHORITY
    location_authority: str = LOCATION_AUTHORITY
    item_master_authority: str = ITEM_MASTER_AUTHORITY

    platform_licensing_ownership: bool = (
        PLATFORM_LICENSING_OWNERSHIP
    )

    core_authentication_ownership: bool = (
        CORE_AUTHENTICATION_OWNERSHIP
    )

    core_authorization_ownership: bool = (
        CORE_AUTHORIZATION_OWNERSHIP
    )

    direct_core_database_ownership: bool = (
        DIRECT_CORE_DATABASE_OWNERSHIP
    )

    business_transaction_ownership: bool = (
        BUSINESS_TRANSACTION_OWNERSHIP
    )

    organisation_master_ownership: bool = (
        ORGANISATION_MASTER_OWNERSHIP
    )

    branch_master_ownership: bool = (
        BRANCH_MASTER_OWNERSHIP
    )

    location_master_ownership: bool = (
        LOCATION_MASTER_OWNERSHIP
    )

    item_master_ownership: bool = (
        ITEM_MASTER_OWNERSHIP
    )

    setting_definitions: tuple = (
        OPERATIONAL_SETTING_DEFINITIONS
    )

    def validate(self):

        if self.name != CONTRACT_NAME:
            raise OperationalSettingsContractError(
                "Invalid operational settings contract name."
            )

        if self.code != CONTRACT_CODE:
            raise OperationalSettingsContractError(
                "Invalid operational settings contract code."
            )

        if self.version != CONTRACT_VERSION:
            raise OperationalSettingsContractError(
                "Unsupported operational settings contract version."
            )

        if self.owner_scope != COMPANY_SCOPE:
            raise OperationalSettingsContractError(
                "Operational settings must be company scoped."
            )

        if self.company_scope != COMPANY_SCOPE:
            raise OperationalSettingsContractError(
                "Operational settings require COMPANY scope."
            )

        if self.settings_owner != OPERATIONAL_SETTINGS_OWNER:
            raise OperationalSettingsContractError(
                "PCA Company Platform must own operational settings."
            )

        if self.organisation_authority != (
            ORGANISATION_AUTHORITY
        ):
            raise OperationalSettingsContractError(
                "Organisation authority must remain System Platform."
            )

        if self.branch_authority != (
            BRANCH_AUTHORITY
        ):
            raise OperationalSettingsContractError(
                "Branch authority must remain System Platform."
            )

        if self.location_authority != (
            LOCATION_AUTHORITY
        ):
            raise OperationalSettingsContractError(
                "Location authority must remain System Platform."
            )

        if self.item_master_authority != (
            ITEM_MASTER_AUTHORITY
        ):
            raise OperationalSettingsContractError(
                "Item Master authority must remain Inventory."
            )

        prohibited_ownership = (
            self.platform_licensing_ownership
            or self.core_authentication_ownership
            or self.core_authorization_ownership
            or self.direct_core_database_ownership
            or self.business_transaction_ownership
            or self.organisation_master_ownership
            or self.branch_master_ownership
            or self.location_master_ownership
            or self.item_master_ownership
        )

        if prohibited_ownership:
            raise OperationalSettingsContractError(
                "PCA operational settings contract contains "
                "prohibited ownership."
            )

        if not self.setting_definitions:
            raise OperationalSettingsContractError(
                "At least one operational setting is required."
            )

        keys = [
            definition.key
            for definition in self.setting_definitions
        ]

        if len(keys) != len(set(keys)):
            raise OperationalSettingsContractError(
                "Operational setting keys must be unique."
            )

        for definition in self.setting_definitions:

            if not definition.key:
                raise OperationalSettingsContractError(
                    "Operational setting key is required."
                )

            if not definition.value_type:
                raise OperationalSettingsContractError(
                    "Operational setting value type is required."
                )

        return True


def create_operational_settings_contract():
    """
    Create and validate the V1.0 contract.
    """

    contract = OperationalSettingsContract()

    contract.validate()

    return contract


def validate_operational_settings_contract():
    """
    Validate the current V1.0 contract.
    """

    return (
        create_operational_settings_contract()
        .validate()
    )


def operational_setting_keys():
    """
    Return the contract-defined operational setting keys.
    """

    return tuple(
        definition.key
        for definition
        in OPERATIONAL_SETTING_DEFINITIONS
    )


def get_operational_setting_definition(
    key: str,
):
    """
    Resolve one setting definition by key.
    """

    for definition in (
        OPERATIONAL_SETTING_DEFINITIONS
    ):

        if definition.key == key:
            return definition

    return None
