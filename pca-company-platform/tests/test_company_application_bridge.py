import pytest

from phoenix_pca_company_platform.company_application_bridge import (
    CompanyApplicationBridge,
    CompanyApplicationBridgeError,
    CompanyApplicationRequestError,
    create_company_application_bridge,
)

from phoenix_pca_company_platform.company_host import (
    CompanyHostState,
)

from phoenix_pca_company_platform.company_operational_settings import (
    CompanyOperationalSettingsService,
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


def make_context():

    return CompanyRuntimeContext(
        make_user()
    )


def test_bridge_can_be_created():

    bridge = CompanyApplicationBridge()

    assert bridge is not None


def test_factory_creates_bridge():

    bridge = create_company_application_bridge(
        user=make_user()
    )

    assert isinstance(
        bridge,
        CompanyApplicationBridge,
    )


def test_bridge_initial_state():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    assert bridge.state == CompanyHostState.CREATED
    assert bridge.is_ready() is False


def test_bridge_requires_initialization_for_context():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    with pytest.raises(
        CompanyApplicationBridgeError
    ):

        bridge.get_company_context()


def test_bridge_requires_initialization_for_services():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    with pytest.raises(
        CompanyApplicationBridgeError
    ):

        bridge.get_service(
            "operational_settings"
        )


def test_bridge_initializes_from_core_user():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    result = bridge.initialize()

    assert result is bridge
    assert bridge.is_ready() is True
    assert bridge.state == CompanyHostState.READY


def test_bridge_preserves_core_identity():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    context = bridge.runtime_context

    assert context.user_id == 101
    assert context.organisation_id == 501
    assert context.identity_scope == "COMPANY"
    assert context.user == make_user()


def test_bridge_exposes_company_scope():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    assert (
        bridge.runtime_context.company_scope
        == "COMPANY"
    )


def test_bridge_exposes_operational_settings():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    service = bridge.get_service(
        "operational_settings"
    )

    assert isinstance(
        service,
        CompanyOperationalSettingsService,
    )


def test_bridge_services_are_company_scoped():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    service = bridge.get_service(
        "operational_settings"
    )

    result = service.get(
        bridge.runtime_context,
        "default_currency",
    )

    assert result.organisation_id == 501
    assert result.value == "ZAR"


def test_existing_runtime_context_is_preserved():

    context = make_context()

    bridge = CompanyApplicationBridge(
        runtime_context=context
    )

    bridge.initialize()

    assert (
        bridge.runtime_context is context
    )


def test_invalid_runtime_context_rejected():

    bridge = CompanyApplicationBridge(
        runtime_context={}
    )

    with pytest.raises(
        CompanyApplicationRequestError
    ):

        bridge.initialize()


def test_missing_identity_rejected():

    bridge = CompanyApplicationBridge()

    with pytest.raises(Exception):

        bridge.initialize()


def test_missing_service_rejected():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    with pytest.raises(
        CompanyApplicationRequestError
    ):

        bridge.get_service(
            "does_not_exist"
        )


def test_empty_service_name_rejected():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    with pytest.raises(
        CompanyApplicationRequestError
    ):

        bridge.get_service("")


def test_non_string_service_name_rejected():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    with pytest.raises(
        CompanyApplicationRequestError
    ):

        bridge.get_service(123)


def test_bridge_has_no_authentication():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    assert not hasattr(
        bridge,
        "authenticate",
    )

    assert not hasattr(
        bridge,
        "login",
    )

    assert not hasattr(
        bridge,
        "verify_password",
    )


def test_bridge_has_no_authorization():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    assert not hasattr(
        bridge,
        "authorize",
    )

    assert not hasattr(
        bridge,
        "has_permission",
    )

    assert not hasattr(
        bridge,
        "check_permission",
    )


def test_bridge_has_no_database():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    bridge.initialize()

    assert not hasattr(
        bridge,
        "database",
    )

    assert not hasattr(
        bridge,
        "connection",
    )

    assert not hasattr(
        bridge,
        "db",
    )

    assert not hasattr(
        bridge,
        "cursor",
    )


def test_bridge_is_company_isolated():

    bridge_a = CompanyApplicationBridge(
        user={
            "user_id": 101,
            "organisation_id": 501,
            "identity_scope": "COMPANY",
        }
    )

    bridge_b = CompanyApplicationBridge(
        user={
            "user_id": 202,
            "organisation_id": 502,
            "identity_scope": "COMPANY",
        }
    )

    bridge_a.initialize()
    bridge_b.initialize()

    assert (
        bridge_a.runtime_context.organisation_id
        == 501
    )

    assert (
        bridge_b.runtime_context.organisation_id
        == 502
    )


def test_bridge_initialize_is_idempotent():

    bridge = CompanyApplicationBridge(
        user=make_user()
    )

    first = bridge.initialize()
    second = bridge.initialize()

    assert first is bridge
    assert second is bridge
    assert bridge.is_ready() is True


def test_bridge_does_not_replace_identity():

    context = make_context()

    bridge = CompanyApplicationBridge(
        runtime_context=context
    )

    bridge.initialize()

    assert bridge.runtime_context is context
    assert bridge.runtime_context.user is context.user


def test_platform_identity_can_operate_on_company_scope():

    bridge = CompanyApplicationBridge(
        user={
            "user_id": 1,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        }
    )

    bridge.initialize()

    assert (
        bridge.runtime_context.identity_scope
        == "PLATFORM"
    )

    assert (
        bridge.runtime_context.company_scope
        == "COMPANY"
    )

    service = bridge.get_service(
        "operational_settings"
    )

    result = service.get(
        bridge.runtime_context,
        "default_currency",
    )

    assert result.organisation_id == 501


def test_bridge_does_not_own_platform_scope():

    bridge = CompanyApplicationBridge(
        user={
            "user_id": 1,
            "organisation_id": 501,
            "identity_scope": "PLATFORM",
        }
    )

    bridge.initialize()

    assert (
        bridge.runtime_context.identity_scope
        == "PLATFORM"
    )

    assert (
        bridge.runtime_context.company_scope
        == "COMPANY"
    )
