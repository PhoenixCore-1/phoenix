from datetime import datetime
from decimal import Decimal
from typing import Optional

from .models import (
    ManufacturingOrder,
    ProductionState,
    StageQuantityLedger,
)
from .state_machine import TransitionResult, transition


def release(
    order: ManufacturingOrder,
    now: Optional[datetime] = None,
) -> TransitionResult:
    return transition(
        order,
        ProductionState.RELEASED,
        now=now,
    )


def start(
    order: ManufacturingOrder,
    now: Optional[datetime] = None,
) -> TransitionResult:
    return transition(
        order,
        ProductionState.STARTED,
        now=now,
    )


def hold(
    order: ManufacturingOrder,
    reason: str,
    now: Optional[datetime] = None,
) -> TransitionResult:
    return transition(
        order,
        ProductionState.HOLD,
        reason=reason,
        now=now,
    )


def resume(
    order: ManufacturingOrder,
    now: Optional[datetime] = None,
) -> TransitionResult:
    return transition(
        order,
        ProductionState.STARTED,
        now=now,
    )


def record_quantity(
    order: ManufacturingOrder,
    *,
    accepted: Decimal = Decimal("0"),
    rejected: Decimal = Decimal("0"),
    rework: Decimal = Decimal("0"),
) -> None:
    """
    Record order-level production quantity.

    This is the existing 1.2 quantity ledger and remains separate
    from stage-level WIP accounting.
    """

    if order.state != ProductionState.STARTED:
        raise ValueError(
            "Quantity can only be recorded while production is STARTED"
        )

    if min(accepted, rejected, rework) < 0:
        raise ValueError(
            "Quantities cannot be negative"
        )

    new_processed = (
        order.quantity.processed
        + accepted
        + rejected
        + rework
    )

    if new_processed > order.quantity.planned:
        raise ValueError(
            "Recorded quantity cannot exceed planned quantity"
        )

    order.quantity.accepted += accepted
    order.quantity.rejected += rejected
    order.quantity.rework += rework


def record_stage_quantity(
    order: ManufacturingOrder,
    stage_quantity: StageQuantityLedger,
    *,
    accepted: Decimal = Decimal("0"),
    rejected: Decimal = Decimal("0"),
    rework: Decimal = Decimal("0"),
) -> None:
    """
    Record quantity against a manufacturing stage.

    Stage accounting is deliberately separate from the order-level
    quantity ledger because the same physical units may pass through
    multiple manufacturing stages.

    The stage ledger owns the stage-specific quantity validation.
    """

    if order.state != ProductionState.STARTED:
        raise ValueError(
            "Stage quantity can only be recorded while production is STARTED"
        )

    if not isinstance(stage_quantity, StageQuantityLedger):
        raise TypeError(
            "stage_quantity must be a StageQuantityLedger"
        )

    stage_quantity.record(
        accepted=accepted,
        rejected=rejected,
        rework=rework,
    )


def complete(
    order: ManufacturingOrder,
    now: Optional[datetime] = None,
) -> TransitionResult:
    return transition(
        order,
        ProductionState.COMPLETED,
        now=now,
    )