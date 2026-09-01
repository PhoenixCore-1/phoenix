"""
Phoenix System Platform
Core Authority Boundary V1.0.

Controlled System Platform-facing boundary over the existing
Phoenix Core authority modules.

This boundary does not create Core authority.

It delegates to the existing authoritative Core functions:

- core.py
- module_licensing.py
- organisation_admin.py
- module_contract.py

No database access is implemented here.
"""

from typing import Any, Optional


class CoreAuthorityBoundaryError(RuntimeError):
    """Base Core authority boundary error."""


class CoreAuthorityBoundary:
    """
    Controlled facade over the existing Phoenix Core functions.

    This class does not contain business authority itself.
    It delegates to the existing Core modules.
    """

    def __init__(
        self,
        core_module: Any,
        licensing_module: Any,
        organisation_module: Any,
        module_contract_module: Any,
    ):
        if core_module is None:
            raise CoreAuthorityBoundaryError(
                "Core module is required."
            )

        if licensing_module is None:
            raise CoreAuthorityBoundaryError(
                "Core licensing module is required."
            )

        if organisation_module is None:
            raise CoreAuthorityBoundaryError(
                "Core organisation module is required."
            )

        if module_contract_module is None:
            raise CoreAuthorityBoundaryError(
                "Core module contract is required."
            )

        self._core = core_module
        self._licensing = licensing_module
        self._organisation = organisation_module
        self._module_contract = module_contract_module

    # ============================================================
    # CORE SECURITY / IDENTITY AUTHORITY
    # ============================================================

    def has_permission(
        self,
        user_id: int,
        permission: str,
    ) -> bool:

        return bool(
            self._core.has_permission(
                user_id,
                permission,
            )
        )

    def is_system_admin(
        self,
        user: dict,
    ) -> bool:

        return bool(
            self._core.is_system_admin(
                user
            )
        )

    def resolve_admin_organisation(
        self,
        user: dict,
        target_organisation_id: Optional[int] = None,
    ):

        return self._core.resolve_admin_organisation(
            user,
            target_organisation_id,
        )

    def enabled_modules(
        self,
        organisation_id: int,
    ):

        return self._core.enabled_modules(
            organisation_id
        )

    def has_module_entitlement(
        self,
        user_id: int,
        module_code: str,
    ) -> bool:

        return bool(
            self._core.has_module_entitlement(
                user_id,
                module_code,
            )
        )

    # ============================================================
    # MODULE CONTRACT AUTHORITY
    # ============================================================

    def module_catalog(self):

        return self._module_contract.module_catalog()

    # ============================================================
    # MODULE LICENSING AUTHORITY
    # ============================================================

    def list_licences(
        self,
        user: dict,
    ):

        return self._licensing.list_licences(
            user
        )

    def set_licence(
        self,
        user: dict,
        module_id: int,
        status: str = "ACTIVE",
        licence_type: str = "COMMERCIAL",
        notes: Optional[str] = None,
    ):

        return self._licensing.set_licence(
            user,
            module_id,
            status,
            licence_type,
            notes,
        )

    def enable_module(
        self,
        user: dict,
        module_id: int,
    ):

        return self._licensing.enable_module(
            user,
            module_id,
        )

    def disable_module(
        self,
        user: dict,
        module_id: int,
    ):

        return self._licensing.disable_module(
            user,
            module_id,
        )

    def check_module_access(
        self,
        user: dict,
        module_id: int,
        permission_code: Optional[str] = None,
    ) -> bool:

        return bool(
            self._licensing.check_module_access(
                user,
                module_id,
                permission_code,
            )
        )

    # ============================================================
    # ORGANISATION AUTHORITY
    # ============================================================

    def list_organisations(
        self,
        user: dict,
    ):

        return self._organisation.list_organisations(
            user
        )

    def get_organisation(
        self,
        user: dict,
        organisation_id: Optional[int] = None,
    ):

        return self._organisation.get_organisation(
            user,
            organisation_id,
        )

    def create_organisation(
        self,
        user: dict,
        data: dict,
    ):

        return self._organisation.create_organisation(
            user,
            data,
        )

    def update_organisation(
        self,
        user: dict,
        organisation_id: int,
        data: dict,
    ):

        return self._organisation.update_organisation(
            user,
            organisation_id,
            data,
        )

    def set_organisation_status(
        self,
        user: dict,
        organisation_id: int,
        active: bool,
    ):

        return self._organisation.set_organisation_status(
            user,
            organisation_id,
            active,
        )


def create_core_authority_boundary(
    core_module: Any,
    licensing_module: Any,
    organisation_module: Any,
    module_contract_module: Any,
) -> CoreAuthorityBoundary:

    return CoreAuthorityBoundary(
        core_module=core_module,
        licensing_module=licensing_module,
        organisation_module=organisation_module,
        module_contract_module=module_contract_module,
    )
