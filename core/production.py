"""
Phoenix Core Production capability.

Core owns:
- tenant isolation
- permissions
- database persistence
- production order records
- HTTP/API orchestration

Phoenix Production Module owns:
- production lifecycle business rules
- state transitions
- production domain behaviour
- ETA calculation
- ETA risk calculation
- operational ETA decision logic

The Core Production capability communicates with the
standalone Production Module through module_adapters.production.
"""

import json
from decimal import Decimal

from core import (
    connect,
    has_permission,
    audit,
    now,
)

from module_adapters.production import (
    record_stage_quantities,
    release_order as module_release_order,
    start_order as module_start_order,
    hold_order as module_hold_order,
    resume_order as module_resume_order,
    complete_order as module_complete_order,
    start_stage as module_start_stage,
    get_eta_operational_snapshot as module_get_eta_operational_snapshot,
)


PURPOSES = [
    "Customer Order",
    "Stock Replenishment",
    "Internal",
]

PRIORITIES = [
    "Low",
    "Normal",
    "High",
    "Critical",
]


def ensure_stage_templates(org, con=None):
    """
    Ensure the organisation has the standard Production stage templates.

    If an existing database connection is supplied, that connection is
    reused. This is important when called from create_order(), because
    create_order() may already have an active SQLite transaction.

    These are Core configuration records. They do not contain
    Production domain lifecycle rules.
    """

    owns_connection = con is None

    if owns_connection:
        con = connect()

    try:
        templates = [
            (
                "PRODUCTION",
                "Production",
                10,
                "Off-site Manufacturing",
            ),
            (
                "PLATING",
                "Plating",
                20,
                "Off-site Plating",
            ),
            (
                "ASSEMBLY",
                "Assembly",
                30,
                "Assembly",
            ),
            (
                "PACKAGING",
                "Packaging",
                40,
                "Packaging",
            ),
        ]

        for code, name, sequence, location in templates:
            con.execute(
                """
                INSERT OR IGNORE INTO production_stage_templates(
                    organisation_id,
                    stage_code,
                    stage_name,
                    stage_sequence,
                    default_location,
                    active
                )
                VALUES(?,?,?,?,?,1)
                """,
                (
                    org,
                    code,
                    name,
                    sequence,
                    location,
                ),
            )

        if owns_connection:
            con.commit()

    finally:
        if owns_connection:
            con.close()


def _account_ok(con, org, account_id):
    if not account_id:
        return None

    row = con.execute(
        """
        SELECT account_id
        FROM crm_accounts
        WHERE account_id=?
          AND organisation_id=?
        """,
        (
            account_id,
            org,
        ),
    ).fetchone()

    if not row:
        raise ValueError(
            "Customer account not found in this organisation"
        )

    return int(account_id)


def _project_ok(con, org, project_id):
    if not project_id:
        return None

    row = con.execute(
        """
        SELECT project_id
        FROM projects
        WHERE project_id=?
          AND organisation_id=?
        """,
        (
            project_id,
            org,
        ),
    ).fetchone()

    if not row:
        raise ValueError(
            "Project not found in this organisation"
        )

    return int(project_id)


def _quote_ok(con, org, quote_id):
    if not quote_id:
        return None

    row = con.execute(
        """
        SELECT quote_id
        FROM sales_quotes
        WHERE quote_id=?
          AND organisation_id=?
        """,
        (
            quote_id,
            org,
        ),
    ).fetchone()

    if not row:
        raise ValueError(
            "Quote not found in this organisation"
        )

    return int(quote_id)


def next_order_number(org):
    con = connect()

    try:
        n = con.execute(
            """
            SELECT COUNT(*) c
            FROM production_orders
            WHERE organisation_id=?
            """,
            (org,),
        ).fetchone()["c"] + 1

        return f"PO-{n:06d}"

    finally:
        con.close()


def _event(
    con,
    org,
    order_id,
    stage_id,
    event_type,
    user_id,
    payload=None,
):
    con.execute(
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
            org,
            order_id,
            stage_id,
            event_type,
            user_id,
            json.dumps(payload or {}),
            now(),
        ),
    )


def create_order(user, data):
    """
    Create a new Production Order.

    IMPORTANT:
    New orders are created as Planned.

    Release is a separate lifecycle action and must go through
    the Phoenix Production Module.
    """

    if not has_permission(
        user["user_id"],
        "production.manage",
    ):
        raise PermissionError(
            "Production management permission required"
        )

    product_ref = (
        data.get("product_ref") or ""
    ).strip()

    if not product_ref:
        raise ValueError(
            "Product reference is required"
        )

    qty = float(
        data.get("quantity_ordered") or 0
    )

    if qty <= 0:
        raise ValueError(
            "Quantity ordered must be greater than zero"
        )

    purpose = (
        data.get("purpose")
        or "Customer Order"
    )

    if purpose not in PURPOSES:
        raise ValueError(
            "Invalid production purpose"
        )

    priority = (
        data.get("priority")
        or "Normal"
    )

    if priority not in PRIORITIES:
        raise ValueError(
            "Invalid priority"
        )

    con = connect()

    try:
        account_id = _account_ok(
            con,
            user["organisation_id"],
            data.get("account_id"),
        )

        project_id = _project_ok(
            con,
            user["organisation_id"],
            data.get("project_id"),
        )

        quote_id = _quote_ok(
            con,
            user["organisation_id"],
            data.get("quote_id"),
        )

        order_number = (
            data.get("order_number") or ""
        ).strip()

        if not order_number:
            order_number = next_order_number(
                user["organisation_id"]
            )

        cur = con.execute(
            """
            INSERT INTO production_orders(
                organisation_id,
                order_number,
                purpose,
                account_id,
                project_id,
                quote_id,
                product_ref,
                product_description,
                quantity_ordered,
                required_date,
                customer_reference,
                priority,
                status,
                current_location,
                created_by,
                created_at,
                updated_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user["organisation_id"],
                order_number,
                purpose,
                account_id,
                project_id,
                quote_id,
                product_ref,
                (
                    data.get("product_description")
                    or ""
                ).strip() or None,
                qty,
                data.get("required_date") or None,
                (
                    data.get("customer_reference")
                    or ""
                ).strip() or None,
                priority,
                "Planned",
                "Off-site Manufacturing",
                user["user_id"],
                now(),
                now(),
            ),
        )

        order_id = cur.lastrowid

        ensure_stage_templates(
            user["organisation_id"],
            con=con,
        )

        templates = con.execute(
            """
            SELECT *
            FROM production_stage_templates
            WHERE organisation_id=?
              AND active=1
            ORDER BY stage_sequence
            """,
            (user["organisation_id"],),
        ).fetchall()

        for i, template in enumerate(templates):
            con.execute(
                """
                INSERT INTO production_stages(
                    production_order_id,
                    stage_code,
                    stage_name,
                    stage_sequence,
                    location,
                    status
                )
                VALUES(?,?,?,?,?,?)
                """,
                (
                    order_id,
                    template["stage_code"],
                    template["stage_name"],
                    template["stage_sequence"],
                    template["default_location"],
                    "Ready" if i == 0 else "Waiting",
                ),
            )

        first = con.execute(
            """
            SELECT
                stage_id,
                stage_name,
                location
            FROM production_stages
            WHERE production_order_id=?
            ORDER BY stage_sequence
            LIMIT 1
            """,
            (order_id,),
        ).fetchone()

        if first:
            con.execute(
                """
                UPDATE production_orders
                SET current_stage_id=?,
                    current_location=?,
                    updated_at=?
                WHERE production_order_id=?
                """,
                (
                    first["stage_id"],
                    first["location"],
                    now(),
                    order_id,
                ),
            )

        _event(
            con,
            user["organisation_id"],
            order_id,
            None,
            "ORDER_CREATED",
            user["user_id"],
            {
                "order_number": order_number,
                "purpose": purpose,
            },
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "CREATE",
            None,
            {
                "order_number": order_number,
                "product_ref": product_ref,
                "quantity": qty,
                "status": "Planned",
            },
        )

        con.commit()

        return order_id

    finally:
        con.close()


def release_order(user, order_id):
    """
    Release a Planned Production Order.

    The lifecycle transition is owned by the Production Module.
    """

    if not has_permission(
        user["user_id"],
        "production.manage",
    ):
        raise PermissionError(
            "Production management permission required"
        )

    con = connect()

    try:
        result = module_release_order(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            recorded_by=user["user_id"],
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "RELEASE",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def start_order(
    user,
    order_id,
    stage_id=None,
):
    """
    Start a released Production Order.

    Lifecycle rules remain owned by the Production Module.
    """

    if not has_permission(
        user["user_id"],
        "production.operate",
    ):
        raise PermissionError(
            "Production operation permission required"
        )

    con = connect()

    try:
        result = module_start_order(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            recorded_by=user["user_id"],
            stage_id=(
                int(stage_id)
                if stage_id is not None
                else None
            ),
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "START",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def hold_order(
    user,
    order_id,
    reason,
    problem_type="Production Problem",
    affected_quantity=0,
    stage_id=None,
):
    """
    Place a Production Order on hold.
    """

    if not has_permission(
        user["user_id"],
        "production.hold",
    ):
        raise PermissionError(
            "Production hold permission required"
        )

    con = connect()

    try:
        result = module_hold_order(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            recorded_by=user["user_id"],
            reason=reason,
            problem_type=problem_type,
            affected_quantity=Decimal(
                str(affected_quantity or 0)
            ),
            stage_id=(
                int(stage_id)
                if stage_id is not None
                else None
            ),
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "HOLD",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def resume_order(
    user,
    order_id,
    stage_id=None,
):
    """
    Resume a held Production Order.
    """

    if not has_permission(
        user["user_id"],
        "production.resume",
    ):
        raise PermissionError(
            "Production resume permission required"
        )

    con = connect()

    try:
        result = module_resume_order(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            recorded_by=user["user_id"],
            stage_id=(
                int(stage_id)
                if stage_id is not None
                else None
            ),
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "RESUME",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def complete_order(
    user,
    order_id,
    stage_id=None,
):
    """
    Complete a Production Order.

    The Production Module determines whether the order
    is allowed to transition to Completed.
    """

    if not has_permission(
        user["user_id"],
        "production.operate",
    ):
        raise PermissionError(
            "Production operation permission required"
        )

    con = connect()

    try:
        result = module_complete_order(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            recorded_by=user["user_id"],
            stage_id=(
                int(stage_id)
                if stage_id is not None
                else None
            ),
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "COMPLETE",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def start_stage(
    user,
    order_id,
    stage_id,
):
    """
    Start a READY production stage through the Production Module.

    Stage-level progression is owned by the Production Module.

    This is intentionally different from start_order().
    start_order() starts the Production Order itself.
    start_stage() starts the currently READY configured stage.
    """

    if not has_permission(
        user["user_id"],
        "production.operate",
    ):
        raise PermissionError(
            "Production operation permission required"
        )

    con = connect()

    try:
        result = module_start_stage(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            stage_id=int(stage_id),
            recorded_by=user["user_id"],
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "START_STAGE",
            None,
            result,
        )

        con.commit()

        return result

    finally:
        con.close()


def finish_stage(
    user,
    order_id,
    stage_id,
    completed_qty,
    rejected_qty,
    notes="",
):
    """
    Finish a Production stage.

    Quantities are first recorded through the Production Module.

    When the total quantity recorded for the production order
    reaches the ordered quantity, the Production Module lifecycle
    is then asked to complete the order.

    The Production Module remains the owner of lifecycle rules.
    Core only orchestrates the UI/API operation.
    """

    if not has_permission(
        user["user_id"],
        "production.operate",
    ):
        raise PermissionError(
            "Production operation permission required"
        )

    completed_qty = Decimal(
        str(completed_qty or 0)
    )

    rejected_qty = Decimal(
        str(rejected_qty or 0)
    )

    if completed_qty < 0:
        raise ValueError(
            "Completed quantity cannot be negative"
        )

    if rejected_qty < 0:
        raise ValueError(
            "Rejected quantity cannot be negative"
        )

    if completed_qty == 0 and rejected_qty == 0:
        raise ValueError(
            "Completed or rejected quantity must be greater than zero"
        )

    con = connect()

    try:
        result = record_stage_quantities(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
            stage_id=int(stage_id),
            accepted_quantity=completed_qty,
            rejected_quantity=rejected_qty,
            recorded_by=user["user_id"],
            notes=notes or None,
        )

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "production_order",
            str(order_id),
            "RECORD_STAGE_QUANTITY",
            None,
            {
                "stage_id": int(stage_id),
                "completed_quantity": str(
                    completed_qty
                ),
                "rejected_quantity": str(
                    rejected_qty
                ),
            },
        )

        order = con.execute(
            """
            SELECT
                production_order_id,
                quantity_ordered,
                status
            FROM production_orders
            WHERE production_order_id=?
              AND organisation_id=?
            """,
            (
                int(order_id),
                user["organisation_id"],
            ),
        ).fetchone()

        if not order:
            raise ValueError(
                "Production order not found"
            )

        ordered_quantity = Decimal(
            str(order["quantity_ordered"] or 0)
        )

        totals = con.execute(
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
            """,
            (
                user["organisation_id"],
                int(order_id),
            ),
        ).fetchone()

        total_accepted = Decimal(
            str(totals["accepted_quantity"] or 0)
        )

        total_rejected = Decimal(
            str(totals["rejected_quantity"] or 0)
        )

        total_accounted = (
            total_accepted +
            total_rejected
        )

        remaining_quantity = (
            ordered_quantity -
            total_accounted
        )

        if remaining_quantity < 0:
            remaining_quantity = Decimal("0")

        completion_result = None

        if (
            order["status"] != "Completed"
            and ordered_quantity > 0
            and total_accounted >= ordered_quantity
        ):
            completion_result = module_complete_order(
                con,
                organisation_id=user["organisation_id"],
                production_order_id=int(order_id),
                recorded_by=user["user_id"],
                stage_id=int(stage_id),
            )

            audit(
                con,
                user["organisation_id"],
                user["user_id"],
                "production_order",
                str(order_id),
                "COMPLETE",
                None,
                completion_result,
            )

        con.commit()

        response = dict(result)

        response["accepted_quantity_total"] = str(
            total_accepted
        )

        response["rejected_quantity_total"] = str(
            total_rejected
        )

        response["accounted_quantity"] = str(
            total_accounted
        )

        response["remaining_quantity"] = str(
            remaining_quantity
        )

        response["completed"] = (
            completion_result is not None
        )

        if completion_result is not None:
            response["completion"] = completion_result

        return response

    except Exception:
        con.rollback()
        raise

    finally:
        con.close()


def hold_stage(
    user,
    order_id,
    stage_id,
    problem_type,
    description,
    affected_quantity,
):
    """
    Backwards-compatible stage hold API.
    """

    return hold_order(
        user,
        order_id,
        reason=description,
        problem_type=problem_type,
        affected_quantity=affected_quantity,
        stage_id=stage_id,
    )


def resume_stage(
    user,
    order_id,
    stage_id,
    resolution="Production resumed",
):
    """
    Backwards-compatible stage resume API.

    The lifecycle transition is handled by the Production Module.
    """

    return resume_order(
        user,
        order_id,
        stage_id=stage_id,
    )


def get_eta_operational_snapshot(
    user,
    order_id,
):
    """
    Retrieve the operational ETA snapshot for a Production Order.

    Core owns:
        - user permission
        - tenant/organisation context
        - database connection

    Production Module owns:
        - ETA calculation
        - schedule risk
        - required-date risk
        - operational decision
        - action-required determination
        - ETA business rules

    This function deliberately contains no ETA business logic.
    """

    if not has_permission(
        user["user_id"],
        "production.view",
    ):
        raise PermissionError(
            "Production view permission required"
        )

    con = connect()

    try:
        result = module_get_eta_operational_snapshot(
            con,
            organisation_id=user["organisation_id"],
            production_order_id=int(order_id),
        )

        return result

    finally:
        con.close()


def list_orders(
    user,
    search="",
):
    con = connect()

    clauses = [
        "o.organisation_id=?"
    ]

    params = [
        user["organisation_id"]
    ]

    if search:
        like = f"%{search}%"

        clauses.append(
            """
            (
                o.order_number LIKE ?
                OR o.product_ref LIKE ?
                OR COALESCE(
                    o.product_description,
                    ''
                ) LIKE ?
                OR COALESCE(
                    a.account_name,
                    ''
                ) LIKE ?
            )
            """
        )

        params.extend(
            [
                like,
                like,
                like,
                like,
            ]
        )

    rows = con.execute(
        f"""
        SELECT
            o.*,
            a.account_name,
            p.project_name,
            s.stage_name AS current_stage_name
        FROM production_orders o
        LEFT JOIN crm_accounts a
            ON a.account_id=o.account_id
        LEFT JOIN projects p
            ON p.project_id=o.project_id
        LEFT JOIN production_stages s
            ON s.stage_id=o.current_stage_id
        WHERE {' AND '.join(clauses)}
        ORDER BY
            CASE o.priority
                WHEN 'Critical' THEN 1
                WHEN 'High' THEN 2
                WHEN 'Normal' THEN 3
                ELSE 4
            END,
            COALESCE(
                o.required_date,
                '9999-12-31'
            ),
            o.production_order_id DESC
        """,
        tuple(params),
    ).fetchall()

    con.close()

    return [
        dict(row)
        for row in rows
    ]


def get_order(
    user,
    order_id,
):
    con = connect()

    order = con.execute(
        """
        SELECT
            o.*,
            a.account_name,
            p.project_name,
            s.stage_name AS current_stage_name
        FROM production_orders o
        LEFT JOIN crm_accounts a
            ON a.account_id=o.account_id
        LEFT JOIN projects p
            ON p.project_id=o.project_id
        LEFT JOIN production_stages s
            ON s.stage_id=o.current_stage_id
        WHERE o.production_order_id=?
          AND o.organisation_id=?
        """,
        (
            order_id,
            user["organisation_id"],
        ),
    ).fetchone()

    if not order:
        con.close()
        raise ValueError(
            "Production order not found"
        )

    stages = con.execute(
        """
        SELECT *
        FROM production_stages
        WHERE production_order_id=?
        ORDER BY stage_sequence
        """,
        (order_id,),
    ).fetchall()

    holds = con.execute(
        """
        SELECT
            h.*,
            u.display_name AS reported_by_name
        FROM production_holds h
        JOIN users u
            ON u.user_id=h.reported_by
        WHERE h.production_order_id=?
        ORDER BY h.hold_id DESC
        """,
        (order_id,),
    ).fetchall()

    events = con.execute(
        """
        SELECT
            e.*,
            u.display_name
        FROM production_events e
        JOIN users u
            ON u.user_id=e.user_id
        WHERE e.production_order_id=?
        ORDER BY e.event_id DESC
        """,
        (order_id,),
    ).fetchall()

    con.close()

    result = dict(order)

    result["stages"] = [
        dict(row)
        for row in stages
    ]

    result["holds"] = [
        dict(row)
        for row in holds
    ]

    result["events"] = [
        dict(row)
        for row in events
    ]

    return result


def dashboard(user):
    con = connect()

    try:
        org = user["organisation_id"]

        total = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
            """,
            (org,),
        ).fetchone()[0]

        planned = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
              AND status='Planned'
            """,
            (org,),
        ).fetchone()[0]

        released = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
              AND status='Released to Production'
            """,
            (org,),
        ).fetchone()[0]

        in_production = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
              AND status='In Production'
            """,
            (org,),
        ).fetchone()[0]

        on_hold = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
              AND status='On Hold'
            """,
            (org,),
        ).fetchone()[0]

        completed = con.execute(
            """
            SELECT COUNT(*)
            FROM production_orders
            WHERE organisation_id=?
              AND status='Completed'
            """,
            (org,),
        ).fetchone()[0]

        return {
            "total": total,
            "planned": planned,
            "released": released,
            "in_production": in_production,
            "on_hold": on_hold,
            "completed": completed,
        }

    finally:
        con.close()