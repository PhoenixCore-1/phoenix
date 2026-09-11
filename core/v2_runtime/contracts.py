"""HTTP-host-facing contracts for Phoenix Core V2."""

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID


@dataclass(frozen=True)
class V2Request:
    """Request context forwarded to the authoritative V2 integration boundary."""

    request_id: str
    operation: str
    session_id: UUID | None = None
    organisation_id: UUID | None = None
    payload: Mapping[str, Any] | None = None
