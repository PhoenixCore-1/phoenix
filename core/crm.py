"""
Phoenix CRM v0.1

Generic CRM module for Phoenix Core.
No Upat-specific products, customers, pricing, terminology or business rules.
"""

from core import connect, now, audit, has_permission

ACCOUNT_TYPES = ("Customer", "Prospect", "Partner", "Supplier", "Other")
ACCOUNT_STATUSES = ("Active", "Inactive", "Prospect", "Archived")
ACTIVITY_TYPES = ("Call", "Email", "Meeting", "Task", "Note", "Other")
ACTIVITY_STATUSES = ("Open", "Completed", "Cancelled")


def ensure_crm_permissions():
    con = connect()
    permissions = [
        ("crm.view", "View CRM", "Access CRM records"),
        ("crm.manage", "Manage CRM", "Create and update CRM records"),
        ("crm.activities", "Manage CRM Activities", "Create and manage CRM activities"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='crm'"
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


def _validate_access(user, account_id=None, contact_id=None):
    # v0.1 uses tenant isolation. Fine-grained branch/location filtering
    # remains a Core policy extension rather than a CRM-specific rule.
    con = connect()
    if account_id is not None:
        row = con.execute(
            "SELECT * FROM crm_accounts WHERE account_id=? AND organisation_id=?",
            (account_id, user["organisation_id"])
        ).fetchone()
        if not row:
            con.close()
            raise ValueError("CRM account not found")
    if contact_id is not None:
        row = con.execute(
            "SELECT * FROM crm_contacts WHERE contact_id=? AND organisation_id=?",
            (contact_id, user["organisation_id"])
        ).fetchone()
        if not row:
            con.close()
            raise ValueError("CRM contact not found")
    con.close()


def list_accounts(user, search=""):
    con = connect()
    if search:
        like = f"%{search}%"
        rows = con.execute(
            """SELECT a.*,u.display_name AS owner_name
               FROM crm_accounts a
               LEFT JOIN users u ON u.user_id=a.owner_user_id
               WHERE a.organisation_id=?
                 AND (a.account_name LIKE ? OR a.account_code LIKE ? OR
                      COALESCE(a.email,'') LIKE ? OR COALESCE(a.phone,'') LIKE ?)
               ORDER BY a.account_name""",
            (user["organisation_id"], like, like, like, like)
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT a.*,u.display_name AS owner_name
               FROM crm_accounts a
               LEFT JOIN users u ON u.user_id=a.owner_user_id
               WHERE a.organisation_id=?
               ORDER BY a.account_name""",
            (user["organisation_id"],)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_contacts(user, account_id=None, search=""):
    con = connect()
    clauses = ["c.organisation_id=?"]
    params = [user["organisation_id"]]
    if account_id is not None:
        clauses.append("c.account_id=?")
        params.append(account_id)
    if search:
        like = f"%{search}%"
        clauses.append(
            "(c.first_name LIKE ? OR c.last_name LIKE ? OR COALESCE(c.email,'') LIKE ? OR COALESCE(c.phone,'') LIKE ?)"
        )
        params.extend([like, like, like, like])
    rows = con.execute(
        f"""SELECT c.*,a.account_name,u.display_name AS owner_name
            FROM crm_contacts c
            LEFT JOIN crm_accounts a ON a.account_id=c.account_id
            LEFT JOIN users u ON u.user_id=c.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY c.last_name,c.first_name""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_activities(user, status=None):
    con = connect()
    clauses = ["x.organisation_id=?"]
    params = [user["organisation_id"]]
    if status:
        clauses.append("x.status=?")
        params.append(status)
    rows = con.execute(
        f"""SELECT x.*,a.account_name,
                   c.first_name || ' ' || c.last_name AS contact_name,
                   u.display_name AS owner_name
            FROM crm_activities x
            LEFT JOIN crm_accounts a ON a.account_id=x.account_id
            LEFT JOIN crm_contacts c ON c.contact_id=x.contact_id
            LEFT JOIN users u ON u.user_id=x.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(x.due_at,x.created_at) ASC,x.activity_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_account(user, data):
    if not has_permission(user["user_id"], "crm.manage"):
        raise PermissionError("CRM management permission required")
    name = (data.get("account_name") or "").strip()
    if not name:
        raise ValueError("Account name is required")
    code = (data.get("account_code") or "").strip()
    if not code:
        code = "ACC-" + now().replace("-","").replace(":","").replace("+","").replace(".","")[-12:]
    account_type = data.get("account_type") or "Customer"
    status = data.get("status") or "Active"
    if account_type not in ACCOUNT_TYPES:
        raise ValueError("Invalid account type")
    if status not in ACCOUNT_STATUSES:
        raise ValueError("Invalid account status")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO crm_accounts(
                organisation_id,account_code,account_name,account_type,industry,
                website,phone,email,status,owner_user_id,branch_id,location_id,
                notes,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],code,name,account_type,
                (data.get("industry") or "").strip() or None,
                (data.get("website") or "").strip() or None,
                (data.get("phone") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                status,data.get("owner_user_id") or user["user_id"],
                data.get("branch_id") or None,data.get("location_id") or None,
                (data.get("notes") or "").strip() or None,
                user["user_id"],now(),now()
            )
        )
        account_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "crm_account",str(account_id),"CREATE",
              None,{"account_name":name,"account_type":account_type})
        con.commit()
        return account_id
    finally:
        con.close()


def create_contact(user, data):
    if not has_permission(user["user_id"], "crm.manage"):
        raise PermissionError("CRM management permission required")
    first = (data.get("first_name") or "").strip()
    last = (data.get("last_name") or "").strip()
    if not first or not last:
        raise ValueError("First name and last name are required")
    account_id = data.get("account_id")
    if account_id not in (None, "", 0, "0"):
        account_id = int(account_id)
        _validate_access(user, account_id=account_id)
    else:
        account_id = None

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO crm_contacts(
                organisation_id,account_id,first_name,last_name,job_title,
                department,email,phone,mobile,status,owner_user_id,notes,
                created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],account_id,first,last,
                (data.get("job_title") or "").strip() or None,
                (data.get("department") or "").strip() or None,
                (data.get("email") or "").strip() or None,
                (data.get("phone") or "").strip() or None,
                (data.get("mobile") or "").strip() or None,
                (data.get("status") or "Active"),
                data.get("owner_user_id") or user["user_id"],
                (data.get("notes") or "").strip() or None,
                user["user_id"],now(),now()
            )
        )
        contact_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "crm_contact",str(contact_id),"CREATE",
              None,{"name":f"{first} {last}"})
        con.commit()
        return contact_id
    finally:
        con.close()


def create_activity(user, data):
    if not has_permission(user["user_id"], "crm.activities"):
        raise PermissionError("CRM activity permission required")
    subject = (data.get("subject") or "").strip()
    if not subject:
        raise ValueError("Activity subject is required")
    activity_type = data.get("activity_type") or "Task"
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError("Invalid activity type")
    account_id = data.get("account_id")
    contact_id = data.get("contact_id")
    if account_id not in (None,"",0,"0"):
        account_id = int(account_id)
        _validate_access(user, account_id=account_id)
    else:
        account_id = None
    if contact_id not in (None,"",0,"0"):
        contact_id = int(contact_id)
        _validate_access(user, contact_id=contact_id)
    else:
        contact_id = None

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO crm_activities(
                organisation_id,activity_type,subject,description,account_id,
                contact_id,owner_user_id,due_at,status,created_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],activity_type,subject,
                (data.get("description") or "").strip() or None,
                account_id,contact_id,
                data.get("owner_user_id") or user["user_id"],
                data.get("due_at") or None,"Open",
                user["user_id"],now()
            )
        )
        activity_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "crm_activity",str(activity_id),"CREATE",
              None,{"activity_type":activity_type,"subject":subject})
        con.commit()
        return activity_id
    finally:
        con.close()


def complete_activity(user, activity_id):
    if not has_permission(user["user_id"], "crm.activities"):
        raise PermissionError("CRM activity permission required")
    con = connect()
    row = con.execute(
        "SELECT * FROM crm_activities WHERE activity_id=? AND organisation_id=?",
        (activity_id,user["organisation_id"])
    ).fetchone()
    if not row:
        con.close()
        raise ValueError("Activity not found")
    con.execute(
        "UPDATE crm_activities SET status='Completed',completed_at=? WHERE activity_id=?",
        (now(),activity_id)
    )
    audit(con,user["organisation_id"],user["user_id"],
          "crm_activity",str(activity_id),"COMPLETE",
          {"status":row["status"]},{"status":"Completed"})
    con.commit()
    con.close()


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    data = {
        "accounts": con.execute("SELECT COUNT(*) c FROM crm_accounts WHERE organisation_id=?", (org,)).fetchone()["c"],
        "active_accounts": con.execute("SELECT COUNT(*) c FROM crm_accounts WHERE organisation_id=? AND status='Active'", (org,)).fetchone()["c"],
        "contacts": con.execute("SELECT COUNT(*) c FROM crm_contacts WHERE organisation_id=?", (org,)).fetchone()["c"],
        "open_activities": con.execute("SELECT COUNT(*) c FROM crm_activities WHERE organisation_id=? AND status='Open'", (org,)).fetchone()["c"],
        "overdue_activities": con.execute(
            "SELECT COUNT(*) c FROM crm_activities WHERE organisation_id=? AND status='Open' AND due_at IS NOT NULL AND due_at < ?",
            (org, now())
        ).fetchone()["c"],
    }
    con.close()
    return data
