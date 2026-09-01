"""
Phoenix PCA Company Platform
Company Operational Settings Service V1.0.
"""

from dataclasses import dataclass
from typing import Any, Mapping

from .company_runtime_context import CompanyRuntimeContext

from .contracts.operational_settings_contract import (
    create_operational_settings_contract,
    get_operational_setting_definition,
)


class CompanyOperationalSettingsError(RuntimeError):
    """Base operational settings service error."""


class OperationalSettingsContextError(
    CompanyOperationalSettingsError
):
    """Invalid company runtime context."""


class OperationalSettingNotFoundError(
    CompanyOperationalSettingsError
):
    """Requested setting does not exist."""


class OperationalSettingValidationError(
    CompanyOperationalSettingsError
):
    """Setting value failed validation."""


class OperationalSettingsProviderError(
    CompanyOperationalSettingsError
):
    """Provider contract violation."""


@dataclass(frozen=True)
class CompanyOperationalSetting:
    organisation_id: int
    key: str
    value: Any


class CompanyOperationalSettingsProvider:
    """
    Persistence boundary.

    The service does not access a database directly.
    """

    def get_settings(
        self,
        organisation_id: int,
    ) -> Mapping[str, Any]:

        raise NotImplementedError

    def set_setting(
        self,
        organisation_id: int,
        key: str,
        value: Any,
    ) -> None:

        raise NotImplementedError


class InMemoryCompanyOperationalSettingsProvider(
    CompanyOperationalSettingsProvider
):
    """
    Non-database provider used for service testing and
    development.
    """

    def __init__(
        self,
        settings=None,
    ):

        self._settings = {}

        if settings:

            for organisation_id, values in settings.items():

                self._settings[
                    organisation_id
                ] = dict(values)

    def get_settings(
        self,
        organisation_id: int,
    ):

        return dict(
            self._settings.get(
                organisation_id,
                {},
            )
        )

    def set_setting(
        self,
        organisation_id: int,
        key: str,
        value: Any,
    ):

        self._settings.setdefault(
            organisation_id,
            {},
        )[key] = value


class CompanyOperationalSettingsService:
    """
    Company-scoped operational settings service.

    The organisation identity always comes from the
    authenticated CompanyRuntimeContext.
    """

    def __init__(
        self,
        provider: CompanyOperationalSettingsProvider,
    ):

        if provider is None:
            raise CompanyOperationalSettingsError(
                "Operational settings provider is required."
            )

        self._provider = provider
        self._contract = (
            create_operational_settings_contract()
        )

    @property
    def contract(self):
        return self._contract

    @property
    def provider(self):
        return self._provider

    def _require_context(
        self,
        context,
    ):

        if context is None:
            raise OperationalSettingsContextError(
                "Company runtime context is required."
            )

        if not isinstance(
            context,
            CompanyRuntimeContext,
        ):
            raise OperationalSettingsContextError(
                "Valid CompanyRuntimeContext is required."
            )

        if context.company_scope != "COMPANY":
            raise OperationalSettingsContextError(
                "Operational settings require COMPANY scope."
            )

        if context.organisation_id is None:
            raise OperationalSettingsContextError(
                "Company organisation identity is required."
            )

        return context

    def _get_definition(
        self,
        key,
    ):

        if not isinstance(key, str):
            raise OperationalSettingValidationError(
                "Operational setting key must be a string."
            )

        if not key.strip():
            raise OperationalSettingValidationError(
                "Operational setting key is required."
            )

        definition = (
            get_operational_setting_definition(key)
        )

        if definition is None:
            raise OperationalSettingNotFoundError(
                f"Unknown operational setting: {key}"
            )

        return definition

    def _validate_value(
        self,
        definition,
        value,
    ):

        if definition.value_type == "string":

            if not isinstance(value, str):
                raise OperationalSettingValidationError(
                    f"Setting '{definition.key}' requires "
                    "a string value."
                )

        elif definition.value_type == "integer":

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
            ):
                raise OperationalSettingValidationError(
                    f"Setting '{definition.key}' requires "
                    "an integer value."
                )

        else:

            raise OperationalSettingValidationError(
                f"Unsupported setting type: "
                f"{definition.value_type}"
            )

    def _provider_values(
        self,
        context,
    ):

        values = self._provider.get_settings(
            context.organisation_id
        )

        if not isinstance(values, Mapping):
            raise OperationalSettingsProviderError(
                "Provider must return a mapping."
            )

        return dict(values)

    def get_all(
        self,
        context,
    ):

        context = self._require_context(
            context
        )

        values = self._provider_values(
            context
        )

        result = {}

        for definition in (
            self._contract.setting_definitions
        ):

            if definition.key in values:

                value = values[
                    definition.key
                ]

                self._validate_value(
                    definition,
                    value,
                )

                result[
                    definition.key
                ] = value

            else:

                result[
                    definition.key
                ] = definition.default

        return dict(result)

    def get(
        self,
        context,
        key,
    ):

        context = self._require_context(
            context
        )

        definition = self._get_definition(
            key
        )

        values = self._provider_values(
            context
        )

        if key in values:

            value = values[key]

            self._validate_value(
                definition,
                value,
            )

        else:

            value = definition.default

        return CompanyOperationalSetting(
            organisation_id=context.organisation_id,
            key=key,
            value=value,
        )

    def set(
        self,
        context,
        key,
        value,
    ):

        context = self._require_context(
            context
        )

        definition = self._get_definition(
            key
        )

        self._validate_value(
            definition,
            value,
        )

        self._provider.set_setting(
            context.organisation_id,
            key,
            value,
        )

        return CompanyOperationalSetting(
            organisation_id=context.organisation_id,
            key=key,
            value=value,
        )

    def reset(
        self,
        context,
        key,
    ):

        context = self._require_context(
            context
        )

        definition = self._get_definition(
            key
        )

        self._provider.set_setting(
            context.organisation_id,
            key,
            definition.default,
        )

        return CompanyOperationalSetting(
            organisation_id=context.organisation_id,
            key=key,
            value=definition.default,
        )
