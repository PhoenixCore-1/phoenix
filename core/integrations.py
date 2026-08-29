"""
Phoenix Integrations v0.1

Generic integration gateway / adapter foundation.

Important design rule:
Phoenix Core defines the integration contract and lifecycle.
Customer-specific ERP/API credentials, mappings, endpoints and business rules
must live in configuration or customer modules.

This version does NOT make outbound network calls.
It creates and tracks integration definitions, endpoints, mappings, jobs,
events and sync state so that secure adapters can be added later.
"""

import json
from core import connect, now, audit, has_permission

PROVIDER_TYPES = (
    "REST API", "SOAP API", "Database", "File", "Webhook",
    "ERP", "Accounting", "CRM", "Custom"
)
DIRECTIONS = ("Inbound", "Outbound", "Both")
ENDPOINT_TYPES = ("API", "Webhook", "File", "Database")
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
JOB_STATUSES = ("Queued", "Running", "Completed", "Failed", "Cancelled")
EVENT_STATUSES = ("Received", "Processed", "Failed", "Ignored")
ENTITY_TYPES = (
    "Customer", "Contact", "Project", "Quote", "SalesOrder",
    "ProductionOrder", "InventoryItem", "PurchaseOrder",
    "FinancialDocument", "WorkflowInstance", "Generic"
)


def ensure_integrations_permissions():
    con = connect()
    permissions = [
        ("integrations.view", "View Integrations", "View integration definitions and activity"),
        ("integrations.manage", "Manage Integrations", "Create and maintain integration configuration"),
        ("integrations.execute", "Execute Integrations", "Queue and process integration jobs"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='integrations'"
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


def list_integrations(user):
    con = connect()
    rows = con.execute(
        """SELECT * FROM integration_definitions
           WHERE organisation_id=?
           ORDER BY active DESC, integration_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_integration(user, integration_id):
    con = connect()
    definition = con.execute(
        """SELECT * FROM integration_definitions
           WHERE integration_definition_id=? AND organisation_id=?""",
        (integration_id, user["organisation_id"])
    ).fetchone()
    if not definition:
        con.close()
        raise ValueError("Integration not found")

    endpoints = con.execute(
        """SELECT * FROM integration_endpoints
           WHERE integration_definition_id=?
           ORDER BY endpoint_name""",
        (integration_id,)
    ).fetchall()
    mappings = con.execute(
        """SELECT * FROM integration_mappings
           WHERE integration_definition_id=?
           ORDER BY entity_type,local_field""",
        (integration_id,)
    ).fetchall()
    credentials = con.execute(
        """SELECT integration_credential_id,credential_name,credential_type,
                  active,created_at,updated_at
           FROM integration_credentials
           WHERE integration_definition_id=?
           ORDER BY credential_name""",
        (integration_id,)
    ).fetchall()
    con.close()

    result = dict(definition)
    result["endpoints"] = [dict(x) for x in endpoints]
    result["mappings"] = [dict(x) for x in mappings]
    result["credentials"] = [dict(x) for x in credentials]
    return result


def create_integration(user, data):
    if not has_permission(user["user_id"], "integrations.manage"):
        raise PermissionError("Integration management permission required")

    code = (data.get("integration_code") or "").strip()
    name = (data.get("integration_name") or "").strip()
    provider = data.get("provider_type") or ""
    direction = data.get("direction") or "Both"

    if not code or not name:
        raise ValueError("Integration code and name are required")
    if provider not in PROVIDER_TYPES:
        raise ValueError("Invalid provider type")
    if direction not in DIRECTIONS:
        raise ValueError("Invalid integration direction")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO integration_definitions(
                organisation_id,integration_code,integration_name,provider_type,
                description,direction,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name, provider,
                data.get("description"), direction,
                user["user_id"], now(), now()
            )
        )
        iid = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "integration_definition", str(iid), "CREATE", None,
            {"integration_code": code, "provider_type": provider}
        )
        con.commit()
        return iid
    finally:
        con.close()


def add_endpoint(user, integration_id, data):
    if not has_permission(user["user_id"], "integrations.manage"):
        raise PermissionError("Integration management permission required")

    code = (data.get("endpoint_code") or "").strip()
    name = (data.get("endpoint_name") or "").strip()
    endpoint_type = data.get("endpoint_type") or "API"
    method = data.get("method") or "POST"

    if not code or not name:
        raise ValueError("Endpoint code and name are required")
    if endpoint_type not in ENDPOINT_TYPES:
        raise ValueError("Invalid endpoint type")
    if method not in METHODS:
        raise ValueError("Invalid HTTP method")

    con = connect()
    try:
        parent = con.execute(
            """SELECT integration_definition_id FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=?""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not parent:
            raise ValueError("Integration not found")

        cur = con.execute(
            """INSERT INTO integration_endpoints(
                integration_definition_id,endpoint_code,endpoint_name,
                endpoint_type,base_url,method,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                integration_id, code, name, endpoint_type,
                data.get("base_url"), method, now(), now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def add_credential(user, integration_id, data):
    if not has_permission(user["user_id"], "integrations.manage"):
        raise PermissionError("Integration management permission required")

    name = (data.get("credential_name") or "").strip()
    ctype = (data.get("credential_type") or "").strip()
    secret_ref = (data.get("secret_reference") or "").strip()

    if not name or not ctype:
        raise ValueError("Credential name and type are required")

    # Only a reference is stored. Raw secrets must never be stored in this table.
    con = connect()
    try:
        parent = con.execute(
            """SELECT integration_definition_id FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=?""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not parent:
            raise ValueError("Integration not found")

        cur = con.execute(
            """INSERT INTO integration_credentials(
                integration_definition_id,credential_name,credential_type,
                secret_reference,created_at,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            (integration_id, name, ctype, secret_ref, now(), now())
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def add_mapping(user, integration_id, data):
    if not has_permission(user["user_id"], "integrations.manage"):
        raise PermissionError("Integration management permission required")

    entity_type = data.get("entity_type") or "Generic"
    local_field = (data.get("local_field") or "").strip()
    external_field = (data.get("external_field") or "").strip()
    if entity_type not in ENTITY_TYPES:
        raise ValueError("Invalid entity type")
    if not local_field or not external_field:
        raise ValueError("Local field and external field are required")

    con = connect()
    try:
        parent = con.execute(
            """SELECT integration_definition_id FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=?""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not parent:
            raise ValueError("Integration not found")

        cur = con.execute(
            """INSERT INTO integration_mappings(
                integration_definition_id,entity_type,local_field,
                external_field,transform_code,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                integration_id, entity_type, local_field, external_field,
                data.get("transform_code"), now(), now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def queue_job(user, data):
    if not has_permission(user["user_id"], "integrations.execute"):
        raise PermissionError("Integration execution permission required")

    integration_id = int(data.get("integration_definition_id") or 0)
    endpoint_id = data.get("endpoint_id")
    job_type = (data.get("job_type") or "Sync").strip()
    entity_type = data.get("entity_type")
    entity_id = data.get("entity_id")

    con = connect()
    try:
        definition = con.execute(
            """SELECT * FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=? AND active=1""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not definition:
            raise ValueError("Active integration not found")

        if endpoint_id:
            endpoint = con.execute(
                """SELECT integration_endpoint_id FROM integration_endpoints
                   WHERE integration_endpoint_id=? AND integration_definition_id=? AND active=1""",
                (int(endpoint_id), integration_id)
            ).fetchone()
            if not endpoint:
                raise ValueError("Active endpoint not found")

        cur = con.execute(
            """INSERT INTO integration_jobs(
                organisation_id,integration_definition_id,endpoint_id,
                job_type,entity_type,entity_id,status,queued_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], integration_id,
                int(endpoint_id) if endpoint_id else None,
                job_type, entity_type,
                int(entity_id) if entity_id is not None else None,
                "Queued", now(), now()
            )
        )
        job_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "integration_job", str(job_id), "QUEUE", None,
            {"integration_id": integration_id, "job_type": job_type}
        )
        con.commit()
        return job_id
    finally:
        con.close()


def update_job_status(user, job_id, status, error_message=None):
    if not has_permission(user["user_id"], "integrations.execute"):
        raise PermissionError("Integration execution permission required")
    if status not in JOB_STATUSES:
        raise ValueError("Invalid job status")

    con = connect()
    try:
        job = con.execute(
            """SELECT * FROM integration_jobs
               WHERE integration_job_id=? AND organisation_id=?""",
            (job_id, user["organisation_id"])
        ).fetchone()
        if not job:
            raise ValueError("Integration job not found")

        started = job["started_at"]
        completed = job["completed_at"]
        if status == "Running" and not started:
            started = now()
        if status in ("Completed", "Failed", "Cancelled"):
            completed = now()

        con.execute(
            """UPDATE integration_jobs
               SET status=?,attempt_count=attempt_count+CASE WHEN ?='Running' THEN 1 ELSE 0 END,
                   error_message=?,started_at=?,completed_at=?,updated_at=?
               WHERE integration_job_id=?""",
            (status, status, error_message, started, completed, now(), job_id)
        )
        con.commit()
    finally:
        con.close()


def receive_event(user, data):
    if not has_permission(user["user_id"], "integrations.execute"):
        raise PermissionError("Integration execution permission required")

    integration_id = int(data.get("integration_definition_id") or 0)
    event_type = (data.get("event_type") or "Generic").strip()
    direction = data.get("direction") or "Inbound"

    if direction not in DIRECTIONS:
        raise ValueError("Invalid event direction")

    con = connect()
    try:
        definition = con.execute(
            """SELECT integration_definition_id FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=? AND active=1""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not definition:
            raise ValueError("Active integration not found")

        cur = con.execute(
            """INSERT INTO integration_events(
                organisation_id,integration_definition_id,event_type,
                entity_type,entity_id,direction,status,
                external_reference,payload_reference,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], integration_id, event_type,
                data.get("entity_type"), data.get("entity_id"), direction,
                "Received", data.get("external_reference"),
                data.get("payload_reference"), now()
            )
        )
        event_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "integration_event", str(event_id), "RECEIVE", None,
            {"event_type": event_type, "direction": direction}
        )
        con.commit()
        return event_id
    finally:
        con.close()


def update_sync_state(user, data):
    if not has_permission(user["user_id"], "integrations.execute"):
        raise PermissionError("Integration execution permission required")

    integration_id = int(data.get("integration_definition_id") or 0)
    entity_type = data.get("entity_type") or "Generic"
    status = data.get("status") or "Idle"

    con = connect()
    try:
        parent = con.execute(
            """SELECT integration_definition_id FROM integration_definitions
               WHERE integration_definition_id=? AND organisation_id=?""",
            (integration_id, user["organisation_id"])
        ).fetchone()
        if not parent:
            raise ValueError("Integration not found")

        con.execute(
            """INSERT INTO integration_sync_state(
                organisation_id,integration_definition_id,entity_type,
                last_external_cursor,last_sync_at,status,error_message,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,integration_definition_id,entity_type)
            DO UPDATE SET last_external_cursor=excluded.last_external_cursor,
                          last_sync_at=excluded.last_sync_at,
                          status=excluded.status,
                          error_message=excluded.error_message,
                          updated_at=excluded.updated_at""",
            (
                user["organisation_id"], integration_id, entity_type,
                data.get("last_external_cursor"),
                data.get("last_sync_at") or now(),
                status, data.get("error_message"), now()
            )
        )
        con.commit()
    finally:
        con.close()


def list_jobs(user, status=None):
    con = connect()
    clauses = ["j.organisation_id=?"]
    params = [user["organisation_id"]]
    if status:
        clauses.append("j.status=?")
        params.append(status)
    rows = con.execute(
        f"""SELECT j.*,d.integration_code,d.integration_name,
                   e.endpoint_name
            FROM integration_jobs j
            JOIN integration_definitions d
              ON d.integration_definition_id=j.integration_definition_id
            LEFT JOIN integration_endpoints e
              ON e.integration_endpoint_id=j.endpoint_id
            WHERE {' AND '.join(clauses)}
            ORDER BY j.integration_job_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_events(user, status=None):
    con = connect()
    clauses = ["e.organisation_id=?"]
    params = [user["organisation_id"]]
    if status:
        clauses.append("e.status=?")
        params.append(status)
    rows = con.execute(
        f"""SELECT e.*,d.integration_code,d.integration_name
            FROM integration_events e
            JOIN integration_definitions d
              ON d.integration_definition_id=e.integration_definition_id
            WHERE {' AND '.join(clauses)}
            ORDER BY e.integration_event_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    result = {
        "active_integrations": con.execute(
            "SELECT COUNT(*) c FROM integration_definitions WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "queued_jobs": con.execute(
            "SELECT COUNT(*) c FROM integration_jobs WHERE organisation_id=? AND status='Queued'",
            (org,)
        ).fetchone()["c"],
        "running_jobs": con.execute(
            "SELECT COUNT(*) c FROM integration_jobs WHERE organisation_id=? AND status='Running'",
            (org,)
        ).fetchone()["c"],
        "failed_jobs": con.execute(
            "SELECT COUNT(*) c FROM integration_jobs WHERE organisation_id=? AND status='Failed'",
            (org,)
        ).fetchone()["c"],
        "received_events": con.execute(
            "SELECT COUNT(*) c FROM integration_events WHERE organisation_id=? AND status='Received'",
            (org,)
        ).fetchone()["c"],
        "failed_events": con.execute(
            "SELECT COUNT(*) c FROM integration_events WHERE organisation_id=? AND status='Failed'",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return result
