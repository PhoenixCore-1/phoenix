"""
Phoenix System Platform
Application Bootstrap Bridge V1.0.

Provides the controlled integration seam between the active
Phoenix application and System Platform.

The bridge does not own authentication, authorization,
database access, or Core authority.
"""

from typing import Any, Optional

from .application_host import (
    ApplicationContext,
    SystemPlatformApplicationHost,
)
from .runtime_context import ApplicationRuntimeContext


class ApplicationBridgeError(RuntimeError):
    """Application/System Platform bridge error."""


def create_system_platform_host(
    core: Any,
    runtime_context: Optional[ApplicationRuntimeContext] = None,
) -> SystemPlatformApplicationHost:
    """
    Construct and initialise the System Platform Application Host.

    Core remains authoritative for identity and security.
    Runtime identity is request-scoped.
    """

    if core is None:
        raise ApplicationBridgeError(
            "Phoenix Core instance is required."
        )

    if runtime_context is not None and not isinstance(
        runtime_context,
        ApplicationRuntimeContext,
    ):
        raise ApplicationBridgeError(
            "Runtime context must be an ApplicationRuntimeContext."
        )

    context = None

    if runtime_context is not None:
        context = ApplicationContext(
            user=runtime_context.as_user()
        )

    host = SystemPlatformApplicationHost(
        core=core,
        context=context,
    )

    try:
        return host.initialize()
    except Exception as exc:
        raise ApplicationBridgeError(
            "System Platform Application Host initialization failed."
        ) from exc
