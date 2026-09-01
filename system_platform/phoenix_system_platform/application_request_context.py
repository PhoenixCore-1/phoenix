"""
Phoenix System Platform
Application Request Context V1.0.

Converts an already-authenticated Phoenix Core user into the
request-scoped System Platform runtime context.

This module does not authenticate users and does not access
the database.
"""

from typing import Any, Mapping

from .runtime_context import ApplicationRuntimeContext


class ApplicationRequestContextError(RuntimeError):
    """Application request-context construction error."""


def create_runtime_context(
    authenticated_user: Mapping[str, Any],
) -> ApplicationRuntimeContext:
    """
    Construct a System Platform runtime context from an
    already-authenticated Core user.

    Authentication MUST already have occurred in Phoenix Core.
    """

    if authenticated_user is None:
        raise ApplicationRequestContextError(
            "Authenticated Core user is required."
        )

    try:
        return ApplicationRuntimeContext(
            authenticated_user
        )
    except Exception as exc:
        raise ApplicationRequestContextError(
            "Authenticated Core user could not be converted "
            "to a System Platform runtime context."
        ) from exc
