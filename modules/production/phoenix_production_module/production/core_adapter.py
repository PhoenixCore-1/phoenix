import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional


QUANTITY_TYPES = {
    "ACCEPTED",
    "REJECTED",
    "REWORK",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_quantity(
    db: sqlite3.Connection,
    *,
    organisation_id: int,
    production_order_id: int,
    stage_id: Optional[int],
    quantity_type: str,
    quantity: Decimal,
    uom_code: str,
    recorded_by: int,
    reason_code: Optional[str] = None,
    notes: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> int:
    """
    Persist one immutable Production quantity ledger entry.

    This adapter owns persistence only. Production business rules remain
    in the standalone Production domain layer.
    """

    quantity_type = quantity_type.upper().strip()

    if quantity_type not in QUANTITY_TYPES:
        raise ValueError(
            f"Unsupported quantity_type: {quantity_type}"
        )

    quantity = Decimal(str(quantity))

    if quantity < 0:
        raise ValueError("Quantity cannot be negative")

    if not uom_code or not uom_code.strip():
        raise ValueError("uom_code is required")

    # Confirm the order belongs to the supplied organisation.
    order = db.execute(
        """
        SELECT production_order_id
        FROM production_orders
        WHERE production_order_id=?
          AND organisation_id=?
        """,
        (production_order_id, organisation_id),
    ).fetchone()

    if not order:
        raise ValueError("Production order not found")

    # If a stage is supplied, it must belong to the same order.
    if stage_id is not None:
        stage = db.execute(
            """
            SELECT stage_id
            FROM production_stages
            WHERE stage_id=?
              AND production_order_id=?
            """,
            (stage_id, production_order_id),
        ).fetchone()

        if not stage:
            raise ValueError("Production stage not found")

    # Idempotent retry protection.
    if idempotency_key:
        existing = db.execute(
            """
            SELECT quantity_ledger_id
            FROM production_quantity_ledger
            WHERE organisation_id=?
              AND idempotency_key=?
            """,
            (organisation_id, idempotency_key),
        ).fetchone()

        if existing:
            return int(existing[0])

    cur = db.execute(
        """
        INSERT INTO production_quantity_ledger(
            organisation_id,
            production_order_id,
            stage_id,
            quantity_type,
            quantity,
            uom_code,
            reason_code,
            notes,
            recorded_by,
            recorded_at,
            idempotency_key
        )
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            organisation_id,
            production_order_id,
            stage_id,
            quantity_type,
            str(quantity),
            uom_code.strip(),
            reason_code,
            notes,
            recorded_by,
            utc_now(),
            idempotency_key,
        ),
    )

    return int(cur.lastrowid)