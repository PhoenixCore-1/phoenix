"""
Phoenix PCA Company Platform
Company Structure Reference Service V1.0.

Controlled PCA-facing reference to the authoritative
organisation, branch and location identities owned by
Phoenix System Platform.

This service does NOT create or persist a second master.

Authoritative ownership remains:

    Organisation -> Phoenix System Platform
    Branch       -> Phoenix System Platform
    Location     -> Phoenix System Platform

PCA owns only the reference/consumption boundary.

This V1.0 service is intentionally provider-based.

An approved upstream provider supplies authoritative
structure data. Persistence is deliberately outside this
service.
"""

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .company_runtime_context import CompanyRuntimeContext
from .contracts.company_structure_contract import (
    validate_company_structure_contract,
)


class CompanyStructureReferenceError(RuntimeError):
    """Base structure reference error."""


@dataclass(frozen=True)
class OrganisationReference:
    """
    Reference to an authoritative organisation.

    This is not an organisation master record.
    """

    organisation_id: Any
    name: Optional[str] = None
    active: Optional[bool] = None


@dataclass(frozen=True)
class BranchReference:
    """
    Reference to an authoritative branch.

    This is not a branch master record.
    """

    branch_id: Any
    organisation_id: Any
    name: Optional[str] = None
    active: Optional[bool] = None


@dataclass(frozen=True)
class LocationReference:
    """
    Reference to an authoritative location.

    This is not a location master record.
    """

    location_id: Any
    organisation_id: Any
    branch_id: Optional[Any] = None
    name: Optional[str] = None
    active: Optional[bool] = None


class CompanyStructureReferenceProvider:
    """
    Abstract upstream structure provider.

    The provider is responsible for obtaining authoritative
    structure information.

    It does not belong to PCA's identity or database layer.
    """

    def get_organisation(
        self,
        organisation_id,
    ):
        raise NotImplementedError

    def list_branches(
        self,
        organisation_id,
    ):
        raise NotImplementedError

    def list_locations(
        self,
        organisation_id,
        branch_id=None,
    ):
        raise NotImplementedError


class InMemoryCompanyStructureReferenceProvider(
    CompanyStructureReferenceProvider
):
    """
    Test/development provider.

    This is deliberately an in-memory reference source.

    It is NOT a database and does NOT establish PCA ownership
    of the authoritative organisation/branch/location masters.
    """

    def __init__(
        self,
        organisation=None,
        branches=None,
        locations=None,
    ):

        self._organisation = organisation
        self._branches = list(
            branches or []
        )
        self._locations = list(
            locations or []
        )

    def get_organisation(
        self,
        organisation_id,
    ):

        if self._organisation is None:
            return None

        if (
            self._organisation.get(
                "organisation_id"
            )
            != organisation_id
        ):
            return None

        return dict(
            self._organisation
        )

    def list_branches(
        self,
        organisation_id,
    ):

        # The test provider represents an upstream authoritative
        # source. PCA performs the company-scope validation.
        #
        # organisation_id is accepted because it is part of the
        # provider contract, but the provider must not silently
        # enforce PCA's scope boundary.

        return [
            dict(branch)
            for branch in self._branches
        ]

    def list_locations(
        self,
        organisation_id,
        branch_id=None,
    ):

        results = [
            dict(location)
            for location in self._locations
            if location.get(
                "organisation_id"
            ) == organisation_id
        ]

        if branch_id is not None:

            results = [
                location
                for location in results
                if location.get(
                    "branch_id"
                ) == branch_id
            ]

        return results


class CompanyStructureReferenceService:
    """
    PCA-facing company structure reference service.

    The service requires an authenticated PCA company runtime
    context and an authoritative upstream provider.

    It never creates a competing master.
    """

    def __init__(
        self,
        provider: CompanyStructureReferenceProvider,
    ):

        if provider is None:
            raise CompanyStructureReferenceError(
                "Authoritative structure provider is required."
            )

        self._provider = provider

        validate_company_structure_contract()

    @property
    def provider(self):

        return self._provider

    def _require_context(
        self,
        context: CompanyRuntimeContext,
    ):

        if context is None:
            raise CompanyStructureReferenceError(
                "PCA Company Runtime Context is required."
            )

        if not isinstance(
            context,
            CompanyRuntimeContext,
        ):
            raise CompanyStructureReferenceError(
                "Invalid PCA Company Runtime Context."
            )

        if context.company_scope != "COMPANY":
            raise CompanyStructureReferenceError(
                "Company structure reference requires COMPANY scope."
            )

        if context.organisation_id is None:
            raise CompanyStructureReferenceError(
                "Organisation identity is required."
            )

        return context

    def get_organisation(
        self,
        context,
    ):

        context = self._require_context(
            context
        )

        result = self._provider.get_organisation(
            context.organisation_id
        )

        if result is None:
            return None

        if (
            result.get("organisation_id")
            != context.organisation_id
        ):
            raise CompanyStructureReferenceError(
                "Provider returned organisation outside company scope."
            )

        return OrganisationReference(
            organisation_id=result.get(
                "organisation_id"
            ),
            name=result.get("name"),
            active=result.get("active"),
        )

    def list_branches(
        self,
        context,
    ):

        context = self._require_context(
            context
        )

        results = self._provider.list_branches(
            context.organisation_id
        )

        references = []

        for result in results:

            if (
                result.get("organisation_id")
                != context.organisation_id
            ):
                raise CompanyStructureReferenceError(
                    "Provider returned branch outside company scope."
                )

            references.append(
                BranchReference(
                    branch_id=result.get(
                        "branch_id"
                    ),
                    organisation_id=result.get(
                        "organisation_id"
                    ),
                    name=result.get("name"),
                    active=result.get("active"),
                )
            )

        return tuple(references)

    def list_locations(
        self,
        context,
        branch_id=None,
    ):

        context = self._require_context(
            context
        )

        results = self._provider.list_locations(
            context.organisation_id,
            branch_id=branch_id,
        )

        references = []

        for result in results:

            if (
                result.get("organisation_id")
                != context.organisation_id
            ):
                raise CompanyStructureReferenceError(
                    "Provider returned location outside company scope."
                )

            # When a branch-scoped request is made, the
            # authoritative provider must return only records
            # belonging to that branch.
            #
            # A wrong-branch record is an upstream integrity
            # violation and PCA fails closed rather than silently
            # accepting or hiding it.
            if (
                branch_id is not None
                and result.get("branch_id")
                != branch_id
            ):
                raise CompanyStructureReferenceError(
                    "Provider returned location outside requested branch."
                )

            references.append(
                LocationReference(
                    location_id=result.get(
                        "location_id"
                    ),
                    organisation_id=result.get(
                        "organisation_id"
                    ),
                    branch_id=result.get(
                        "branch_id"
                    ),
                    name=result.get("name"),
                    active=result.get("active"),
                )
            )

        return tuple(references)

    def get_branch(
        self,
        context,
        branch_id,
    ):

        context = self._require_context(
            context
        )

        for branch in self.list_branches(
            context
        ):

            if branch.branch_id == branch_id:
                return branch

        return None

    def get_location(
        self,
        context,
        location_id,
    ):

        context = self._require_context(
            context
        )

        for location in self.list_locations(
            context
        ):

            if location.location_id == location_id:
                return location

        return None

    def has_branch(
        self,
        context,
        branch_id,
    ):

        return (
            self.get_branch(
                context,
                branch_id,
            )
            is not None
        )

    def has_location(
        self,
        context,
        location_id,
    ):

        return (
            self.get_location(
                context,
                location_id,
            )
            is not None
        )

    def configuration_scope(
        self,
        context,
    ):

        context = self._require_context(
            context
        )

        return {
            "organisation_id":
            context.organisation_id,
            "company_scope":
            context.company_scope,
        }



