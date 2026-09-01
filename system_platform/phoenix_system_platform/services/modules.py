"""
Phoenix System Platform
Module Administration Service V1.0.

This service provides platform-facing orchestration for module
catalogue, entitlement, enablement and access information.

Core remains authoritative for all module and licensing rules.
"""

from ..core_adapter import CoreAdapter


class ModuleAdministrationService:
    """
    System Platform module administration facade.

    No database access is permitted.
    No licensing rules are implemented here.
    """

    def __init__(self, core: CoreAdapter):
        self._core = core

    def get_catalog(self):
        """Return the authoritative Core module catalogue."""
        return self._core.module_catalog()

    def get_enabled_modules(self):
        """Return modules enabled for the current organisation."""
        return self._core.enabled_modules()

    def get_module_entitlement(
        self,
        module_code: str,
    ) -> bool:
        """Return Core-authoritative module entitlement."""
        return self._core.has_module_entitlement(
            module_code
        )

    def check_access(
        self,
        module_id,
        permission_code=None,
    ) -> bool:
        """Return Core-authoritative module access."""
        return self._core.check_module_access(
            module_id,
            permission_code,
        )

    def get_licences(self):
        """Return Core-authoritative licence information."""
        return self._core.list_licences()

    def enable_module(self, module_id):
        """Delegate module enablement to Core."""
        return self._core.enable_module(
            module_id
        )

    def disable_module(self, module_id):
        """Delegate module disablement to Core."""
        return self._core.disable_module(
            module_id
        )

    def set_licence(
        self,
        module_id,
        status="ACTIVE",
        licence_type="COMMERCIAL",
        start_date=None,
        expiry_date=None,
        seats=None,
        auto_enable=False,
        notes=None,
    ):
        """Delegate licence administration to Core."""
        return self._core.set_licence(
            module_id,
            status=status,
            licence_type=licence_type,
            start_date=start_date,
            expiry_date=expiry_date,
            seats=seats,
            auto_enable=auto_enable,
            notes=notes,
        )
