"""
Phoenix PCA Company Platform
Company Configuration Service V1.0.

Company-scoped configuration owned by PCA.

This service operates only within the authenticated
PCA Company Runtime Context.

It does not own:

- authentication
- authorization
- platform licensing
- platform provisioning
- global platform configuration
- Core database access
- business transactions
- Inventory Item Master
- CRM records
- Sales records
- Production records
"""

from collections.abc import Mapping
from typing import Any


class CompanyConfigurationError(RuntimeError):
    """Base company configuration error."""


class CompanyConfigurationService:
    """
    PCA-owned company configuration service.

    V1.0 deliberately uses an in-memory configuration store.

    Persistence will be introduced only through an approved
    PCA persistence/application contract.

    Direct database access is prohibited.
    """

    def __init__(self):

        self._configurations = {}

    def _require_context(self, context):

        if context is None:
            raise CompanyConfigurationError(
                "PCA Company Runtime Context is required."
            )

        if not hasattr(context, "company_scope"):
            raise CompanyConfigurationError(
                "Invalid PCA Company Runtime Context."
            )

        if context.company_scope != "COMPANY":
            raise CompanyConfigurationError(
                "PCA Company Configuration requires COMPANY scope."
            )

        return context

    def _organisation_key(self, context):

        context = self._require_context(context)

        organisation_id = context.organisation_id

        if organisation_id is None:
            raise CompanyConfigurationError(
                "Organisation identity is required."
            )

        return organisation_id

    def get_configuration(self, context):

        organisation_id = self._organisation_key(
            context
        )

        configuration = self._configurations.get(
            organisation_id
        )

        if configuration is None:

            return {}

        return dict(configuration)

    def set_configuration(
        self,
        context,
        data: Mapping[str, Any],
    ):

        organisation_id = self._organisation_key(
            context
        )

        if not isinstance(data, Mapping):
            raise CompanyConfigurationError(
                "Company configuration must be a mapping."
            )

        configuration = dict(data)

        self._configurations[
            organisation_id
        ] = configuration

        return dict(configuration)

    def update_configuration(
        self,
        context,
        data: Mapping[str, Any],
    ):

        organisation_id = self._organisation_key(
            context
        )

        if not isinstance(data, Mapping):
            raise CompanyConfigurationError(
                "Company configuration must be a mapping."
            )

        current = self._configurations.get(
            organisation_id,
            {},
        )

        updated = dict(current)
        updated.update(data)

        self._configurations[
            organisation_id
        ] = updated

        return dict(updated)

    def remove_configuration(
        self,
        context,
        key: str,
    ):

        organisation_id = self._organisation_key(
            context
        )

        if not isinstance(key, str) or not key:
            raise CompanyConfigurationError(
                "Configuration key is required."
            )

        current = dict(
            self._configurations.get(
                organisation_id,
                {},
            )
        )

        current.pop(key, None)

        self._configurations[
            organisation_id
        ] = current

        return dict(current)

    def has_configuration(
        self,
        context,
        key: str,
    ):

        organisation_id = self._organisation_key(
            context
        )

        if not isinstance(key, str) or not key:
            raise CompanyConfigurationError(
                "Configuration key is required."
            )

        return key in self._configurations.get(
            organisation_id,
            {},
        )

    def clear_configuration(self, context):

        organisation_id = self._organisation_key(
            context
        )

        self._configurations[
            organisation_id
        ] = {}

        return {}

    def configuration_keys(self, context):

        organisation_id = self._organisation_key(
            context
        )

        return tuple(
            self._configurations.get(
                organisation_id,
                {},
            ).keys()
        )
