"""
Phoenix System Platform
Core Adapter Boundary V1.0.
"""

from typing import Any, Optional

from .errors import (
    CoreBoundaryError,
    PlatformAuthorizationError,
)
from .models import PlatformIdentity


class CoreAdapter:

    def __init__(self, core: Any, user: Optional[dict] = None):
        self._core = core
        self._user = user

    # ============================================================
    # IDENTITY
    # ============================================================

    def current_identity(self) -> PlatformIdentity:
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        return PlatformIdentity(
            user_id=int(self._user["user_id"]),
            organisation_id=(
                int(self._user["organisation_id"])
                if self._user.get("organisation_id") is not None
                else None
            ),
            identity_scope=str(
                self._user.get("identity_scope") or ""
            ).upper(),
            is_system_admin=self.is_system_admin(),
        )

    # ============================================================
    # AUTHORIZATION
    # ============================================================

    def has_permission(self, permission: str) -> bool:
        if self._user is None:
            return False

        try:
            return bool(
                self._core.has_permission(
                    self._user["user_id"],
                    permission,
                )
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core permission evaluation failed."
            ) from exc

    def require_permission(self, permission: str) -> None:
        if not self.has_permission(permission):
            raise PlatformAuthorizationError(
                f"Required permission denied: {permission}"
            )

    def is_system_admin(self) -> bool:
        if self._user is None:
            return False

        try:
            return bool(
                self._core.is_system_admin(
                    self._user
                )
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core system-admin evaluation failed."
            ) from exc

    def resolve_admin_organisation(
        self,
        target_organisation_id: Optional[int] = None,
    ):
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.resolve_admin_organisation(
                self._user,
                target_organisation_id,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation-scope resolution failed."
            ) from exc

    # ============================================================
    # MODULE CATALOGUE
    # ============================================================

    def module_catalog(self):
        try:
            return self._core.module_catalog()
        except Exception as exc:
            raise CoreBoundaryError(
                "Core module catalogue retrieval failed."
            ) from exc

    def enabled_modules(self):
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.enabled_modules(
                self._user["organisation_id"]
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core enabled-module retrieval failed."
            ) from exc

    def has_module_entitlement(
        self,
        module_code: str,
    ) -> bool:
        if self._user is None:
            return False

        try:
            return bool(
                self._core.has_module_entitlement(
                    self._user["user_id"],
                    module_code,
                )
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core module entitlement evaluation failed."
            ) from exc

    # ============================================================
    # LICENSING
    # ============================================================

    def list_licences(self):
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.list_licences(
                self._user
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core licence retrieval failed."
            ) from exc

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
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.set_licence(
                self._user,
                module_id,
                status,
                licence_type,
                start_date,
                expiry_date,
                seats,
                auto_enable,
                notes,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core licence administration failed."
            ) from exc

    def enable_module(self, module_id):
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.enable_module(
                self._user,
                module_id,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core module enablement failed."
            ) from exc

    def disable_module(self, module_id):
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.disable_module(
                self._user,
                module_id,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core module disablement failed."
            ) from exc

    def check_module_access(
        self,
        module_id,
        permission_code=None,
    ) -> bool:
        if self._user is None:
            return False

        try:
            return bool(
                self._core.check_module_access(
                    self._user,
                    module_id,
                    permission_code,
                )
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core module access evaluation failed."
            ) from exc

    # ============================================================
    # ORGANISATION / COMPANY ADMINISTRATION
    # ============================================================

    def list_organisations(self):
        """
        Return the Core-authoritative platform tenant directory.
        """
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.list_organisations(
                self._user
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation listing failed."
            ) from exc

    def get_organisation(
        self,
        organisation_id=None,
    ):
        """
        Retrieve an organisation through Core's existing
        System Administrator / Company Administrator rules.
        """
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.get_organisation(
                self._user,
                organisation_id,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation retrieval failed."
            ) from exc

    def create_organisation(self, data):
        """
        Create a tenant through Core authority.
        """
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.create_organisation(
                self._user,
                data,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation creation failed."
            ) from exc

    def update_organisation(
        self,
        organisation_id,
        data,
    ):
        """
        Update organisation details through Core authority.
        """
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.update_organisation(
                self._user,
                organisation_id,
                data,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation update failed."
            ) from exc

    def set_organisation_status(
        self,
        organisation_id,
        active,
    ):
        """
        Activate or suspend a tenant through Core authority.
        """
        if self._user is None:
            raise CoreBoundaryError(
                "No Core identity is available."
            )

        try:
            return self._core.set_organisation_status(
                self._user,
                organisation_id,
                active,
            )
        except Exception as exc:
            raise CoreBoundaryError(
                "Core organisation status change failed."
            ) from exc
