"""
Phoenix Projects v0.1

Generic project management module built on Phoenix Core.
CRM accounts are an optional relationship; Projects does not import
customer-specific business rules from any implementation.
"""

from core import connect, now, audit, has_permission

DEFAULT_STATUSES = [
    ("PLANNED", "Planned", 10),
    ("ACTIVE", "Active", 20),
    ("ON_HOLD", "On Hold", 30),
    ("COMPLETED", "Completed", 40),
    ("CANCELLED", "Cancelled", 50),
]
PROJECT_PRIORITIES = ("Low", "Normal", "High", "Critical")
TASK_STATUSES = ("Open", "In Progress", "Blocked", "Completed", "Cancelled")
TASK_PRIORITIES = ("Low", "Normal", "High", "Critical")


def ensure_projects_permissions():
    con = connect()
    permissions = [
        ("projects.view", "View Projects", "Access project records"),
        ("projects.manage", "Manage Projects", "Create and update projects"),
        ("projects.tasks", "Manage Project Tasks", "Create and update project tasks"),
        ("projects.milestones", "Manage Project Milestones", "Create and update milestones"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='projects'"
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


def ensure_statuses(organisation_id):
    con = connect()
    for code, name, order in DEFAULT_STATUSES:
        con.execute(
            """INSERT OR IGNORE INTO project_statuses(
                organisation_id,status_code,status_name,display_order
            ) VALUES(?,?,?,?)""",
            (organisation_id, code, name, order)
        )
    con.commit()
    con.close()


def list_projects(user, search=""):
    ensure_statuses(user["organisation_id"])
    con = connect()
    clauses = ["p.organisation_id=?"]
    params = [user["organisation_id"]]
    if search:
        like = f"%{search}%"
        clauses.append("(p.project_name LIKE ? OR p.project_code LIKE ? OR COALESCE(p.description,'') LIKE ?)")
        params.extend([like, like, like])
    rows = con.execute(
        f"""SELECT p.*,s.status_name,
                   a.account_name,
                   u.display_name AS owner_name
            FROM projects p
            JOIN project_statuses s ON s.status_id=p.status_id
            LEFT JOIN crm_accounts a ON a.account_id=p.account_id
            LEFT JOIN users u ON u.user_id=p.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY
                CASE p.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                                WHEN 'Normal' THEN 3 ELSE 4 END,
                COALESCE(p.target_date,'9999-12-31'),p.project_name""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_tasks(user, project_id=None):
    con = connect()
    clauses = ["t.organisation_id=?"]
    params = [user["organisation_id"]]
    if project_id is not None:
        clauses.append("t.project_id=?")
        params.append(project_id)
    rows = con.execute(
        f"""SELECT t.*,p.project_name,u.display_name AS owner_name
            FROM project_tasks t
            JOIN projects p ON p.project_id=t.project_id
            LEFT JOIN users u ON u.user_id=t.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(t.due_date,'9999-12-31'),t.task_id""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_milestones(user, project_id=None):
    con = connect()
    clauses = ["m.organisation_id=?"]
    params = [user["organisation_id"]]
    if project_id is not None:
        clauses.append("m.project_id=?")
        params.append(project_id)
    rows = con.execute(
        f"""SELECT m.*,p.project_name,u.display_name AS owner_name
            FROM project_milestones m
            JOIN projects p ON p.project_id=m.project_id
            LEFT JOIN users u ON u.user_id=m.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(m.due_date,'9999-12-31'),m.milestone_id""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_project(user, data):
    if not has_permission(user["user_id"], "projects.manage"):
        raise PermissionError("Project management permission required")
    name = (data.get("project_name") or "").strip()
    if not name:
        raise ValueError("Project name is required")
    code = (data.get("project_code") or "").strip()
    if not code:
        code = "PRJ-" + now().replace("-","").replace(":","").replace("+","").replace(".","")[-12:]
    priority = data.get("priority") or "Normal"
    if priority not in PROJECT_PRIORITIES:
        raise ValueError("Invalid project priority")

    account_id = data.get("account_id")
    if account_id not in (None,"",0,"0"):
        account_id = int(account_id)
        con_check = connect()
        ok = con_check.execute(
            "SELECT 1 FROM crm_accounts WHERE account_id=? AND organisation_id=?",
            (account_id,user["organisation_id"])
        ).fetchone()
        con_check.close()
        if not ok:
            raise ValueError("CRM account not found in this organisation")
    else:
        account_id = None

    ensure_statuses(user["organisation_id"])
    con = connect()
    status = con.execute(
        "SELECT status_id FROM project_statuses WHERE organisation_id=? AND status_code='PLANNED'",
        (user["organisation_id"],)
    ).fetchone()

    try:
        cur = con.execute(
            """INSERT INTO projects(
                organisation_id,project_code,project_name,description,status_id,
                account_id,owner_user_id,manager_user_id,branch_id,location_id,
                start_date,target_date,priority,notes,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],code,name,
                (data.get("description") or "").strip() or None,
                status["status_id"],account_id,
                data.get("owner_user_id") or user["user_id"],
                data.get("manager_user_id") or user["user_id"],
                data.get("branch_id") or None,data.get("location_id") or None,
                data.get("start_date") or None,data.get("target_date") or None,
                priority,(data.get("notes") or "").strip() or None,
                user["user_id"],now(),now()
            )
        )
        project_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "project",str(project_id),"CREATE",None,
              {"project_code":code,"project_name":name,"priority":priority})
        con.commit()
        return project_id
    finally:
        con.close()


def create_task(user, data):
    if not has_permission(user["user_id"], "projects.tasks"):
        raise PermissionError("Project task permission required")
    project_id = int(data.get("project_id") or 0)
    name = (data.get("task_name") or "").strip()
    if not project_id or not name:
        raise ValueError("Project and task name are required")
    con = connect()
    project = con.execute(
        "SELECT project_id FROM projects WHERE project_id=? AND organisation_id=?",
        (project_id,user["organisation_id"])
    ).fetchone()
    if not project:
        con.close()
        raise ValueError("Project not found")
    code = (data.get("task_code") or "").strip()
    if not code:
        count = con.execute(
            "SELECT COUNT(*) c FROM project_tasks WHERE project_id=?",
            (project_id,)
        ).fetchone()["c"] + 1
        code = f"T-{count:03d}"
    priority = data.get("priority") or "Normal"
    if priority not in TASK_PRIORITIES:
        con.close()
        raise ValueError("Invalid task priority")
    status = data.get("status") or "Open"
    if status not in TASK_STATUSES:
        con.close()
        raise ValueError("Invalid task status")
    try:
        cur = con.execute(
            """INSERT INTO project_tasks(
                organisation_id,project_id,parent_task_id,task_code,task_name,
                description,status,priority,owner_user_id,start_date,due_date,
                created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],project_id,
                data.get("parent_task_id") or None,code,name,
                (data.get("description") or "").strip() or None,status,priority,
                data.get("owner_user_id") or user["user_id"],
                data.get("start_date") or None,data.get("due_date") or None,
                user["user_id"],now(),now()
            )
        )
        task_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "project_task",str(task_id),"CREATE",None,
              {"project_id":project_id,"task_name":name})
        con.commit()
        return task_id
    finally:
        con.close()


def complete_task(user, task_id):
    if not has_permission(user["user_id"], "projects.tasks"):
        raise PermissionError("Project task permission required")
    con = connect()
    row = con.execute(
        """SELECT * FROM project_tasks
           WHERE task_id=? AND organisation_id=?""",
        (task_id,user["organisation_id"])
    ).fetchone()
    if not row:
        con.close()
        raise ValueError("Task not found")
    con.execute(
        "UPDATE project_tasks SET status='Completed',completed_at=?,updated_at=? WHERE task_id=?",
        (now(),now(),task_id)
    )
    audit(con,user["organisation_id"],user["user_id"],
          "project_task",str(task_id),"COMPLETE",
          {"status":row["status"]},{"status":"Completed"})
    con.commit()
    con.close()


def create_milestone(user, data):
    if not has_permission(user["user_id"], "projects.milestones"):
        raise PermissionError("Project milestone permission required")
    project_id = int(data.get("project_id") or 0)
    name = (data.get("milestone_name") or "").strip()
    if not project_id or not name:
        raise ValueError("Project and milestone name are required")
    con = connect()
    project = con.execute(
        "SELECT project_id FROM projects WHERE project_id=? AND organisation_id=?",
        (project_id,user["organisation_id"])
    ).fetchone()
    if not project:
        con.close()
        raise ValueError("Project not found")
    code = (data.get("milestone_code") or "").strip()
    if not code:
        count = con.execute(
            "SELECT COUNT(*) c FROM project_milestones WHERE project_id=?",
            (project_id,)
        ).fetchone()["c"] + 1
        code = f"M-{count:03d}"
    try:
        cur = con.execute(
            """INSERT INTO project_milestones(
                organisation_id,project_id,milestone_code,milestone_name,
                description,due_date,status,owner_user_id,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],project_id,code,name,
                (data.get("description") or "").strip() or None,
                data.get("due_date") or None,
                "Open",data.get("owner_user_id") or user["user_id"],
                user["user_id"],now(),now()
            )
        )
        milestone_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "project_milestone",str(milestone_id),"CREATE",None,
              {"project_id":project_id,"milestone_name":name})
        con.commit()
        return milestone_id
    finally:
        con.close()


def complete_milestone(user, milestone_id):
    if not has_permission(user["user_id"], "projects.milestones"):
        raise PermissionError("Project milestone permission required")
    con = connect()
    row = con.execute(
        "SELECT * FROM project_milestones WHERE milestone_id=? AND organisation_id=?",
        (milestone_id,user["organisation_id"])
    ).fetchone()
    if not row:
        con.close()
        raise ValueError("Milestone not found")
    con.execute(
        "UPDATE project_milestones SET status='Completed',completed_at=?,updated_at=? WHERE milestone_id=?",
        (now(),now(),milestone_id)
    )
    audit(con,user["organisation_id"],user["user_id"],
          "project_milestone",str(milestone_id),"COMPLETE",
          {"status":row["status"]},{"status":"Completed"})
    con.commit()
    con.close()


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    data = {
        "projects": con.execute(
            "SELECT COUNT(*) c FROM projects WHERE organisation_id=?", (org,)
        ).fetchone()["c"],
        "active_projects": con.execute(
            """SELECT COUNT(*) c FROM projects p
               JOIN project_statuses s ON s.status_id=p.status_id
               WHERE p.organisation_id=? AND s.status_code='ACTIVE'""", (org,)
        ).fetchone()["c"],
        "open_tasks": con.execute(
            "SELECT COUNT(*) c FROM project_tasks WHERE organisation_id=? AND status NOT IN ('Completed','Cancelled')",
            (org,)
        ).fetchone()["c"],
        "overdue_tasks": con.execute(
            """SELECT COUNT(*) c FROM project_tasks
               WHERE organisation_id=? AND status NOT IN ('Completed','Cancelled')
                 AND due_date IS NOT NULL AND due_date < ?""",
            (org,now())
        ).fetchone()["c"],
        "open_milestones": con.execute(
            "SELECT COUNT(*) c FROM project_milestones WHERE organisation_id=? AND status='Open'",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return data
