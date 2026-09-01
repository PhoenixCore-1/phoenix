from pathlib import Path
import json
"""
Phoenix Production Module -> Phoenix Core integration boundary.

Production Module 1.3.24

The Production domain owns business rules.
This integration layer translates Core database records into
Production domain objects, invokes the domain service, and
persists the resulting state back to Core where required.

Stage quantity rules:

    First stage:
        available input = production order quantity

    Subsequent stage:
        available input = previous stage accepted quantity

    Current stage:
        WIP = input - accepted - rejected

    Rework:
        remains a classification within WIP

Operational ETA snapshot:

    Core-facing read-only projection of:

        - planned ETA
        - current/live ETA
        - required date
        - schedule risk
        - required-date risk
        - operational decision
        - action-required state
        - human-readable summary

Important:
    - The Production Module does not own the Core database schema.
    - The Core quantity ledger remains immutable.
    - Stage input cannot exceed physically available quantity.
    - Rejected quantity never becomes downstream input.
    - Existing idempotency behaviour is preserved.
    - Idempotent retries are recognised before physical quantity
      validation is performed.
    - Stage ordering remains compatible with Core schemas that use
      stage_id rather than stage_sequence.
    - Operational ETA snapshot calculation is read-only.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .core_adapter import record_quantity
from .models import (
    ManufacturingOrder,
    ProductionState,
    StageQuantityLedger,
)
from .service import ProductionService


SERVICE = ProductionService()


CORE_TO_DOMAIN_STATE = {
    "Planned": ProductionState.PLANNED,
    "Released to Production": ProductionState.RELEASED,
    "In Production": ProductionState.STARTED,
    "On Hold": ProductionState.HOLD,
    "Completed": ProductionState.COMPLETED,
    "Cancelled": ProductionState.CANCELLED,
}


DOMAIN_TO_CORE_STATE = {
    ProductionState.PLANNED: "Planned",
    ProductionState.RELEASED: "Released to Production",
    ProductionState.STARTED: "In Production",
    ProductionState.HOLD: "On Hold",
    ProductionState.COMPLETED: "Completed",
    ProductionState.CANCELLED: "Cancelled",
}



# ============================================================
# 1.4 CONFIGURABLE WORKING-DAY ETA
# ============================================================

def _load_eta_configuration() -> dict:
    """
    Load the external Production ETA configuration.

    The lead time is intentionally configurable and is not
    hard-coded into the Production workflow.
    """

    config_path = (
        Path(__file__).resolve().parent.parent
        / "eta_config.json"
    )

    if not config_path.exists():
        raise RuntimeError(
            "Production ETA configuration not found: "
            + str(config_path)
        )

    with config_path.open(
        "r",
        encoding="utf-8-sig",
    ) as handle:
        config = json.load(handle)

    lead_time = int(
        config.get(
            "lead_time_working_days",
            0,
        )
    )

    if lead_time <= 0:
        raise ValueError(
            "lead_time_working_days must be greater than zero"
        )

    return config


def _configured_working_day_eta(
    start_at: datetime,
) -> datetime:
    """
    Calculate ETA from the Production Process Date.

    The configured number of working days is added while
    excluding weekends and configured public holidays.
    """

    from datetime import timedelta

    config = _load_eta_configuration()

    lead_time = int(
        config.get(
            "lead_time_working_days",
            0,
        )
    )

    calendar = config.get(
        "calendar",
        {},
    )

    exclude_weekends = bool(
        calendar.get(
            "exclude_weekends",
            True,
        )
    )

    exclude_public_holidays = bool(
        calendar.get(
            "exclude_public_holidays",
            True,
        )
    )

    public_holidays = set(
        calendar.get(
            "public_holidays",
            [],
        )
    )

    if isinstance(start_at, str):
        result = datetime.fromisoformat(
            start_at.replace("Z", "+00:00")
        )
    else:
        result = start_at

    working_days = 0

    while working_days < lead_time:

        result += timedelta(
            days=1
        )

        if (
            exclude_weekends
            and result.weekday() >= 5
        ):
            continue

        if (
            exclude_public_holidays
            and result.date().isoformat()
            in public_holidays
        ):
            continue

        working_days += 1

    return result



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_datetime(value: Optional[str]) -> datetime:
    if value:
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            pass

    return datetime.now(timezone.utc)


def _table_columns(db, table_name: str) -> set[str]:
    """
    Return the available columns for a Core table.

    This keeps the Production integration boundary compatible with
    Core schema variations without making the Production domain own
    the Core schema.
    """

    rows = db.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    columns = set()

    for row in rows:
        try:
            columns.add(str(row["name"]))
        except (TypeError, IndexError):
            columns.add(str(row[1]))

    return columns


def _stage_order_expression(db) -> str:
    """
    Determine the safest Core-compatible stage ordering expression.

    Preferred:
        stage_sequence

    Compatibility fallback:
        sequence

    Final fallback:
        stage_id
    """

    columns = _table_columns(
        db,
        "production_stages",
    )

    if "stage_sequence" in columns:
        return "stage_sequence"

    if "sequence" in columns:
        return "sequence"

    return "stage_id"


def _load_quantity_totals(
    db,
    organisation_id: int,
    production_order_id: int,
    stage_id: Optional[int] = None,
) -> tuple[Decimal, Decimal, Decimal]:
    """
    Read immutable quantity ledger totals.

    When stage_id is supplied, totals are calculated only for
    that production stage.

    Returns:
        accepted, rejected, rework
    """

    if stage_id is None:
        rows = db.execute(
            """
            SELECT
                quantity_type,
                COALESCE(SUM(quantity), 0)
            FROM production_quantity_ledger
            WHERE organisation_id=?
              AND production_order_id=?
            GROUP BY quantity_type
            """,
            (
                organisation_id,
                production_order_id,
            ),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT
                quantity_type,
                COALESCE(SUM(quantity), 0)
            FROM production_quantity_ledger
            WHERE organisation_id=?
              AND production_order_id=?
              AND stage_id=?
            GROUP BY quantity_type
            """,
            (
                organisation_id,
                production_order_id,
                int(stage_id),
            ),
        ).fetchall()

    accepted = Decimal("0")
    rejected = Decimal("0")
    rework = Decimal("0")

    for row in rows:
        quantity_type = str(row[0]).upper()
        quantity = Decimal(str(row[1] or 0))

        if quantity_type == "ACCEPTED":
            accepted += quantity

        elif quantity_type == "REJECTED":
            rejected += quantity

        elif quantity_type == "REWORK":
            rework += quantity

    return accepted, rejected, rework


def _get_existing_idempotency_id(
    db,
    *,
    organisation_id: int,
    idempotency_key: Optional[str],
) -> Optional[int]:
    """
    Return the existing quantity ledger ID for an idempotency key.

    Returns None when the key has not previously been recorded.

    This lookup intentionally happens before physical quantity
    validation so that a true retry is treated as a retry rather
    than as a new quantity transaction.
    """

    if not idempotency_key:
        return None

    row = db.execute(
        """
        SELECT quantity_ledger_id
        FROM production_quantity_ledger
        WHERE organisation_id=?
          AND idempotency_key=?
        LIMIT 1
        """,
        (
            organisation_id,
            idempotency_key,
        ),
    ).fetchone()

    if not row:
        return None

    return int(row[0])


def _load_domain_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
) -> ManufacturingOrder:
    """
    Load a Core Production Order into the Production domain.

    Phoenix Core remains the owner of the database schema.
    The Production Module translates the persisted Core record
    into a ManufacturingOrder.

    ETA values persisted by the Core Production API are restored
    into the domain ETAPlan so operational ETA snapshots reflect
    the actual stored ETA.
    """

    row = db.execute(
        """
        SELECT
            production_order_id,
            organisation_id,
            product_ref,
            quantity_ordered,
            required_date,
            status,
            current_location,
            planned_eta_at,
            current_eta_at
        FROM production_orders
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (
            production_order_id,
            organisation_id,
        ),
    ).fetchone()

    if not row:
        raise ValueError(
            "Production order not found"
        )

    status_map = {
        "Planned": ProductionState.PLANNED,
        "Released to Production": ProductionState.RELEASED,
        "In Production": ProductionState.STARTED,
        "On Hold": ProductionState.HOLD,
        "Completed": ProductionState.COMPLETED,
        "Cancelled": ProductionState.CANCELLED,
    }

    domain_state = status_map.get(
        str(row["status"]),
        ProductionState.PLANNED,
    )

    accepted, rejected, rework = (
        _load_quantity_totals(
            db,
            organisation_id,
            production_order_id,
        )
    )

    order = ManufacturingOrder(
        tenant_id=str(organisation_id),
        site_id=str(row["current_location"] or ""),
        product_id=str(row["product_ref"] or ""),
        planned_quantity=Decimal(
            str(row["quantity_ordered"])
        ),
        required_date=_parse_datetime(
            row["required_date"]
        ),
    )

    # ------------------------------------------------------------
    # 1.4 PERSISTED ETA RESTORE
    #
    # ManufacturingOrder creates a fresh ETAPlan in
    # __post_init__. Restore the ETA values persisted by Core.
    # ------------------------------------------------------------

    planned_eta_value = row["planned_eta_at"]
    current_eta_value = row["current_eta_at"]

    if planned_eta_value:
        order.eta.planned_eta = _parse_datetime(
            planned_eta_value
        )

    if current_eta_value:
        order.eta.current_eta = _parse_datetime(
            current_eta_value
        )

    order.state = domain_state

    order.quantity.accepted = accepted
    order.quantity.rejected = rejected
    order.quantity.rework = rework

    return order


def get_eta_operational_snapshot(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
) -> dict:
    """
    Return the read-only operational ETA snapshot for a
    Core production order.

    This is the 1.3.24 Production -> Core integration boundary.

    The Core layer does not need to know how ETA risk is calculated.

    The flow is:

        Core DB record
            ->
        Production domain order
            ->
        ProductionService
            ->
        ETAOperationalSnapshot
            ->
        Core-safe dictionary

    No database records are modified.

    Returns a dictionary containing:

        production_order_id
        planned_eta
        current_eta
        required_date
        schedule_risk
        required_date_risk
        decision
        action_required
        summary
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    snapshot = (
        SERVICE.calculate_eta_operational_snapshot(
            order,
        )
    )

    return {
        "production_order_id": production_order_id,
        "planned_eta": (
            snapshot.planned_eta.isoformat()
            if snapshot.planned_eta is not None
            else None
        ),
        "current_eta": (
            snapshot.current_eta.isoformat()
            if snapshot.current_eta is not None
            else None
        ),
        "required_date": (
            snapshot.required_date.isoformat()
            if snapshot.required_date is not None
            else None
        ),
        "schedule_risk": (
            snapshot.schedule_risk.value
        ),
        "required_date_risk": (
            snapshot.required_date_risk.value
        ),
        "decision": (
            snapshot.decision.value
        ),
        "action_required": bool(
            snapshot.action_required
        ),
        "summary": str(
            snapshot.summary
        ),
    }


# ============================================================
# EXISTING STAGE QUANTITY FUNCTIONS
# ============================================================


def _get_current_stage(
    db,
    *,
    production_order_id: int,
    stage_id: Optional[int] = None,
):
    order_expression = _stage_order_expression(db)

    if stage_id is not None:
        row = db.execute(
            """
            SELECT *
            FROM production_stages
            WHERE stage_id=?
              AND production_order_id=?
            """,
            (
                stage_id,
                production_order_id,
            ),
        ).fetchone()

        if not row:
            raise ValueError("Production stage not found")

        return row

    row = db.execute(
        f"""
        SELECT *
        FROM production_stages
        WHERE production_order_id=?
          AND status IN (
              'In Progress',
              'On Hold',
              'Ready'
          )
        ORDER BY {order_expression}
        LIMIT 1
        """,
        (
            production_order_id,
        ),
    ).fetchone()

    if row:
        return row

    return db.execute(
        f"""
        SELECT *
        FROM production_stages
        WHERE production_order_id=?
        ORDER BY {order_expression}
        LIMIT 1
        """,
        (
            production_order_id,
        ),
    ).fetchone()


def _get_stage_sequence(
    db,
    *,
    production_order_id: int,
    stage_id: int,
) -> int:
    """
    Return the logical stage ordering value.

    Core schemas with stage_sequence use that field.
    Older/alternate Core schemas fall back to sequence or stage_id.
    """

    order_expression = _stage_order_expression(db)

    row = db.execute(
        f"""
        SELECT {order_expression}
        FROM production_stages
        WHERE stage_id=?
          AND production_order_id=?
        """,
        (
            stage_id,
            production_order_id,
        ),
    ).fetchone()

    if not row:
        raise ValueError("Production stage not found")

    return int(row[0])


def _get_previous_stage(
    db,
    *,
    production_order_id: int,
    stage_id: int,
):
    """
    Return the immediately preceding configured production stage.
    """

    order_expression = _stage_order_expression(db)

    current_sequence = _get_stage_sequence(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    return db.execute(
        f"""
        SELECT *
        FROM production_stages
        WHERE production_order_id=?
          AND {order_expression} < ?
        ORDER BY {order_expression} DESC
        LIMIT 1
        """,
        (
            production_order_id,
            current_sequence,
        ),
    ).fetchone()


def _get_stage_available_input(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
) -> Decimal:
    """
    Determine the physical quantity currently available to a stage.

    First stage:
        production order quantity

    Subsequent stage:
        previous stage accepted quantity

    Rejected quantity is intentionally excluded.
    """

    order_row = db.execute(
        """
        SELECT quantity_ordered
        FROM production_orders
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (
            production_order_id,
            organisation_id,
        ),
    ).fetchone()

    if not order_row:
        raise ValueError("Production order not found")

    previous_stage = _get_previous_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if previous_stage is None:
        return Decimal(
            str(order_row["quantity_ordered"])
        )

    previous_accepted, _, _ = _load_quantity_totals(
        db,
        organisation_id,
        production_order_id,
        int(previous_stage["stage_id"]),
    )

    return previous_accepted


def _load_stage_quantity_ledger(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
    input_quantity: Decimal,
) -> StageQuantityLedger:
    """
    Build a Production-domain StageQuantityLedger from
    the immutable Core quantity ledger.
    """

    accepted, rejected, rework = _load_quantity_totals(
        db,
        organisation_id,
        production_order_id,
        stage_id,
    )

    return StageQuantityLedger(
        input_quantity=input_quantity,
        accepted=accepted,
        rejected=rejected,
        rework=rework,
    )


def get_stage_quantity_status(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
) -> dict:
    """
    Return the read-only quantity/WIP status of one stage.

    No database rows are modified.
    """

    order_row = db.execute(
        """
        SELECT quantity_ordered
        FROM production_orders
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (
            production_order_id,
            organisation_id,
        ),
    ).fetchone()

    if not order_row:
        raise ValueError("Production order not found")

    stage = db.execute(
        """
        SELECT
            stage_id,
            stage_code,
            stage_name,
            status,
            location
        FROM production_stages
        WHERE stage_id=?
          AND production_order_id=?
        """,
        (
            stage_id,
            production_order_id,
        ),
    ).fetchone()

    if not stage:
        raise ValueError("Production stage not found")

    previous_stage = _get_previous_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    stage_sequence = _get_stage_sequence(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if previous_stage is None:
        input_quantity = Decimal(
            str(order_row["quantity_ordered"])
        )
        previous_stage_id = None
        previous_stage_accepted = None

    else:
        (
            previous_accepted,
            _,
            _,
        ) = _load_quantity_totals(
            db,
            organisation_id,
            production_order_id,
            int(previous_stage["stage_id"]),
        )

        input_quantity = previous_accepted
        previous_stage_id = int(
            previous_stage["stage_id"]
        )
        previous_stage_accepted = previous_accepted

    ledger = _load_stage_quantity_ledger(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage_id,
        input_quantity=input_quantity,
    )

    return {
        "production_order_id": production_order_id,
        "stage_id": int(stage["stage_id"]),
        "stage_code": stage["stage_code"],
        "stage_name": stage["stage_name"],
        "stage_sequence": stage_sequence,
        "stage_status": stage["status"],
        "location": stage["location"],
        "previous_stage_id": previous_stage_id,
        "previous_stage_accepted_quantity": (
            None
            if previous_stage_accepted is None
            else str(previous_stage_accepted)
        ),
        "input_quantity": str(
            ledger.input_quantity
        ),
        "accepted_quantity": str(
            ledger.accepted
        ),
        "rejected_quantity": str(
            ledger.rejected
        ),
        "rework_quantity": str(
            ledger.rework
        ),
        "wip_quantity": str(
            ledger.wip
        ),
        "available_to_next_stage": str(
            ledger.available_to_next_stage
        ),
        "is_complete": ledger.is_complete,
    }


def _validate_stage_output_available(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: int,
    accepted_quantity: Decimal,
    rejected_quantity: Decimal,
) -> Decimal:
    """
    Enforce the physical stage-input constraint.

    Existing output already recorded against the stage is included.

    Idempotent quantities must be passed in as zero by the caller.

    Therefore:

        existing accepted
        + existing rejected
        + new accepted
        + new rejected

    may not exceed the stage's available input.

    Returns:
        available input quantity
    """

    available_input = _get_stage_available_input(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    existing_accepted, existing_rejected, _ = (
        _load_quantity_totals(
            db,
            organisation_id,
            production_order_id,
            stage_id,
        )
    )

    new_total = (
        existing_accepted
        + existing_rejected
        + accepted_quantity
        + rejected_quantity
    )

    if new_total > available_input:
        remaining_input = (
            available_input
            - existing_accepted
            - existing_rejected
        )

        raise ValueError(
            "Stage output exceeds available input: "
            f"available={available_input}, "
            f"already_accounted="
            f"{existing_accepted + existing_rejected}, "
            f"remaining={remaining_input}, "
            f"requested="
            f"{accepted_quantity + rejected_quantity}"
        )

    return available_input


def _write_event(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    user_id: int,
    event_type: str,
    stage_id: Optional[int] = None,
    payload_json: str = "{}",
) -> None:
    db.execute(
        """
        INSERT INTO production_events(
            organisation_id,
            production_order_id,
            stage_id,
            event_type,
            user_id,
            payload_json,
            created_at
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            organisation_id,
            production_order_id,
            stage_id,
            event_type,
            user_id,
            payload_json,
            utc_now(),
        ),
    )


def _persist_order_state(
    db,
    *,
    production_order_id: int,
    state: ProductionState,
    updated_at: Optional[str] = None,
) -> None:
    status = DOMAIN_TO_CORE_STATE[state]

    db.execute(
        """
        UPDATE production_orders
        SET status=?,
            updated_at=?
        WHERE production_order_id=?
        """,
        (
            status,
            updated_at or utc_now(),
            production_order_id,
        ),
    )


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
    Record stage output in the immutable Core quantity ledger.

    Production Module 1.3.8 maintains the physical quantity
    constraint while fixing idempotent retries.

    Idempotency is checked before quantity availability validation.

    This means:

        first submission
            -> validate physical quantity
            -> write ledger entry

        repeated submission with same key
            -> recognise existing ledger entry
            -> do not count the quantity again
            -> return the existing ledger ID
    """

    accepted_quantity = Decimal(
        str(accepted_quantity)
    )

    rejected_quantity = Decimal(
        str(rejected_quantity)
    )

    if accepted_quantity < 0:
        raise ValueError(
            "Accepted quantity cannot be negative"
        )

    if rejected_quantity < 0:
        raise ValueError(
            "Rejected quantity cannot be negative"
        )

    if (
        accepted_quantity == 0
        and rejected_quantity == 0
    ):
        return {}

    accepted_existing_id = (
        _get_existing_idempotency_id(
            db,
            organisation_id=organisation_id,
            idempotency_key=accepted_idempotency_key,
        )
    )

    rejected_existing_id = (
        _get_existing_idempotency_id(
            db,
            organisation_id=organisation_id,
            idempotency_key=rejected_idempotency_key,
        )
    )

    effective_accepted_quantity = (
        Decimal("0")
        if accepted_existing_id is not None
        else accepted_quantity
    )

    effective_rejected_quantity = (
        Decimal("0")
        if rejected_existing_id is not None
        else rejected_quantity
    )

    if (
        effective_accepted_quantity > 0
        or effective_rejected_quantity > 0
    ):
        _validate_stage_output_available(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage_id,
            accepted_quantity=effective_accepted_quantity,
            rejected_quantity=effective_rejected_quantity,
        )

    results = {}

    if accepted_quantity > 0:
        results["accepted_ledger_id"] = record_quantity(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage_id,
            quantity_type="ACCEPTED",
            quantity=accepted_quantity,
            uom_code="EA",
            recorded_by=recorded_by,
            notes=notes,
            idempotency_key=accepted_idempotency_key,
        )

    if rejected_quantity > 0:
        results["rejected_ledger_id"] = record_quantity(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage_id,
            quantity_type="REJECTED",
            quantity=rejected_quantity,
            uom_code="EA",
            recorded_by=recorded_by,
            reason_code=rejected_reason_code,
            notes=notes,
            idempotency_key=rejected_idempotency_key,
        )

    return results


def release_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
) -> dict:
    """
    Release a Planned production order.
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    result = SERVICE.release_order(order)

    _persist_order_state(
        db,
        production_order_id=production_order_id,
        state=order.state,
        updated_at=result.changed_at.isoformat(
            timespec="seconds"
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        user_id=recorded_by,
        event_type="RELEASE",
        payload_json="{}",
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "from_state": result.from_state.value,
        "to_state": result.to_state.value,
        "status": DOMAIN_TO_CORE_STATE[
            result.to_state
        ],
    }


def start_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Start a Released production order and its active stage.
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    stage = _get_current_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if not stage:
        raise ValueError(
            "Production order has no production stages"
        )

    result = SERVICE.start_order(order)

    changed_at = result.changed_at.isoformat(
        timespec="seconds"
    )

    _persist_order_state(
        db,
        production_order_id=production_order_id,
        state=order.state,
        updated_at=changed_at,
    )

    db.execute(
        """
        UPDATE production_orders
        SET current_stage_id=?,
            current_location=?,
            planned_start_at=?,
            planned_finish_at=?,
            planned_eta_at=?,
            current_eta_at=?,
            eta_source=?,
            eta_override_reason=NULL,
            eta_updated_at=?,
            eta_updated_by=?,
            updated_at=?
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (
            stage["stage_id"],
            stage["location"],
            changed_at,
            _configured_working_day_eta(_parse_datetime(changed_at)),
            _configured_working_day_eta(_parse_datetime(changed_at)),
            _configured_working_day_eta(_parse_datetime(changed_at)),
            "CONFIGURED_WORKING_DAY_LEAD_TIME",
            changed_at,
            recorded_by,
            changed_at,
            production_order_id,
            organisation_id,
        ),
    )

    db.execute(
        """
        UPDATE production_stages
        SET status='In Progress',
            start_datetime=COALESCE(
                start_datetime,
                ?
            )
        WHERE stage_id=?
        """,
        (
            changed_at,
            stage["stage_id"],
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="START",
        payload_json="{}",
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "stage_id": stage["stage_id"],
        "stage_name": stage["stage_name"],
        "from_state": result.from_state.value,
        "to_state": result.to_state.value,
        "status": DOMAIN_TO_CORE_STATE[
            result.to_state
        ],
    }


def start_stage(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: int,
) -> dict:
    """
    Start a Ready production stage without changing the
    overall Production Order lifecycle state.
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    stage = _get_current_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if not stage:
        raise ValueError(
            "Production order does not contain the requested "
            "production stage"
        )

    if order.state.value != "STARTED":
        raise ValueError(
            "Production order must be STARTED before "
            "starting a stage; "
            f"current state is {order.state.value}"
        )

    if stage["status"] not in (
        "Ready",
        "Waiting",
    ):
        raise ValueError(
            "Production stage cannot be started from status "
            f"{stage['status']}"
        )

    # ------------------------------------------------------------
    # PRODUCTION 1.4 — STAGE SEQUENCING ENFORCEMENT
    #
    # A production stage may only start when every preceding
    # stage, according to stage_sequence, is Complete.
    #
    # This is intentionally generic and does not depend on
    # stage names such as Production, Plating, Assembly or
    # Packaging.
    # ------------------------------------------------------------

    preceding_stage = db.execute(
        """
        SELECT
            stage_id,
            stage_name,
            status,
            stage_sequence
        FROM production_stages
        WHERE production_order_id=?
          AND stage_sequence < ?
        ORDER BY stage_sequence DESC
        LIMIT 1
        """,
        (
            production_order_id,
            stage["stage_sequence"],
        ),
    ).fetchone()

    if preceding_stage:
        if preceding_stage["status"] != "Complete":
            raise ValueError(
                "Production stage cannot be started because "
                "the preceding stage is not complete: "
                f"{preceding_stage['stage_name']} "
                f"(status={preceding_stage['status']})"
            )

    changed_at = utc_now()

    db.execute(
        """
        UPDATE production_stages
        SET status='In Progress',
            start_datetime=COALESCE(
                start_datetime,
                ?
            )
        WHERE stage_id=?
        """,
        (
            changed_at,
            stage["stage_id"],
        ),
    )

    db.execute(
        """
        UPDATE production_orders
        SET current_stage_id=?,
            current_location=?,
            status='In Production',
            updated_at=?
        WHERE production_order_id=?
        """,
        (
            stage["stage_id"],
            stage["location"],
            changed_at,
            production_order_id,
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="START_STAGE",
        payload_json="{}",
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "stage_id": stage["stage_id"],
        "stage_name": stage["stage_name"],
        "from_status": stage["status"],
        "to_status": "In Progress",
        "status": "In Production",
    }


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
    Place a production stage on hold.
    """

    reason = (reason or "").strip()

    if not reason:
        raise ValueError(
            "A Hold requires a reason"
        )

    affected_quantity = Decimal(
        str(affected_quantity)
    )

    if affected_quantity < 0:
        raise ValueError(
            "Affected quantity cannot be negative"
        )

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    stage = _get_current_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if not stage:
        raise ValueError(
            "Production order has no production stage"
        )

    changed_at = utc_now()

    if (
        order.state == ProductionState.RELEASED
        and stage["status"] == "Ready"
    ):
        db.execute(
            """
            UPDATE production_stages
            SET status='On Hold',
                notes=?
            WHERE stage_id=?
            """,
            (
                reason,
                stage["stage_id"],
            ),
        )

        hold = db.execute(
            """
            INSERT INTO production_holds(
                organisation_id,
                production_order_id,
                stage_id,
                problem_type,
                description,
                affected_quantity,
                reported_by,
                reported_at,
                status
            )
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (
                organisation_id,
                production_order_id,
                stage["stage_id"],
                problem_type or "Production Problem",
                reason,
                str(affected_quantity),
                recorded_by,
                changed_at,
                "Open",
            ),
        )

        _write_event(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage["stage_id"],
            user_id=recorded_by,
            event_type="HOLD",
            payload_json=(
                '{"hold_level":"stage",'
                '"order_state":"RELEASED",'
                '"previous_stage_status":"Ready"}'
            ),
        )

        db.commit()

        return {
            "production_order_id": production_order_id,
            "stage_id": stage["stage_id"],
            "hold_id": int(
                hold.lastrowid
            ),
            "from_state": "RELEASED",
            "to_state": "RELEASED",
            "status": "Released to Production",
            "stage_status": "On Hold",
            "reason": reason,
        }

    result = SERVICE.hold_order(
        order,
        reason=reason,
    )

    changed_at = result.changed_at.isoformat(
        timespec="seconds"
    )

    _persist_order_state(
        db,
        production_order_id=production_order_id,
        state=order.state,
        updated_at=changed_at,
    )

    db.execute(
        """
        UPDATE production_stages
        SET status='On Hold',
            notes=?
        WHERE stage_id=?
        """,
        (
            reason,
            stage["stage_id"],
        ),
    )

    hold = db.execute(
        """
        INSERT INTO production_holds(
            organisation_id,
            production_order_id,
            stage_id,
            problem_type,
            description,
            affected_quantity,
            reported_by,
            reported_at,
            status
        )
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (
            organisation_id,
            production_order_id,
            stage["stage_id"],
            problem_type or "Production Problem",
            reason,
            str(affected_quantity),
            recorded_by,
            changed_at,
            "Open",
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="HOLD",
        payload_json="{}",
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "stage_id": stage["stage_id"],
        "hold_id": int(
            hold.lastrowid
        ),
        "from_state": result.from_state.value,
        "to_state": result.to_state.value,
        "status": DOMAIN_TO_CORE_STATE[
            result.to_state
        ],
        "stage_status": "On Hold",
        "reason": reason,
    }


def _apply_resolved_hold_eta_impact(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    hold_id: int,
    resolved_at: str,
    recorded_by: int,
) -> dict:
    """
    Apply the actual duration of a resolved production hold
    to the Production Order's current ETA.

    Phoenix Production Module 1.4 temporary ETA policy:

        planned_eta_at
            remains the base / production-process ETA

        current_eta_at
            = existing current ETA
              + actual resolved hold duration

    The verified lead-time calculation is intentionally NOT
    changed by this patch.

    The hold duration is persisted in production_holds so the
    operational impact remains auditable.
    """

    from datetime import datetime, timedelta

    hold = db.execute(
        """
        SELECT
            hold_id,
            reported_at,
            resolved_at
        FROM production_holds
        WHERE organisation_id=?
          AND production_order_id=?
          AND hold_id=?
        """,
        (
            organisation_id,
            production_order_id,
            hold_id,
        ),
    ).fetchone()

    if not hold:
        raise ValueError(
            "Production hold not found"
        )

    if not hold["reported_at"]:
        raise ValueError(
            "Production hold has no reported_at timestamp"
        )

    hold_started_at = datetime.fromisoformat(
        str(hold["reported_at"])
    )

    hold_resolved_at = datetime.fromisoformat(
        str(resolved_at)
    )

    duration_seconds = (
        hold_resolved_at - hold_started_at
    ).total_seconds()

    if duration_seconds < 0:
        raise ValueError(
            "Production hold resolved_at cannot be before reported_at"
        )

    eta_impact_minutes = int(
        round(duration_seconds / 60.0)
    )

    # Persist actual hold impact.
    db.execute(
        """
        UPDATE production_holds
        SET eta_impact_minutes=?,
            eta_recalculated_at=?
        WHERE organisation_id=?
          AND production_order_id=?
          AND hold_id=?
        """,
        (
            eta_impact_minutes,
            resolved_at,
            organisation_id,
            production_order_id,
            hold_id,
        ),
    )

    order = db.execute(
        """
        SELECT
            planned_eta_at,
            current_eta_at
        FROM production_orders
        WHERE organisation_id=?
          AND production_order_id=?
        """,
        (
            organisation_id,
            production_order_id,
        ),
    ).fetchone()

    if not order:
        raise ValueError(
            "Production order not found"
        )

    current_eta = order["current_eta_at"]

    new_current_eta_value = None

    # If no current ETA exists yet, record the hold impact
    # but do not invent an ETA.
    if current_eta:
        current_eta_dt = datetime.fromisoformat(
            str(current_eta)
        )

        new_current_eta = (
            current_eta_dt
            + timedelta(
                minutes=eta_impact_minutes
            )
        )

        new_current_eta_value = (
            new_current_eta.isoformat(
                timespec="seconds"
            )
        )

        db.execute(
            """
            UPDATE production_orders
            SET current_eta_at=?,
                eta_source=?,
                eta_updated_at=?,
                eta_updated_by=?,
                updated_at=?
            WHERE organisation_id=?
              AND production_order_id=?
            """,
            (
                new_current_eta_value,
                "PRODUCTION_PROCESS_DATE",
                resolved_at,
                recorded_by,
                resolved_at,
                organisation_id,
                production_order_id,
            ),
        )

    else:
        db.execute(
            """
            UPDATE production_orders
            SET eta_source=?,
                eta_updated_at=?,
                eta_updated_by=?,
                updated_at=?
            WHERE organisation_id=?
              AND production_order_id=?
            """,
            (
                "PRODUCTION_PROCESS_DATE",
                resolved_at,
                recorded_by,
                resolved_at,
                organisation_id,
                production_order_id,
            ),
        )

    return {
        "hold_id": hold_id,
        "eta_impact_minutes": eta_impact_minutes,
        "previous_current_eta": current_eta,
        "new_current_eta": new_current_eta_value,
        "eta_source": "PRODUCTION_PROCESS_DATE",
    }


def resume_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Resume a production hold.

    Phoenix Production Module 1.4 supports two hold levels:

    1. Stage-level hold
       - Production Order is HOLD.
       - Requested stage is On Hold.
       - Active production_holds row exists for that stage.
       - Resume restores the order to STARTED / In Production.
       - The held stage is restored to In Progress.

    2. Order-level hold
       - Production Order is HOLD.
       - Resume uses the domain service transition.
       - The active production hold is resolved.
       - The current stage is restored to In Progress or Ready.

    Stage-level hold/resume is handled before the generic
    order-level resume path because the stage hold is the
    authoritative operational state.
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    stage = _get_current_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if not stage:
        raise ValueError(
            "Production order has no production stage"
        )

    changed_at = utc_now()

    # ------------------------------------------------------------
    # 1.4 STAGE-LEVEL HOLD RESUME
    #
    # A stage hold places the Production Order into HOLD and the
    # affected stage into On Hold.
    #
    # Resume must therefore restore:
    #
    #     HOLD -> STARTED
    #     On Hold -> In Progress
    #
    # and resolve the active production_holds record.
    # ------------------------------------------------------------

    if (
        order.state == ProductionState.HOLD
        and stage["status"] == "On Hold"
    ):
        open_hold = db.execute(
            """
            SELECT hold_id
            FROM production_holds
            WHERE organisation_id=?
              AND production_order_id=?
              AND stage_id=?
              AND status='Open'
            ORDER BY hold_id DESC
            LIMIT 1
            """,
            (
                organisation_id,
                production_order_id,
                stage["stage_id"],
            ),
        ).fetchone()

        if not open_hold:
            raise ValueError(
                "No active production hold exists"
            )

        # Restore the Production Order to STARTED.
        order.state = ProductionState.STARTED

        _persist_order_state(
            db,
            production_order_id=production_order_id,
            state=order.state,
            updated_at=changed_at,
        )

        # A stage that has already started resumes as In Progress.
        restored_stage_status = "In Progress"

        db.execute(
            """
            UPDATE production_stages
            SET status=?
            WHERE stage_id=?
            """,
            (
                restored_stage_status,
                stage["stage_id"],
            ),
        )

        # Resolve the active stage hold.
        db.execute(
            """
            UPDATE production_holds
            SET status='Resolved',
                resolution='Production resumed',
                resolved_at=?,
                resolved_by=?
            WHERE hold_id=?
            """,
            (
                changed_at,
                recorded_by,
                open_hold["hold_id"],
            ),
        )

        eta_impact = _apply_resolved_hold_eta_impact(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            hold_id=int(open_hold["hold_id"]),
            resolved_at=changed_at,
            recorded_by=recorded_by,
        )

        _write_event(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage["stage_id"],
            user_id=recorded_by,
            event_type="RESUME",
            payload_json=(
                '{"hold_level":"stage",'
                '"restored_stage_status":"In Progress",'
                '"order_state":"STARTED"}'
            ),
        )

        _write_event(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage["stage_id"],
            user_id=recorded_by,
            event_type="ETA_HOLD_IMPACT",
            payload_json=(
                '{"hold_id":'
                + str(eta_impact["hold_id"])
                + ','
                '"eta_impact_minutes":'
                + str(eta_impact["eta_impact_minutes"])
                + ','
                '"eta_source":"PRODUCTION_PROCESS_DATE"}'
            ),
        )

        db.commit()

        return {
            "production_order_id": production_order_id,
            "stage_id": stage["stage_id"],
            "from_state": "HOLD",
            "to_state": "STARTED",
            "status": "In Production",
            "stage_status": "In Progress",
        }

    # ------------------------------------------------------------
    # 1.4 GENERIC ORDER-LEVEL HOLD RESUME
    # ------------------------------------------------------------

    if order.state != ProductionState.HOLD:
        raise ValueError(
            "Production order is not on hold"
        )

    result = SERVICE.resume_order(order)

    changed_at = result.changed_at.isoformat(
        timespec="seconds"
    )

    _persist_order_state(
        db,
        production_order_id=production_order_id,
        state=order.state,
        updated_at=changed_at,
    )

    restored_stage_status = (
        "In Progress"
        if stage["start_datetime"]
        else "Ready"
    )

    db.execute(
        """
        UPDATE production_stages
        SET status=?
        WHERE stage_id=?
        """,
        (
            restored_stage_status,
            stage["stage_id"],
        ),
    )

    open_hold = db.execute(
        """
        SELECT hold_id
        FROM production_holds
        WHERE organisation_id=?
          AND production_order_id=?
          AND stage_id=?
          AND status='Open'
        ORDER BY hold_id DESC
        LIMIT 1
        """,
        (
            organisation_id,
            production_order_id,
            stage["stage_id"],
        ),
    ).fetchone()

    if not open_hold:
        raise ValueError(
            "No active production hold exists"
        )

    db.execute(
        """
        UPDATE production_holds
        SET status='Resolved',
            resolution='Production resumed',
            resolved_at=?,
            resolved_by=?
        WHERE production_order_id=?
          AND stage_id=?
          AND status='Open'
        """,
        (
            changed_at,
            recorded_by,
            production_order_id,
            stage["stage_id"],
        ),
    )

    eta_impact = _apply_resolved_hold_eta_impact(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        hold_id=int(open_hold["hold_id"]),
        resolved_at=changed_at,
        recorded_by=recorded_by,
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="RESUME",
        payload_json=(
            '{"hold_level":"order",'
            '"restored_stage_status":"'
            + restored_stage_status
            + '"}'
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="ETA_HOLD_IMPACT",
        payload_json=(
            '{"hold_id":'
            + str(eta_impact["hold_id"])
            + ','
            '"eta_impact_minutes":'
            + str(eta_impact["eta_impact_minutes"])
            + ','
            '"eta_source":"PRODUCTION_PROCESS_DATE"}'
        ),
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "stage_id": stage["stage_id"],
        "from_state": result.from_state.value,
        "to_state": result.to_state.value,
        "status": DOMAIN_TO_CORE_STATE[
            result.to_state
        ],
        "stage_status": restored_stage_status,
    }


def complete_order(
    db,
    *,
    organisation_id: int,
    production_order_id: int,
    recorded_by: int,
    stage_id: Optional[int] = None,
) -> dict:
    """
    Complete the current configured production stage.
    """

    order = _load_domain_order(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
    )

    stage = _get_current_stage(
        db,
        production_order_id=production_order_id,
        stage_id=stage_id,
    )

    if not stage:
        raise ValueError(
            "Production order has no production stage"
        )

    changed_at = utc_now()

    stage_totals = db.execute(
        """
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN quantity_type='ACCEPTED'
                        THEN quantity
                        ELSE 0
                    END
                ),
                0
            ) AS accepted_quantity,
            COALESCE(
                SUM(
                    CASE
                        WHEN quantity_type='REJECTED'
                        THEN quantity
                        ELSE 0
                    END
                ),
                0
            ) AS rejected_quantity
        FROM production_quantity_ledger
        WHERE organisation_id=?
          AND production_order_id=?
          AND stage_id=?
        """,
        (
            organisation_id,
            production_order_id,
            stage["stage_id"],
        ),
    ).fetchone()

    stage_accepted = Decimal(
        str(
            stage_totals["accepted_quantity"] or 0
        )
    )

    stage_rejected = Decimal(
        str(
            stage_totals["rejected_quantity"] or 0
        )
    )

    stage_accounted = (
        stage_accepted
        + stage_rejected
    )

    quantity_ordered = Decimal(
        str(order.quantity.planned)
    )

    remaining_quantity = (
        quantity_ordered
        - stage_accounted
    )

    if remaining_quantity < 0:
        raise ValueError(
            "Stage accounted quantity exceeds "
            "ordered quantity"
        )

    if remaining_quantity != 0:
        raise ValueError(
            "Cannot complete stage with "
            f"{remaining_quantity} quantity remaining"
        )

    order_expression = _stage_order_expression(db)

    current_sequence = _get_stage_sequence(
        db,
        production_order_id=production_order_id,
        stage_id=int(stage["stage_id"]),
    )

    next_stage = db.execute(
        f"""
        SELECT
            stage_id,
            stage_name,
            location,
            status
        FROM production_stages
        WHERE production_order_id=?
          AND {order_expression} > ?
        ORDER BY {order_expression} ASC
        LIMIT 1
        """,
        (
            production_order_id,
            current_sequence,
        ),
    ).fetchone()

    if next_stage:
        db.execute(
            """
            UPDATE production_stages
            SET status='Complete',
                finish_datetime=?,
                quantity_completed=?,
                quantity_rejected=?
            WHERE stage_id=?
            """,
            (
                changed_at,
                float(stage_accepted),
                float(stage_rejected),
                stage["stage_id"],
            ),
        )

        db.execute(
            """
            UPDATE production_stages
            SET status='Ready'
            WHERE stage_id=?
            """,
            (
                next_stage["stage_id"],
            ),
        )

        db.execute(
            """
            UPDATE production_orders
            SET current_stage_id=?,
                current_location=?,
                status='In Production',
                updated_at=?
            WHERE production_order_id=?
              AND organisation_id=?
            """,
            (
                next_stage["stage_id"],
                next_stage["location"],
                changed_at,
                production_order_id,
                organisation_id,
            ),
        )

        _write_event(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=stage["stage_id"],
            user_id=recorded_by,
            event_type="STAGE_COMPLETE",
            payload_json="{}",
        )

        _write_event(
            db,
            organisation_id=organisation_id,
            production_order_id=production_order_id,
            stage_id=next_stage["stage_id"],
            user_id=recorded_by,
            event_type="STAGE_READY",
            payload_json="{}",
        )

        db.commit()

        return {
            "production_order_id": production_order_id,
            "stage_id": stage["stage_id"],
            "stage_name": stage["stage_name"],
            "from_state": order.state.value,
            "to_state": order.state.value,
            "status": "In Production",
            "stage_completed": True,
            "accepted_quantity": str(
                stage_accepted
            ),
            "rejected_quantity": str(
                stage_rejected
            ),
            "remaining_quantity": "0",
            "next_stage_id": next_stage["stage_id"],
            "next_stage_name": next_stage["stage_name"],
            "next_stage_status": "Ready",
            "order_completed": False,
        }

    result = SERVICE.complete_order(order)

    changed_at = result.changed_at.isoformat(
        timespec="seconds"
    )

    _persist_order_state(
        db,
        production_order_id=production_order_id,
        state=order.state,
        updated_at=changed_at,
    )

    db.execute(
        """
        UPDATE production_stages
        SET status='Complete',
            finish_datetime=?,
            quantity_completed=?,
            quantity_rejected=?
        WHERE stage_id=?
        """,
        (
            changed_at,
            float(stage_accepted),
            float(stage_rejected),
            stage["stage_id"],
        ),
    )

    db.execute(
        """
        UPDATE production_orders
        SET current_location=NULL,
            updated_at=?
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (
            changed_at,
            production_order_id,
            organisation_id,
        ),
    )

    _write_event(
        db,
        organisation_id=organisation_id,
        production_order_id=production_order_id,
        stage_id=stage["stage_id"],
        user_id=recorded_by,
        event_type="COMPLETE",
        payload_json="{}",
    )

    db.commit()

    return {
        "production_order_id": production_order_id,
        "stage_id": stage["stage_id"],
        "stage_name": stage["stage_name"],
        "from_state": result.from_state.value,
        "to_state": result.to_state.value,
        "status": DOMAIN_TO_CORE_STATE[
            result.to_state
        ],
        "accepted_quantity": str(
            stage_accepted
        ),
        "rejected_quantity": str(
            stage_rejected
        ),
        "remaining_quantity": str(
            order.quantity.remaining
        ),
        "next_stage_id": None,
        "next_stage_name": None,
        "next_stage_status": None,
        "order_completed": True,
    }