import pytest

from phoenix_pca_company_platform.company_host import (
    CompanyHostError,
    CompanyHostState,
    PcaCompanyHost,
)

from phoenix_pca_company_platform.company_runtime_context import (
    CompanyRuntimeContext,
)


def make_user():

    return {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "COMPANY",
    }


def test_host_starts_created():

    host = PcaCompanyHost()

    assert host.state == CompanyHostState.CREATED


def test_host_requires_user_when_no_context():

    host = PcaCompanyHost()

    with pytest.raises(
        CompanyHostError
    ):
        host.initialize()


def test_host_initializes_from_core_user():

    host = PcaCompanyHost(
        user=make_user()
    )

    result = host.initialize()

    assert result is host
    assert host.state == CompanyHostState.READY


def test_host_creates_company_runtime_context():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    context = host.runtime_context

    assert isinstance(
        context,
        CompanyRuntimeContext,
    )

    assert context.user_id == 101
    assert context.organisation_id == 501
    assert context.company_scope == "COMPANY"


def test_host_preserves_core_user():

    user = make_user()

    host = PcaCompanyHost(
        user=user
    )

    host.initialize()

    assert host.runtime_context.as_user() is user


def test_host_accepts_existing_runtime_context():

    context = CompanyRuntimeContext(
        make_user()
    )

    host = PcaCompanyHost(
        runtime_context=context
    )

    host.initialize()

    assert host.runtime_context is context


def test_host_is_idempotent_after_ready():

    host = PcaCompanyHost(
        user=make_user()
    )

    first = host.initialize()
    second = host.initialize()

    assert first is second
    assert host.state == CompanyHostState.READY


def test_host_services_are_composed():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert "operational_settings" in host.services
    assert host.services["operational_settings"] is not None


def test_host_can_register_service():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    service = object()

    result = host.register_service(
        "example",
        service,
    )

    assert result is service
    assert host.has_service("example") is True
    assert host.services["example"] is service


def test_host_rejects_empty_service_name():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    with pytest.raises(
        CompanyHostError
    ):
        host.register_service(
            "",
            object(),
        )


def test_host_rejects_none_service():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    with pytest.raises(
        CompanyHostError
    ):
        host.register_service(
            "example",
            None,
        )


def test_host_requires_ready_for_context():

    host = PcaCompanyHost(
        user=make_user()
    )

    with pytest.raises(
        CompanyHostError
    ):
        _ = host.runtime_context


def test_host_requires_ready_for_services():

    host = PcaCompanyHost(
        user=make_user()
    )

    with pytest.raises(
        CompanyHostError
    ):
        _ = host.services


def test_host_does_not_expose_database():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert not hasattr(
        host,
        "connection",
    )

    assert not hasattr(
        host,
        "database",
    )

    assert not hasattr(
        host,
        "db",
    )

    assert not hasattr(
        host,
        "cursor",
    )


def test_host_does_not_authenticate():

    host = PcaCompanyHost(
        user=make_user()
    )

    assert not hasattr(
        host,
        "authenticate",
    )

    assert not hasattr(
        host,
        "login",
    )

    assert not hasattr(
        host,
        "verify_password",
    )


def test_host_does_not_authorize():

    host = PcaCompanyHost(
        user=make_user()
    )

    assert not hasattr(
        host,
        "has_permission",
    )

    assert not hasattr(
        host,
        "authorize",
    )

    assert not hasattr(
        host,
        "require_permission",
    )


def test_host_does_not_create_platform_licensing():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert not hasattr(
        host,
        "licensing",
    )

    assert not hasattr(
        host,
        "licenses",
    )


def test_host_operates_at_company_scope():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert (
        host.runtime_context.company_scope
        == "COMPANY"
    )


def test_host_accepts_platform_identity_from_core():

    user = {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "PLATFORM",
    }

    host = PcaCompanyHost(
        user=user
    )

    host.initialize()

    assert (
        host.runtime_context.identity_scope
        == "PLATFORM"
    )

    assert (
        host.runtime_context.company_scope
        == "COMPANY"
    )

