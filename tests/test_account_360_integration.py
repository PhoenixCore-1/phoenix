"""Core-side integration tests for Phoenix Account 360."""

from pathlib import Path


def test_account_360_is_registered_in_core_catalog():
    from core.module_contract import ACCOUNT_360_MODULE

    assert ACCOUNT_360_MODULE.code == "account_360"
    assert ACCOUNT_360_MODULE.name == "Account 360"
    assert ACCOUNT_360_MODULE.version == "1.0.0"
    assert ACCOUNT_360_MODULE.core is False
    assert any(item.code == "account_360.home" for item in ACCOUNT_360_MODULE.menu)


def test_account_360_catalog_contains_required_permissions():
    from core.module_contract import ACCOUNT_360_MODULE

    permissions = {item.code for item in ACCOUNT_360_MODULE.permissions}
    assert {
        "account_360.view",
        "account_360.financial.view",
        "account_360.commercial.view",
        "account_360.operations.view",
        "account_360.communication.view",
        "account_360.communication.content.view",
        "account_360.timeline.view",
        "account_360.actions.execute",
        "account_360.ai.use",
        "account_360.ai.action.execute",
    } <= permissions


def test_account_360_is_in_core_module_catalog():
    from core.module_contract import module_catalog

    module = next(item for item in module_catalog() if item["code"] == "account_360")
    assert module["name"] == "Account 360"
    assert module["version"] == "1.0.0"


def test_account_360_is_in_runtime_module_registry():
    from core.modules import MODULES

    module = next(item for item in MODULES if item["code"] == "account_360")
    assert module["name"] == "Account 360"
    assert module["default_enabled"] is False


def test_account_360_adapter_exists_and_uses_external_loader():
    from core.module_adapters.account_360 import ACCOUNT_360_PACKAGE

    assert ACCOUNT_360_PACKAGE == "account_360"
