"""
Phoenix Workflow / Automation v0.1

Generic workflow orchestration foundation.

This version provides:
- workflow definitions
- ordered steps
- workflow instances
- manual actions / transitions
- workflow task queue
- assignment
- completion / cancellation
- action history
- permission-aware execution

It intentionally does NOT embed customer-specific business rules.
Automatic cross-module orchestration is reserved for a later version.
"""

import json
from core import connect, now, audit, has_permission

WORKFLOW_STATUSES = ("Active", "Completed", "Cancelled", "Paused")
TASK_STATUSES = ("Open", "Completed", "Cancelled")
ACTION_TYPES = ("Manual", "Approval", "Notification", "System")
INSTANCE_ACTIONS = ("Start", "Advance", "Complete", "Pause", "Resume", "Cancel")


def ensure_workflow_permissions():
    con = connect()
    permissions = [
        ("workflow.view", "View Workflows", "Access workflow definitions, instances and tasks"),
        ("workflow.manage", "Manage Workflows", "Create and maintain workflow definitions"),
        ("workflow.execute", "Execute Workflows", "Start and advance workflow instances"),
        ("workflow.assign", "Assign Workflow Tasks", "Assign workflow tasks to users"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='workflow'"
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


def list_definitions(user):
    con = connect()
    rows = con.execute(
        """SELECT * FROM workflow_definitions
           WHERE organisation_id=?
           ORDER BY active DESC, workflow_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_definition(user, definition_id):
    con = connect()
    definition = con.execute(
        """SELECT * FROM workflow_definitions
           WHERE workflow_definition_id=? AND organisation_id=?""",
        (definition_id, user["organisation_id"])
    ).fetchone()
    if not definition:
        con.close()
        raise ValueError("Workflow definition not found")
    steps = con.execute(
        """SELECT * FROM workflow_steps
           WHERE workflow_definition_id=?
           ORDER BY step_no""",
        (definition_id,)
    ).fetchall()
    con.close()
    result = dict(definition)
    result["steps"] = [dict(s) for s in steps]
    return result


def create_definition(user, data):
    if not has_permission(user["user_id"], "workflow.manage"):
        raise PermissionError("Workflow management permission required")

    code = (data.get("workflow_code") or "").strip()
    name = (data.get("workflow_name") or "").strip()
    entity_type = (data.get("entity_type") or "").strip()
    if not code or not name or not entity_type:
        raise ValueError("Workflow code, name and entity type are required")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO workflow_definitions(
                organisation_id,workflow_code,workflow_name,entity_type,
                description,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name, entity_type,
                data.get("description"), user["user_id"], now(), now()
            )
        )
        definition_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_definition", str(definition_id), "CREATE", None,
            {"workflow_code": code, "workflow_name": name}
        )
        con.commit()
        return definition_id
    finally:
        con.close()


def add_step(user, definition_id, data):
    if not has_permission(user["user_id"], "workflow.manage"):
        raise PermissionError("Workflow management permission required")

    name = (data.get("step_name") or "").strip()
    code = (data.get("step_code") or "").strip()
    action_type = data.get("action_type") or "Manual"
    if not name or not code:
        raise ValueError("Step code and step name are required")
    if action_type not in ACTION_TYPES:
        raise ValueError("Invalid action type")

    con = connect()
    try:
        definition = con.execute(
            """SELECT * FROM workflow_definitions
               WHERE workflow_definition_id=? AND organisation_id=?""",
            (definition_id, user["organisation_id"])
        ).fetchone()
        if not definition:
            raise ValueError("Workflow definition not found")

        step_no = con.execute(
            """SELECT COALESCE(MAX(step_no),0)+1 n
               FROM workflow_steps WHERE workflow_definition_id=?""",
            (definition_id,)
        ).fetchone()["n"]

        cur = con.execute(
            """INSERT INTO workflow_steps(
                workflow_definition_id,step_no,step_code,step_name,
                action_type,required_permission,next_step_no
            ) VALUES(?,?,?,?,?,?,?)""",
            (
                definition_id, step_no, code, name, action_type,
                data.get("required_permission"), data.get("next_step_no")
            )
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_definition", str(definition_id), "ADD_STEP", None,
            {"step_no": step_no, "step_code": code}
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def start_workflow(user, definition_id, entity_type, entity_id):
    if not has_permission(user["user_id"], "workflow.execute"):
        raise PermissionError("Workflow execution permission required")

    con = connect()
    try:
        definition = con.execute(
            """SELECT * FROM workflow_definitions
               WHERE workflow_definition_id=? AND organisation_id=? AND active=1""",
            (definition_id, user["organisation_id"])
        ).fetchone()
        if not definition:
            raise ValueError("Active workflow definition not found")

        first = con.execute(
            """SELECT * FROM workflow_steps
               WHERE workflow_definition_id=? AND active=1
               ORDER BY step_no LIMIT 1""",
            (definition_id,)
        ).fetchone()
        if not first:
            raise ValueError("Workflow has no active steps")

        existing = con.execute(
            """SELECT * FROM workflow_instances
               WHERE organisation_id=? AND workflow_definition_id=?
                 AND entity_type=? AND entity_id=?""",
            (user["organisation_id"], definition_id, entity_type, int(entity_id))
        ).fetchone()
        if existing and existing["status"] == "Active":
            raise ValueError("An active workflow already exists for this entity")

        cur = con.execute(
            """INSERT INTO workflow_instances(
                organisation_id,workflow_definition_id,entity_type,entity_id,
                status,current_step_no,started_by,started_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], definition_id, entity_type, int(entity_id),
                "Active", first["step_no"], user["user_id"], now(), now()
            )
        )
        instance_id = cur.lastrowid

        con.execute(
            """INSERT INTO workflow_actions(
                workflow_instance_id,workflow_step_id,action_type,
                from_step_no,to_step_no,user_id,metadata_json,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                instance_id, first["workflow_step_id"], "Start",
                None, first["step_no"], user["user_id"],
                json.dumps({"entity_type": entity_type, "entity_id": int(entity_id)}),
                now()
            )
        )

        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_instance", str(instance_id), "START", None,
            {"entity_type": entity_type, "entity_id": int(entity_id)}
        )
        con.commit()
        return instance_id
    finally:
        con.close()


def list_instances(user, status=None):
    con = connect()
    clauses = ["i.organisation_id=?"]
    params = [user["organisation_id"]]
    if status:
        clauses.append("i.status=?")
        params.append(status)
    rows = con.execute(
        f"""SELECT i.*,d.workflow_code,d.workflow_name
            FROM workflow_instances i
            JOIN workflow_definitions d
              ON d.workflow_definition_id=i.workflow_definition_id
            WHERE {' AND '.join(clauses)}
            ORDER BY i.workflow_instance_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_instance(user, instance_id):
    con = connect()
    instance = con.execute(
        """SELECT i.*,d.workflow_code,d.workflow_name
           FROM workflow_instances i
           JOIN workflow_definitions d ON d.workflow_definition_id=i.workflow_definition_id
           WHERE i.workflow_instance_id=? AND i.organisation_id=?""",
        (instance_id, user["organisation_id"])
    ).fetchone()
    if not instance:
        con.close()
        raise ValueError("Workflow instance not found")

    step = con.execute(
        """SELECT * FROM workflow_steps
           WHERE workflow_definition_id=? AND step_no=?""",
        (instance["workflow_definition_id"], instance["current_step_no"])
    ).fetchone()

    actions = con.execute(
        """SELECT a.*,u.display_name,s.step_name
           FROM workflow_actions a
           JOIN users u ON u.user_id=a.user_id
           LEFT JOIN workflow_steps s ON s.workflow_step_id=a.workflow_step_id
           WHERE a.workflow_instance_id=?
           ORDER BY a.workflow_action_id DESC""",
        (instance_id,)
    ).fetchall()

    tasks = con.execute(
        """SELECT t.*,s.step_name,
                  u.display_name AS assigned_name
           FROM workflow_tasks t
           JOIN workflow_steps s ON s.workflow_step_id=t.workflow_step_id
           LEFT JOIN users u ON u.user_id=t.assigned_to
           WHERE t.workflow_instance_id=?
           ORDER BY t.workflow_task_id DESC""",
        (instance_id,)
    ).fetchall()

    con.close()
    result = dict(instance)
    result["current_step"] = dict(step) if step else None
    result["actions"] = [dict(a) for a in actions]
    result["tasks"] = [dict(t) for t in tasks]
    return result


def advance_workflow(user, instance_id, reason=None):
    if not has_permission(user["user_id"], "workflow.execute"):
        raise PermissionError("Workflow execution permission required")

    con = connect()
    try:
        instance = con.execute(
            """SELECT * FROM workflow_instances
               WHERE workflow_instance_id=? AND organisation_id=?""",
            (instance_id, user["organisation_id"])
        ).fetchone()
        if not instance:
            raise ValueError("Workflow instance not found")
        if instance["status"] != "Active":
            raise ValueError("Workflow instance is not active")

        current = con.execute(
            """SELECT * FROM workflow_steps
               WHERE workflow_definition_id=? AND step_no=?""",
            (instance["workflow_definition_id"], instance["current_step_no"])
        ).fetchone()
        if not current:
            raise ValueError("Current workflow step not found")

        if current["required_permission"] and not has_permission(
            user["user_id"], current["required_permission"]
        ):
            raise PermissionError(
                f"Permission required: {current['required_permission']}"
            )

        next_step = None
        if current["next_step_no"]:
            next_step = con.execute(
                """SELECT * FROM workflow_steps
                   WHERE workflow_definition_id=? AND step_no=? AND active=1""",
                (instance["workflow_definition_id"], current["next_step_no"])
            ).fetchone()
        else:
            next_step = con.execute(
                """SELECT * FROM workflow_steps
                   WHERE workflow_definition_id=? AND step_no>? AND active=1
                   ORDER BY step_no LIMIT 1""",
                (instance["workflow_definition_id"], current["step_no"])
            ).fetchone()

        if next_step:
            con.execute(
                """UPDATE workflow_instances
                   SET current_step_no=?,updated_at=?
                   WHERE workflow_instance_id=?""",
                (next_step["step_no"], now(), instance_id)
            )
            action_type = "Advance"
            to_step = next_step["step_no"]
            status = "Active"
        else:
            con.execute(
                """UPDATE workflow_instances
                   SET status='Completed',completed_at=?,updated_at=?
                   WHERE workflow_instance_id=?""",
                (now(), now(), instance_id)
            )
            action_type = "Complete"
            to_step = None
            status = "Completed"

        con.execute(
            """INSERT INTO workflow_actions(
                workflow_instance_id,workflow_step_id,action_type,
                from_step_no,to_step_no,user_id,reason,created_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                instance_id, current["workflow_step_id"], action_type,
                current["step_no"], to_step, user["user_id"], reason, now()
            )
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_instance", str(instance_id), action_type,
            {"step_no": current["step_no"], "status": instance["status"]},
            {"step_no": to_step, "status": status},
            reason
        )
        con.commit()
        return status
    finally:
        con.close()


def set_instance_state(user, instance_id, new_status, reason=None):
    if not has_permission(user["user_id"], "workflow.execute"):
        raise PermissionError("Workflow execution permission required")
    if new_status not in ("Paused", "Cancelled", "Active"):
        raise ValueError("Invalid workflow state")

    con = connect()
    try:
        instance = con.execute(
            """SELECT * FROM workflow_instances
               WHERE workflow_instance_id=? AND organisation_id=?""",
            (instance_id, user["organisation_id"])
        ).fetchone()
        if not instance:
            raise ValueError("Workflow instance not found")

        if new_status == "Active" and instance["status"] != "Paused":
            raise ValueError("Only Paused workflows can be resumed")
        if new_status == "Paused" and instance["status"] != "Active":
            raise ValueError("Only Active workflows can be paused")
        if new_status == "Cancelled" and instance["status"] in ("Completed","Cancelled"):
            raise ValueError("Workflow cannot be cancelled from its current state")

        con.execute(
            """UPDATE workflow_instances
               SET status=?,updated_at=?,
                   completed_at=CASE WHEN ?='Cancelled' THEN ? ELSE completed_at END
               WHERE workflow_instance_id=?""",
            (new_status, now(), new_status, now() if new_status=="Cancelled" else None, instance_id)
        )
        action = "Resume" if new_status=="Active" else new_status[:-1] if new_status=="Paused" else new_status
        con.execute(
            """INSERT INTO workflow_actions(
                workflow_instance_id,action_type,from_step_no,to_step_no,
                user_id,reason,created_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (instance_id, action, instance["current_step_no"], instance["current_step_no"],
             user["user_id"], reason, now())
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_instance", str(instance_id), action,
            {"status": instance["status"]}, {"status": new_status}, reason
        )
        con.commit()
    finally:
        con.close()


def create_task(user, instance_id, data):
    if not has_permission(user["user_id"], "workflow.assign"):
        raise PermissionError("Workflow assignment permission required")

    con = connect()
    try:
        instance = con.execute(
            """SELECT * FROM workflow_instances
               WHERE workflow_instance_id=? AND organisation_id=?""",
            (instance_id, user["organisation_id"])
        ).fetchone()
        if not instance:
            raise ValueError("Workflow instance not found")

        step_id = int(data.get("workflow_step_id") or 0)
        step = con.execute(
            """SELECT * FROM workflow_steps
               WHERE workflow_step_id=? AND workflow_definition_id=?""",
            (step_id, instance["workflow_definition_id"])
        ).fetchone()
        if not step:
            raise ValueError("Workflow step not found")

        assigned_to = data.get("assigned_to")
        if assigned_to:
            user_row = con.execute(
                "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
                (int(assigned_to), user["organisation_id"])
            ).fetchone()
            if not user_row:
                raise ValueError("Assigned user not found")

        cur = con.execute(
            """INSERT INTO workflow_tasks(
                organisation_id,workflow_instance_id,workflow_step_id,
                assigned_to,due_at,notes,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], instance_id, step_id,
                int(assigned_to) if assigned_to else None,
                data.get("due_at"), data.get("notes"),
                now(), now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def complete_task(user, task_id, notes=None):
    if not has_permission(user["user_id"], "workflow.execute"):
        raise PermissionError("Workflow execution permission required")

    con = connect()
    try:
        task = con.execute(
            """SELECT * FROM workflow_tasks
               WHERE workflow_task_id=? AND organisation_id=?""",
            (task_id, user["organisation_id"])
        ).fetchone()
        if not task:
            raise ValueError("Workflow task not found")
        if task["status"] != "Open":
            raise ValueError("Workflow task is not open")

        con.execute(
            """UPDATE workflow_tasks
               SET status='Completed',completed_at=?,completed_by=?,
                   notes=COALESCE(?,notes),updated_at=?
               WHERE workflow_task_id=?""",
            (now(), user["user_id"], notes, now(), task_id)
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "workflow_task", str(task_id), "COMPLETE",
            {"status": "Open"}, {"status": "Completed"}
        )
        con.commit()
    finally:
        con.close()


def list_tasks(user, status="Open"):
    con = connect()
    clauses = ["t.organisation_id=?"]
    params = [user["organisation_id"]]
    if status:
        clauses.append("t.status=?")
        params.append(status)
    rows = con.execute(
        f"""SELECT t.*,s.step_name,d.workflow_name,i.entity_type,i.entity_id,
                   u.display_name AS assigned_name
            FROM workflow_tasks t
            JOIN workflow_steps s ON s.workflow_step_id=t.workflow_step_id
            JOIN workflow_instances i ON i.workflow_instance_id=t.workflow_instance_id
            JOIN workflow_definitions d ON d.workflow_definition_id=i.workflow_definition_id
            LEFT JOIN users u ON u.user_id=t.assigned_to
            WHERE {' AND '.join(clauses)}
            ORDER BY t.workflow_task_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    d = {
        "definitions": con.execute(
            "SELECT COUNT(*) c FROM workflow_definitions WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "active_instances": con.execute(
            "SELECT COUNT(*) c FROM workflow_instances WHERE organisation_id=? AND status='Active'",
            (org,)
        ).fetchone()["c"],
        "paused_instances": con.execute(
            "SELECT COUNT(*) c FROM workflow_instances WHERE organisation_id=? AND status='Paused'",
            (org,)
        ).fetchone()["c"],
        "open_tasks": con.execute(
            "SELECT COUNT(*) c FROM workflow_tasks WHERE organisation_id=? AND status='Open'",
            (org,)
        ).fetchone()["c"],
        "completed_instances": con.execute(
            "SELECT COUNT(*) c FROM workflow_instances WHERE organisation_id=? AND status='Completed'",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return d
