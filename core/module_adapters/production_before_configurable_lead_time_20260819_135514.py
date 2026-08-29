"""
Phoenix Core -> Production Module adapter.

Core uses this adapter instead of importing the Production Module's
internal packages directly.

The Production Module owns Production business rules.
Phoenix Core owns authentication, permissions, tenant isolation,
database access and HTTP/API orchestration.
"""

from decimal import Decimal
from pathlib import Path
from typing import Optional

from module_loader import LoadedModule, load_module


PRODUCTION_PACKAGE = "phoenix_production_module"

_production_module: Optional[LoadedModule] = None


def configure_production_module(
    module_path: str | Path,
) -> LoadedModule:
    """
    Configure and load the external Phoenix Production Module.

    The host application supplies the module path.
    Phoenix Core does not hard-code the module location.
    """

    global _production_module

    _production_module = load_module(
        PRODUCTION_PACKAGE,
        module_path=module_path,
    )

    return _production_module


def get_production_module() -> LoadedModule:
    """
    Return the configured Production Module.

    Raises RuntimeError if the host application has not configured
    the Production Module yet.
    """

    if _production_module is None:
        raise RuntimeError(
            "Phoenix Production Module is not configured. "
            "Call configure_production_module() first."
        )

    return _production_module


def record_stage_quantities(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
    accepted_quantity: Decimal = Decimal("0"),
    rejected_quantity: Decimal = Decimal("0"),
    recorded_by: int,
    rejected_reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    accepted_idempotency_key: Optional[str] = None,
    rejected_idempotency_key: Optional[str] = None,
) -> dict:
    """
    Record Production stage quantities through the Production Module.

    The Core adapter deliberately exposes only the integration contract.
    Production business rules remain owned by the Production Module.
    """

    module = get_production_module()

    return module.module.record_stage_quantities(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage_id,
        accepted_quantity=accepted_quantity,
        rejected_quantity=rejected_quantity,
        recorded_by=recorded_by,
        rejected_reason_code=rejected_reason_code,
        notes=notes,
        accepted_idempotency_key=accepted_idempotency_key,
        rejected_idempotency_key=rejected_idempotency_key,
    )


def release_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
) -> dict:
    """
    Release a Planned Production order through the Production Module.
    """

    module = get_production_module()

    return module.module.release_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        recorded_by=recorded_by,
    )


def start_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Start a Released Production order through the Production Module.
    """

    module = get_production_module()

    return module.module.start_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        recorded_by=recorded_by,
        stage_id=stage_id,
    )


def start_stage(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
    recorded_by: int,
) -> dict:
    """
    Start a READY production stage through the Production Module.

    This is a stage-level operation and does not attempt to transition
    the overall Production Order state from STARTED to STARTED.
    """

    module = get_production_module()

    return module.module.start_stage(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage_id,
        recorded_by=recorded_by,
    )


def hold_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    reason: str,
    problem_type: str = "Production Problem",
    affected_quantity: Decimal = Decimal("0"),
    stage_id: Optional[int] = None,
) -> dict:
    """
    Place a Production order on hold through the Production Module.
    """

    module = get_production_module()

    return module.module.hold_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        recorded_by=recorded_by,
        reason=reason,
        problem_type=problem_type,
        affected_quantity=affected_quantity,
        stage_id=stage_id,
    )


def resume_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Resume a held Production order through the Production Module.
    """

    module = get_production_module()

    return module.module.resume_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        recorded_by=recorded_by,
        stage_id=stage_id,
    )


def complete_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Complete a Production order through the Production Module.
    """

    module = get_production_module()

    return module.module.complete_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        recorded_by=recorded_by,
        stage_id=stage_id,
    )


def get_eta_operational_snapshot(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
) -> dict:
    """
    Retrieve the operational ETA snapshot for a Production order.

    Core receives the Production Module's calculated operational view
    through the public module contract.

    ETA calculation and Production business rules remain owned by the
    Production Module.
    """

    module = get_production_module()

    return module.module.get_eta_operational_snapshot(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )


__all__ = [
    "configure_production_module",
    "get_production_module",
    "record_stage_quantities",
    "release_order",
    "start_order",
    "start_stage",
    "hold_order",
    "resume_order",
    "complete_order",
    "get_eta_operational_snapshot",
]