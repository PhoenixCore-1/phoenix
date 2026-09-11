import os

import pytest

from core.v2_runtime.http_host_guard import (
    V2HostAdoptionError,
    require_v2_integration,
    should_use_v2,
)


def test_v2_disabled_does_not_require_v2_runtime(monkeypatch):
    monkeypatch.setenv("PHOENIX_CORE_V2_ENABLED", "0")
    assert should_use_v2() is False
    with pytest.raises(V2HostAdoptionError):
        require_v2_integration()


def test_v2_enabled_requires_a_usable_v2_runtime(monkeypatch):
    monkeypatch.setenv("PHOENIX_CORE_V2_ENABLED", "1")
    monkeypatch.delenv("PHOENIX_CORE_V2_PATH", raising=False)
    monkeypatch.delenv("PHOENIX_CORE_V2_DATABASE", raising=False)

    assert should_use_v2() is True
    with pytest.raises(V2HostAdoptionError):
        require_v2_integration()
