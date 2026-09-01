"""
Phoenix PCA Company Platform
Company Runtime Context V1.0.

Request-scoped company context created from an already
authenticated Phoenix Core identity.

PCA does not authenticate users.

PCA does not authorize users.

PCA does not create an independent identity.

The authenticated Core identity remains authoritative.
"""

from collections.abc import Mapping
from typing import Any, Optional


class CompanyRuntimeContextError(RuntimeError):
    """Base PCA company runtime context error."""


class CompanyRuntimeContext:
    """
    Immutable request-scoped PCA company runtime context.

    The context preserves the authenticated Core user and
    exposes the company/organisation scope required by PCA.

    Core remains authoritative for authentication,
    authorization and identity.
    """

    __slots__ = (
        "_user",
        "_user_id",
        "_organisation_id",
        "_identity_scope",
        "_company_scope",
        "_frozen",
    )

    def __init__(self, user: Mapping[str, Any]):

        if user is None:
            raise CompanyRuntimeContextError(
                "Authenticated Core user is required."
            )

        if not isinstance(user, Mapping):
            raise CompanyRuntimeContextError(
                "Authenticated Core user must be a mapping."
            )

        if "user_id" not in user:
            raise CompanyRuntimeContextError(
                "Authenticated Core user_id is required."
            )

        user_id = user["user_id"]

        if user_id is None:
            raise CompanyRuntimeContextError(
                "Authenticated Core user_id cannot be None."
            )

        organisation_id = user.get(
            "organisation_id"
        )

        identity_scope = user.get(
            "identity_scope",
            "COMPANY",
        )

        if identity_scope is None:
            identity_scope = "COMPANY"

        identity_scope = str(
            identity_scope
        ).upper()

        if identity_scope not in (
            "COMPANY",
            "PLATFORM",
        ):
            raise CompanyRuntimeContextError(
                "Unsupported identity scope."
            )

        object.__setattr__(
            self,
            "_user",
            user,
        )

        object.__setattr__(
            self,
            "_user_id",
            user_id,
        )

        object.__setattr__(
            self,
            "_organisation_id",
            organisation_id,
        )

        object.__setattr__(
            self,
            "_identity_scope",
            identity_scope,
        )

        object.__setattr__(
            self,
            "_company_scope",
            "COMPANY",
        )

        object.__setattr__(
            self,
            "_frozen",
            True,
        )

    @property
    def user_id(self):
        return self._user_id

    @property
    def organisation_id(self):
        return self._organisation_id

    @property
    def identity_scope(self):
        return self._identity_scope

    @property
    def company_scope(self):
        return self._company_scope

    @property
    def user(self):
        return self._user

    def as_user(self):
        """
        Return the original authenticated Core user object.

        PCA does not replace or reconstruct Core identity.
        """

        return self._user

    def __setattr__(self, name, value):

        if getattr(self, "_frozen", False):
            raise AttributeError(
                "CompanyRuntimeContext is immutable."
            )

        object.__setattr__(
            self,
            name,
            value,
        )
