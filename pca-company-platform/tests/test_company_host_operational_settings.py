import pytest

from phoenix_pca_company_platform.company_host import (
    CompanyHostError,
    CompanyHostState,
    PcaCompanyHost,
)

from phoenix_pca_company_platform.company_operational_settings import (
    CompanyOperationalSettingsService,
)


def make_user():

    return {
        "user_id": 101,
        "organisation_id": 501,
        "identity_scope": "COMPANY",
    }


def test_host_composes_operational_settings():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert host.state == CompanyHostState.READY
    assert host.has_service(
        "operational_settings"
    )


def test_operational_settings_service_type():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    service = host.services[
        "operational_settings"
    ]

    assert isinstance(
        service,
        CompanyOperationalSettingsService,
    )


def test_operational_settings_uses_host_company():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    service = host.services[
        "operational_settings"
    ]

    result = service.get(
        host.runtime_context,
        "default_currency",
    )

    assert result.organisation_id == 501
    assert result.value == "ZAR"


def test_host_still_preserves_core_identity():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert host.runtime_context.user_id == 101
    assert (
        host.runtime_context.organisation_id
        == 501
    )
    assert (
        host.runtime_context.identity_scope
        == "COMPANY"
    )


def test_host_has_no_database():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert not hasattr(host, "database")
    assert not hasattr(host, "connection")
    assert not hasattr(host, "db")
    assert not hasattr(host, "cursor")


def test_host_has_no_authentication():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert not hasattr(host, "authenticate")
    assert not hasattr(host, "login")
    assert not hasattr(host, "verify_password")


def test_host_has_no_authorization():

    host = PcaCompanyHost(
        user=make_user()
    )

    host.initialize()

    assert not hasattr(host, "authorize")
    assert not hasattr(host, "has_permission")
    assert not hasattr(host, "check_permission")


def test_service_is_company_isolated():

    host_a = PcaCompanyHost(
        user={
            "user_id": 101,
            "organisation_id": 501,
            "identity_scope": "COMPANY",
        }
    )

    host_b = PcaCompanyHost(
        user={
            "user_id": 202,
            "organisation_id": 502,
            "identity_scope": "COMPANY",
        }
    )

    host_a.initialize()
    host_b.initialize()

    service_a = host_a.services[
        "operational_settings"
    ]

    service_b = host_b.services[
        "operational_settings"
    ]

    service_a.set(
        host_a.runtime_context,
        "default_currency",
        "EUR",
    )

    assert (
        service_a.get(
            host_a.runtime_context,
            "default_currency",
        ).value
        == "EUR"
    )

    assert (
        service_b.get(
            host_b.runtime_context,
            "default_currency",
        ).value
        == "ZAR"
    )
