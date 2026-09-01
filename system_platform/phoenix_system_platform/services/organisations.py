"""
Phoenix System Platform
Organisation Administration Service V1.0.

Platform-facing orchestration for Phoenix tenant/company
administration.

Core remains authoritative for organisation identity,
authorisation, persistence, audit and lifecycle rules.
"""

from ..core_adapter import CoreAdapter


class OrganisationAdministrationService:
    """
    System Platform organisation administration facade.

    No direct database access is permitted.
    No tenant-authorisation rules are duplicated here.
    """

    def __init__(self, core: CoreAdapter):
        self._core = core

    def list_organisations(self):
        """Return the Core-authoritative organisation directory."""
        return self._core.list_organisations()

    def get_organisation(
        self,
        organisation_id=None,
    ):
        """Retrieve an organisation through Core authority."""
        return self._core.get_organisation(
            organisation_id
        )

    def create_organisation(self, data):
        """Create an organisation through Core authority."""
        return self._core.create_organisation(
            data
        )

    def update_organisation(
        self,
        organisation_id,
        data,
    ):
        """Update organisation details through Core authority."""
        return self._core.update_organisation(
            organisation_id,
            data,
        )

    def set_organisation_status(
        self,
        organisation_id,
        active,
    ):
        """Change organisation lifecycle status through Core."""
        return self._core.set_organisation_status(
            organisation_id,
            active,
        )
