"""
Phoenix Reporting / BI v0.1

Generic reporting and dashboard foundation.

This version intentionally uses controlled metric definitions rather than
arbitrary SQL entered by users. It provides reusable cross-module KPIs and
simple table reports while keeping customer-specific report logic outside Core.
"""

import json
from core import connect, now, audit, has_permission

REPORT_TYPES = ("Table", "KPI", "Summary")
WIDGET_TYPES = ("KPI", "Table", "Status")
MODULES = ("CRM", "Projects", "Sales", "Production", "Inventory",
           "Procurement", "Accounts", "Workflow", "Core")

METRICS = {
    "CRM": {
        "customer_accounts": "Active customer accounts",
        "contacts": "Active contacts",
    },
    "Projects": {
        "active_projects": "Active projects",
        "completed_projects": "Completed projects",
    },
    "Sales": {
        "open_quotes": "Open quotes",
        "confirmed_orders": "Confirmed sales orders",
        "sales_value": "Confirmed sales value",
    },
    "Production": {
        "open_orders": "Open production orders",
        "completed_orders": "Completed production orders",
    },
    "Inventory": {
        "active_items": "Active inventory items",
        "stock_on_hand": "Stock on hand value",
        "low_stock": "Items below reorder level",
    },
    "Procurement": {
        "open_purchase_orders": "Open purchase orders",
        "purchase_order_value": "Open purchase order value",
    },
    "Accounts": {
        "draft_documents": "Draft financial documents",
        "posted_documents": "Posted financial documents",
        "landed_cost_value": "Allocated landed-cost value",
        "ledger_debits": "Ledger debits",
        "ledger_credits": "Ledger credits",
    },
    "Workflow": {
        "active_instances": "Active workflow instances",
        "open_tasks": "Open workflow tasks",
        "completed_instances": "Completed workflow instances",
    },
    "Core": {
        "users": "Active users",
        "audit_events": "Audit events",
    }
}


def ensure_reporting_permissions():
    con = connect()
    permissions = [
        ("reporting.view", "View Reporting", "Access reports and dashboards"),
        ("reporting.manage", "Manage Reporting", "Create and maintain report definitions"),
        ("reporting.dashboard", "Manage Dashboards", "Create and maintain dashboard definitions"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='reporting'"
    ).fetchone()
    if module:
        for code, _, _ in permissions:
            p = con.execute(
                "SELECT permission_id FROM permissions WHERE permission_code=?",
                (code,)
            ).fetchone()
            if p:
                con.execute(
                    "INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",
                    (module["module_id"], p["permission_id"])
                )
    con.commit()
    con.close()


def list_report_definitions(user):
    con = connect()
    rows = con.execute(
        """SELECT * FROM report_definitions
           WHERE organisation_id=?
           ORDER BY active DESC, report_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_report_definition(user, data):
    if not has_permission(user["user_id"], "reporting.manage"):
        raise PermissionError("Reporting management permission required")

    code = (data.get("report_code") or "").strip()
    name = (data.get("report_name") or "").strip()
    module = data.get("source_module") or ""
    report_type = data.get("report_type") or "Table"
    if not code or not name or not module:
        raise ValueError("Report code, name and source module are required")
    if module not in MODULES:
        raise ValueError("Invalid source module")
    if report_type not in REPORT_TYPES:
        raise ValueError("Invalid report type")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO report_definitions(
                organisation_id,report_code,report_name,description,
                report_type,source_module,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name, data.get("description"),
                report_type, module, user["user_id"], now(), now()
            )
        )
        rid = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "report_definition", str(rid), "CREATE", None,
            {"report_code": code, "report_name": name}
        )
        con.commit()
        return rid
    finally:
        con.close()


def list_dashboards(user):
    con = connect()
    rows = con.execute(
        """SELECT * FROM dashboard_definitions
           WHERE organisation_id=?
           ORDER BY active DESC, dashboard_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_dashboard(user, dashboard_id):
    con = connect()
    dashboard = con.execute(
        """SELECT * FROM dashboard_definitions
           WHERE dashboard_definition_id=? AND organisation_id=?""",
        (dashboard_id, user["organisation_id"])
    ).fetchone()
    if not dashboard:
        con.close()
        raise ValueError("Dashboard not found")
    widgets = con.execute(
        """SELECT * FROM dashboard_widgets
           WHERE dashboard_definition_id=? AND active=1
           ORDER BY position_no""",
        (dashboard_id,)
    ).fetchall()
    con.close()
    result = dict(dashboard)
    result["widgets"] = [dict(w) for w in widgets]
    return result


def create_dashboard(user, data):
    if not has_permission(user["user_id"], "reporting.dashboard"):
        raise PermissionError("Dashboard management permission required")

    code = (data.get("dashboard_code") or "").strip()
    name = (data.get("dashboard_name") or "").strip()
    if not code or not name:
        raise ValueError("Dashboard code and name are required")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO dashboard_definitions(
                organisation_id,dashboard_code,dashboard_name,description,
                created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name, data.get("description"),
                user["user_id"], now(), now()
            )
        )
        did = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "dashboard_definition", str(did), "CREATE", None,
            {"dashboard_code": code, "dashboard_name": name}
        )
        con.commit()
        return did
    finally:
        con.close()


def add_widget(user, dashboard_id, data):
    if not has_permission(user["user_id"], "reporting.dashboard"):
        raise PermissionError("Dashboard management permission required")

    module = data.get("source_module") or ""
    metric = data.get("metric_code") or ""
    widget_type = data.get("widget_type") or "KPI"
    if module not in METRICS:
        raise ValueError("Invalid source module")
    if metric not in METRICS[module]:
        raise ValueError("Invalid metric for source module")
    if widget_type not in WIDGET_TYPES:
        raise ValueError("Invalid widget type")

    con = connect()
    try:
        dash = con.execute(
            """SELECT dashboard_definition_id FROM dashboard_definitions
               WHERE dashboard_definition_id=? AND organisation_id=?""",
            (dashboard_id, user["organisation_id"])
        ).fetchone()
        if not dash:
            raise ValueError("Dashboard not found")

        code = (data.get("widget_code") or "").strip() or f"{module.lower()}_{metric}"
        name = (data.get("widget_name") or "").strip() or METRICS[module][metric]
        position = con.execute(
            """SELECT COALESCE(MAX(position_no),0)+1 n
               FROM dashboard_widgets WHERE dashboard_definition_id=?""",
            (dashboard_id,)
        ).fetchone()["n"]

        cur = con.execute(
            """INSERT INTO dashboard_widgets(
                dashboard_definition_id,widget_code,widget_name,widget_type,
                source_module,metric_code,position_no
            ) VALUES(?,?,?,?,?,?,?)""",
            (dashboard_id, code, name, widget_type, module, metric, position)
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def metric_value(user, module, metric):
    if module not in METRICS or metric not in METRICS[module]:
        raise ValueError("Unknown metric")

    con = connect()
    org = user["organisation_id"]

    queries = {
        ("CRM","customer_accounts"):
            ("SELECT COUNT(*) v FROM crm_accounts WHERE organisation_id=? AND status='Active'", (org,)),
        ("CRM","contacts"):
            ("SELECT COUNT(*) v FROM crm_contacts WHERE organisation_id=? AND status='Active'", (org,)),
        ("Projects","active_projects"):
            ("SELECT COUNT(*) v FROM projects WHERE organisation_id=? AND status NOT IN ('Completed','Cancelled')", (org,)),
        ("Projects","completed_projects"):
            ("SELECT COUNT(*) v FROM projects WHERE organisation_id=? AND status='Completed'", (org,)),
        ("Sales","open_quotes"):
            ("SELECT COUNT(*) v FROM sales_quotes WHERE organisation_id=? AND status IN ('Draft','Submitted','Sent')", (org,)),
        ("Sales","confirmed_orders"):
            ("SELECT COUNT(*) v FROM sales_orders WHERE organisation_id=? AND status NOT IN ('Cancelled','Completed')", (org,)),
        ("Sales","sales_value"):
            ("SELECT COALESCE(SUM(total),0) v FROM sales_orders WHERE organisation_id=? AND status NOT IN ('Cancelled','Draft')", (org,)),
        ("Production","open_orders"):
            ("SELECT COUNT(*) v FROM production_orders WHERE organisation_id=? AND status NOT IN ('Completed','Cancelled')", (org,)),
        ("Production","completed_orders"):
            ("SELECT COUNT(*) v FROM production_orders WHERE organisation_id=? AND status='Completed'", (org,)),
        ("Inventory","active_items"):
            ("SELECT COUNT(*) v FROM inventory_items WHERE organisation_id=? AND active=1", (org,)),
        ("Inventory","stock_on_hand"):
            ("SELECT COALESCE(SUM(quantity_on_hand*average_cost),0) v FROM inventory_items WHERE organisation_id=? AND active=1", (org,)),
        ("Inventory","low_stock"):
            ("SELECT COUNT(*) v FROM inventory_items WHERE organisation_id=? AND active=1 AND quantity_on_hand<=reorder_level", (org,)),
        ("Procurement","open_purchase_orders"):
            ("SELECT COUNT(*) v FROM purchase_orders WHERE organisation_id=? AND status IN ('Draft','Issued','Partially Received')", (org,)),
        ("Procurement","purchase_order_value"):
            ("SELECT COALESCE(SUM(total),0) v FROM purchase_orders WHERE organisation_id=? AND status IN ('Issued','Partially Received')", (org,)),
        ("Accounts","draft_documents"):
            ("SELECT COUNT(*) v FROM financial_documents WHERE organisation_id=? AND status='Draft'", (org,)),
        ("Accounts","posted_documents"):
            ("SELECT COUNT(*) v FROM financial_documents WHERE organisation_id=? AND status='Posted'", (org,)),
        ("Accounts","landed_cost_value"):
            ("SELECT COALESCE(SUM(amount),0) v FROM landed_costs WHERE organisation_id=? AND status='Allocated'", (org,)),
        ("Accounts","ledger_debits"):
            ("SELECT COALESCE(SUM(debit),0) v FROM financial_transactions WHERE organisation_id=?", (org,)),
        ("Accounts","ledger_credits"):
            ("SELECT COALESCE(SUM(credit),0) v FROM financial_transactions WHERE organisation_id=?", (org,)),
        ("Workflow","active_instances"):
            ("SELECT COUNT(*) v FROM workflow_instances WHERE organisation_id=? AND status='Active'", (org,)),
        ("Workflow","open_tasks"):
            ("SELECT COUNT(*) v FROM workflow_tasks WHERE organisation_id=? AND status='Open'", (org,)),
        ("Workflow","completed_instances"):
            ("SELECT COUNT(*) v FROM workflow_instances WHERE organisation_id=? AND status='Completed'", (org,)),
        ("Core","users"):
            ("SELECT COUNT(*) v FROM users WHERE organisation_id=? AND status='Active'", (org,)),
        ("Core","audit_events"):
            ("SELECT COUNT(*) v FROM audit_log WHERE organisation_id=?", (org,)),
    }

    query = queries.get((module, metric))
    if not query:
        con.close()
        raise ValueError("Metric is not implemented")
    value = con.execute(query[0], query[1]).fetchone()["v"]
    con.close()
    return value


def dashboard_data(user, dashboard_id):
    dash = get_dashboard(user, dashboard_id)
    for widget in dash["widgets"]:
        widget["value"] = metric_value(user, widget["source_module"], widget["metric_code"])
        widget["metric_label"] = METRICS[widget["source_module"]][widget["metric_code"]]
    return dash


def module_snapshot(user):
    result = {}
    for module, metrics in METRICS.items():
        result[module] = {}
        for metric in metrics:
            try:
                result[module][metric] = metric_value(user, module, metric)
            except Exception:
                result[module][metric] = None
    return result


def save_filter(user, report_id, data):
    if not has_permission(user["user_id"], "reporting.manage"):
        raise PermissionError("Reporting management permission required")
    name = (data.get("filter_name") or "").strip()
    if not name:
        raise ValueError("Filter name is required")
    filter_json = json.dumps(data.get("filters") or {})
    con = connect()
    try:
        report = con.execute(
            """SELECT report_definition_id FROM report_definitions
               WHERE report_definition_id=? AND organisation_id=?""",
            (report_id, user["organisation_id"])
        ).fetchone()
        if not report:
            raise ValueError("Report not found")
        con.execute(
            """INSERT INTO saved_report_filters(
                organisation_id,report_definition_id,filter_name,filter_json,
                created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,report_definition_id,filter_name)
            DO UPDATE SET filter_json=excluded.filter_json,updated_at=excluded.updated_at""",
            (
                user["organisation_id"], report_id, name, filter_json,
                user["user_id"], now(), now()
            )
        )
        con.commit()
    finally:
        con.close()


def list_saved_filters(user, report_id):
    con = connect()
    rows = con.execute(
        """SELECT * FROM saved_report_filters
           WHERE organisation_id=? AND report_definition_id=?
           ORDER BY filter_name""",
        (user["organisation_id"], report_id)
    ).fetchall()
    con.close()
    result = []
    for row in rows:
        item = dict(row)
        item["filters"] = json.loads(item.pop("filter_json"))
        result.append(item)
    return result


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    d = {
        "reports": con.execute(
            "SELECT COUNT(*) c FROM report_definitions WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "dashboards": con.execute(
            "SELECT COUNT(*) c FROM dashboard_definitions WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "widgets": con.execute(
            """SELECT COUNT(*) c FROM dashboard_widgets w
               JOIN dashboard_definitions d ON d.dashboard_definition_id=w.dashboard_definition_id
               WHERE d.organisation_id=? AND w.active=1""",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return d
