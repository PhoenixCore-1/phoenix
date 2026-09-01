"""System Platform domain models."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlatformIdentity:
    user_id: int
    organisation_id: Optional[int]
    identity_scope: str
    is_system_admin: bool
