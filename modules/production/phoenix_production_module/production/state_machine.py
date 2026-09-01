from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .models import ManufacturingOrder, ProductionState


TRANSITIONS = {
    ProductionState.PLANNED: {
        ProductionState.RELEASED,
        ProductionState.CANCELLED,
    },
    ProductionState.RELEASED: {
        ProductionState.STARTED,
        ProductionState.CANCELLED,
    },
    ProductionState.STARTED: {
        ProductionState.HOLD,
        ProductionState.COMPLETED,
        ProductionState.CANCELLED,
    },
    ProductionState.HOLD: {
        ProductionState.STARTED,
        ProductionState.COMPLETED,
        ProductionState.CANCELLED,
    },
    ProductionState.COMPLETED: set(),
    ProductionState.CANCELLED: set(),
}


@dataclass(frozen=True)
class TransitionResult:
    from_state: ProductionState
    to_state: ProductionState
    changed_at: datetime
    hold_reason: Optional[str] = None


class InvalidTransition(ValueError):
    pass


def transition(
    order: ManufacturingOrder,
    target: ProductionState,
    *,
    reason: Optional[str] = None,
    now: Optional[datetime] = None,
) -> TransitionResult:
    """
    Apply a validated Production state transition.

    ETA timing is recorded alongside lifecycle transitions, while
    ETA calculations remain owned by ETAPlan.
    """

    now = now or datetime.now(timezone.utc)

    if target not in TRANSITIONS[order.state]:
        raise InvalidTransition(
            f"Cannot transition "
            f"{order.state.value} -> {target.value}"
        )

    if target == ProductionState.HOLD and not reason:
        raise InvalidTransition(
            "A Hold requires a reason"
        )

    if (
        target == ProductionState.COMPLETED
        and order.quantity.remaining != 0
    ):
        raise InvalidTransition(
            f"Cannot complete MO with "
            f"{order.quantity.remaining} quantity remaining"
        )

    previous = order.state

    order.state = target

    if target == ProductionState.HOLD:
        order.hold_reason = reason

        _record_hold_started(
            order,
            now,
        )

    elif target == ProductionState.STARTED:
        if previous == ProductionState.RELEASED:
            order.started_at = now

            _record_production_started(
                order,
                now,
            )

        elif previous == ProductionState.HOLD:
            _record_hold_resumed(
                order,
                now,
            )

        order.hold_reason = None

    elif target == ProductionState.COMPLETED:
        order.completed_at = now
        order.hold_reason = None

        if previous == ProductionState.HOLD:
            _record_hold_resumed(
                order,
                now,
            )

        _record_production_completed(
            order,
            now,
        )

    elif target == ProductionState.CANCELLED:
        order.hold_reason = None

        if previous == ProductionState.HOLD:
            _record_hold_resumed(
                order,
                now,
            )

    return TransitionResult(
        from_state=previous,
        to_state=target,
        changed_at=now,
        hold_reason=reason,
    )


def _record_production_started(
    order: ManufacturingOrder,
    started_at: datetime,
) -> None:
    eta = getattr(
        order,
        "eta",
        None,
    )

    if eta is None:
        return

    eta.mark_production_started(
        started_at
    )


def _record_production_completed(
    order: ManufacturingOrder,
    completed_at: datetime,
) -> None:
    eta = getattr(
        order,
        "eta",
        None,
    )

    if eta is None:
        return

    eta.mark_completed(
        completed_at
    )


def _record_hold_started(
    order: ManufacturingOrder,
    hold_started_at: datetime,
) -> None:
    eta = getattr(
        order,
        "eta",
        None,
    )

    if eta is None:
        return

    mark_hold_started = getattr(
        eta,
        "mark_hold_started",
        None,
    )

    if mark_hold_started is None:
        return

    mark_hold_started(
        hold_started_at
    )


def _record_hold_resumed(
    order: ManufacturingOrder,
    resumed_at: datetime,
) -> None:
    eta = getattr(
        order,
        "eta",
        None,
    )

    if eta is None:
        return

    mark_hold_resumed = getattr(
        eta,
        "mark_hold_resumed",
        None,
    )

    if mark_hold_resumed is None:
        return

    mark_hold_resumed(
        resumed_at
    )