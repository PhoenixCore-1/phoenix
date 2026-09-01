"""
Phoenix Production Module.

Public package identity and integration surface for
Phoenix Production Module 1.3.25.
"""

__module_code__ = "production"
__module_name__ = "Production"
__version__ = "1.3.25"


from .production.integration import (
    complete_order,
    get_eta_operational_snapshot,
    hold_order,
    record_stage_quantities,
    release_order,
    resume_order,
    start_order,
    start_stage,
)


__all__ = [
    "record_stage_quantities",
    "release_order",
    "start_order",
    "start_stage",
    "hold_order",
    "resume_order",
    "complete_order",
    "get_eta_operational_snapshot",
]