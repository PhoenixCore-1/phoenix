import pytest

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
)

from phoenix_pca_company_platform.company_structure_reference import (
    BranchReference,
    CompanyStructureReferenceError,
    CompanyStructureReferenceService,
    InMemoryCompanyStructureReferenceProvider,
    LocationReference,
    OrganisationReference,
)


def make_context(
    organisation_id=501,
):

    return CompanyRuntimeContext(
        {
            "user_id": 101,
            "organisation_id": organisation_id,
            "identity_scope": "COMPANY",
        }
    )


def make_provider():

    return InMemoryCompanyStructureReferenceProvider(
        organisation={
            "organisation_id": 501,
            "name": "Phoenix Company",
            "active": True,
        },
        branches=[
            {
                "branch_id": 10,
                "organisation_id": 501,
                "name": "Johannesburg",
                "active": True,
            },
            {
                "branch_id": 20,
                "organisation_id": 501,
                "name": "Cape Town",
                "active": True,
            },
        ],
        locations=[
            {
                "location_id": 100,
                "organisation_id": 501,
                "branch_id": 10,
                "name": "JHB Warehouse",
                "active": True,
            },
            {
                "location_id": 101,
                "organisation_id": 501,
                "branch_id": 10,
                "name": "JHB Office",
                "active": True,
            },
            {
                "location_id": 200,
                "organisation_id": 501,
                "branch_id": 20,
                "name": "CPT Warehouse",
                "active": True,
            },
        ],
    )


def test_provider_is_required():

    with pytest.raises(
        CompanyStructureReferenceError
    ):

        CompanyStructureReferenceService(
            None
        )


def test_service_constructs():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert service is not None


def test_get_organisation():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    result = service.get_organisation(
        make_context()
    )

    assert isinstance(
        result,
        OrganisationReference,
    )

    assert result.organisation_id == 501
    assert result.name == "Phoenix Company"


def test_list_branches():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    results = service.list_branches(
        make_context()
    )

    assert len(results) == 2

    assert all(
        isinstance(
            item,
            BranchReference,
        )
        for item in results
    )


def test_get_branch():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    result = service.get_branch(
        make_context(),
        10,
    )

    assert result is not None
    assert result.branch_id == 10
    assert result.name == "Johannesburg"


def test_missing_branch_returns_none():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert (
        service.get_branch(
            make_context(),
            999,
        )
        is None
    )


def test_list_locations():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    results = service.list_locations(
        make_context()
    )

    assert len(results) == 3

    assert all(
        isinstance(
            item,
            LocationReference,
        )
        for item in results
    )


def test_list_locations_by_branch():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    results = service.list_locations(
        make_context(),
        branch_id=10,
    )

    assert len(results) == 2

    assert all(
        item.branch_id == 10
        for item in results
    )


def test_get_location():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    result = service.get_location(
        make_context(),
        100,
    )

    assert result is not None
    assert result.location_id == 100


def test_missing_location_returns_none():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert (
        service.get_location(
            make_context(),
            999,
        )
        is None
    )


def test_has_branch():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert service.has_branch(
        make_context(),
        10,
    ) is True

    assert service.has_branch(
        make_context(),
        999,
    ) is False


def test_has_location():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert service.has_location(
        make_context(),
        100,
    ) is True

    assert service.has_location(
        make_context(),
        999,
    ) is False


def test_company_isolation_for_organisation():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert (
        service.get_organisation(
            make_context(502)
        )
        is None
    )


def test_company_isolation_for_branches():

    provider = InMemoryCompanyStructureReferenceProvider(
        branches=[
            {
                "branch_id": 10,
                "organisation_id": 501,
                "name": "Company A Branch",
            },
            {
                "branch_id": 20,
                "organisation_id": 502,
                "name": "Company B Branch",
            },
        ]
    )

    service = CompanyStructureReferenceService(
        provider
    )

    with pytest.raises(
        CompanyStructureReferenceError
    ):
        service.list_branches(
            make_context(501)
        )


def test_company_isolation_for_locations():

    provider = InMemoryCompanyStructureReferenceProvider(
        locations=[
            {
                "location_id": 100,
                "organisation_id": 501,
                "branch_id": 10,
                "name": "Company A Location",
            },
            {
                "location_id": 200,
                "organisation_id": 502,
                "branch_id": 20,
                "name": "Company B Location",
            },
        ]
    )

    service = CompanyStructureReferenceService(
        provider
    )

    results = service.list_locations(
        make_context(501)
    )

    assert len(results) == 1

    assert results[0].location_id == 100

    assert results[0].organisation_id == 501

    assert all(
        item.organisation_id == 501
        for item in results
    )
def test_provider_outside_scope_is_rejected():

    provider = InMemoryCompanyStructureReferenceProvider(
        branches=[
            {
                "branch_id": 99,
                "organisation_id": 999,
                "name": "Wrong Company",
            }
        ]
    )

    service = CompanyStructureReferenceService(
        provider
    )

    with pytest.raises(
        CompanyStructureReferenceError
    ):

        service.list_branches(
            make_context(501)
        )


def test_location_outside_requested_branch_is_rejected():

    class BrokenProvider(
        InMemoryCompanyStructureReferenceProvider
    ):

        def list_locations(
            self,
            organisation_id,
            branch_id=None,
        ):

            return [
                {
                    "location_id": 100,
                    "organisation_id": 501,
                    "branch_id": 20,
                    "name": "Wrong Branch",
                }
            ]

    provider = BrokenProvider()

    service = CompanyStructureReferenceService(
        provider
    )

    with pytest.raises(
        CompanyStructureReferenceError
    ):

        service.list_locations(
            make_context(),
            branch_id=10,
        )
def test_context_is_required():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    with pytest.raises(
        CompanyStructureReferenceError
    ):

        service.list_branches(None)


def test_context_type_is_required():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    with pytest.raises(
        CompanyStructureReferenceError
    ):

        service.list_branches(
            {"organisation_id": 501}
        )


def test_database_is_not_exposed():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert not hasattr(
        service,
        "database",
    )

    assert not hasattr(
        service,
        "connection",
    )

    assert not hasattr(
        service,
        "db",
    )

    assert not hasattr(
        service,
        "cursor",
    )


def test_authentication_is_not_exposed():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert not hasattr(
        service,
        "authenticate",
    )

    assert not hasattr(
        service,
        "login",
    )

    assert not hasattr(
        service,
        "verify_password",
    )


def test_authorization_is_not_exposed():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert not hasattr(
        service,
        "authorize",
    )

    assert not hasattr(
        service,
        "has_permission",
    )


def test_no_master_creation_methods():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    assert not hasattr(
        service,
        "create_organisation",
    )

    assert not hasattr(
        service,
        "create_branch",
    )

    assert not hasattr(
        service,
        "create_location",
    )


def test_configuration_scope():

    service = CompanyStructureReferenceService(
        make_provider()
    )

    result = service.configuration_scope(
        make_context()
    )

    assert result == {
        "organisation_id": 501,
        "company_scope": "COMPANY",
    }


def test_reference_objects_are_immutable():

    organisation = OrganisationReference(
        organisation_id=501
    )

    branch = BranchReference(
        branch_id=10,
        organisation_id=501,
    )

    location = LocationReference(
        location_id=100,
        organisation_id=501,
    )

    with pytest.raises(Exception):
        organisation.organisation_id = 999

    with pytest.raises(Exception):
        branch.branch_id = 999

    with pytest.raises(Exception):
        location.location_id = 999



