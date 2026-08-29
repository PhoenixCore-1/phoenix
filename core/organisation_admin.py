"""
Phoenix Core Organisation Administration v1.0

Generic hierarchy:
Organisation
  -> Branch / Location
       -> Warehouse(s)

No customer-specific branch or warehouse assumptions belong here.
"""

from core import connect, now, audit, has_permission, is_system_admin, resolve_admin_organisation


def _require(user, permission):
    if not has_permission(user["user_id"], permission):
        raise PermissionError(f"Permission required: {permission}")


def ensure_organisation_permissions():
    con = connect()
    perms = [
        ("org.structure.view", "View Organisation Structure", "View branches and warehouses"),
        ("org.structure.manage", "Manage Organisation Structure", "Create and maintain branches and warehouses"),
    ]
    for code, name, desc in perms:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
        p = con.execute(
            "SELECT permission_id FROM permissions WHERE permission_code=?",
            (code,)
        ).fetchone()
        core = con.execute(
            "SELECT module_id FROM modules WHERE module_code='core'"
        ).fetchone()
        if p and core:
            con.execute(
                "INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",
                (core["module_id"], p["permission_id"])
            )
            con.execute(
                """INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
                   SELECT role_id,? FROM roles WHERE role_code='system_admin'""",
                (p["permission_id"],)
            )
    con.commit()
    con.close()


def get_structure(user):
    _require(user, "org.structure.view")
    con = connect()
    try:
        org = con.execute(
            """SELECT organisation_id,organisation_name,organisation_code,active
               FROM organisations WHERE organisation_id=?""",
            (user["organisation_id"],)
        ).fetchone()
        branches = con.execute(
            """SELECT branch_id,branch_code,branch_name,branch_type,address,active
               FROM branches WHERE organisation_id=? ORDER BY branch_name""",
            (user["organisation_id"],)
        ).fetchall()
        warehouses = con.execute(
            """SELECT warehouse_id,branch_id,warehouse_code,warehouse_name,
                      warehouse_type,address,active
               FROM warehouses WHERE organisation_id=? ORDER BY warehouse_name""",
            (user["organisation_id"],)
        ).fetchall()
        return {
            "organisation": dict(org) if org else None,
            "branches": [dict(x) for x in branches],
            "warehouses": [dict(x) for x in warehouses],
        }
    finally:
        con.close()


def create_branch(user, data):
    _require(user, "org.structure.manage")
    code = (data.get("branch_code") or "").strip().upper()
    name = (data.get("branch_name") or "").strip()
    if not code or not name:
        raise ValueError("Branch code and name are required")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO branches
               (organisation_id,branch_code,branch_name,branch_type,address,active,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name,
                data.get("branch_type") or "BRANCH",
                data.get("address"),
                1, now(), now()
            )
        )
        branch_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "branch", str(branch_id), "CREATE",
            None, {"branch_code": code, "branch_name": name}
        )
        con.commit()
        return branch_id
    finally:
        con.close()


def create_warehouse(user, data):
    _require(user, "org.structure.manage")
    branch_id = int(data.get("branch_id") or 0)
    code = (data.get("warehouse_code") or "").strip().upper()
    name = (data.get("warehouse_name") or "").strip()
    if not branch_id or not code or not name:
        raise ValueError("Branch, warehouse code and warehouse name are required")

    con = connect()
    try:
        branch = con.execute(
            "SELECT branch_id FROM branches WHERE branch_id=? AND organisation_id=?",
            (branch_id, user["organisation_id"])
        ).fetchone()
        if not branch:
            raise ValueError("Branch not found")

        cur = con.execute(
            """INSERT INTO warehouses
               (organisation_id,branch_id,warehouse_code,warehouse_name,warehouse_type,address,active,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], branch_id, code, name,
                data.get("warehouse_type") or "STANDARD",
                data.get("address"),
                1, now(), now()
            )
        )
        warehouse_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "warehouse", str(warehouse_id), "CREATE",
            None, {"branch_id": branch_id, "warehouse_code": code, "warehouse_name": name}
        )
        con.commit()
        return warehouse_id
    finally:
        con.close()


# ============================================================
# PCA COMPANY / TENANT ADMINISTRATION 1.0
# ============================================================

def _require_system_admin(user, permission):
    """
    Require both the specific tenant-management permission and
    the Phoenix System Administrator platform role.
    """
    if not has_permission(user["user_id"], permission):
        raise PermissionError(f"Permission required: {permission}")

    if not is_system_admin(user):
        raise PermissionError(
            "System Administrator privileges required"
        )


def list_organisations(user):
    """
    List active and inactive Phoenix tenant companies.

    This is a platform-level operation and is restricted to
    System Administrators.
    """
    _require_system_admin(user, "tenant.view")

    con = connect()
    try:
        rows = con.execute(
            """
            SELECT
                organisation_id,
                organisation_code,
                organisation_name,
                active,
                created_at
            FROM organisations
            ORDER BY organisation_name
            """
        ).fetchall()

        return [dict(row) for row in rows]
    finally:
        con.close()


def get_organisation(user, organisation_id=None):
    """
    Return a tenant organisation.

    System Administrators may explicitly target an organisation.
    Company Administrators may only retrieve their own organisation.
    """
    if organisation_id is None:
        organisation_id = user["organisation_id"]

    target_id = resolve_admin_organisation(
        user,
        organisation_id
    )

    if is_system_admin(user):
        permission = "tenant.view"
    else:
        permission = "org.structure.view"

    _require(user, permission)

    con = connect()
    try:
        row = con.execute(
            """
            SELECT
                organisation_id,
                organisation_code,
                organisation_name,
                active,
                created_at
            FROM organisations
            WHERE organisation_id=?
            """,
            (target_id,)
        ).fetchone()

        if not row:
            raise ValueError("Organisation not found")

        return dict(row)
    finally:
        con.close()


def create_organisation(user, data):
    """
    Create a new Phoenix tenant.

    Only System Administrators may create tenants.
    Tenant code is immutable after creation.
    """
    _require_system_admin(user, "tenant.create")

    code = (data.get("organisation_code") or "").strip().upper()
    name = (data.get("organisation_name") or "").strip()

    if not code or not name:
        raise ValueError(
            "Organisation code and organisation name are required"
        )

    con = connect()
    try:
        existing = con.execute(
            """
            SELECT organisation_id
            FROM organisations
            WHERE organisation_code=?
            """,
            (code,)
        ).fetchone()

        if existing:
            raise ValueError(
                f"Organisation code already exists: {code}"
            )

        cur = con.execute(
            """
            INSERT INTO organisations(
                organisation_code,
                organisation_name,
                active,
                created_at
            )
            VALUES(?,?,1,?)
            """,
            (
                code,
                name,
                now(),
            )
        )

        organisation_id = cur.lastrowid

        audit(
            con,
            user["organisation_id"],
            user["user_id"],
            "organisation",
            str(organisation_id),
            "CREATE",
            None,
            {
                "organisation_code": code,
                "organisation_name": name,
                "active": 1,
            },
        )

        con.commit()
        return organisation_id
    finally:
        con.close()


def update_organisation(user, organisation_id, data):
    """
    Update tenant company details.

    System Administrators may update any active tenant.
    Company Administrators may update their own tenant only.

    organisation_code is deliberately immutable.
    """
    target_id = resolve_admin_organisation(
        user,
        organisation_id
    )

    if is_system_admin(user):
        _require_system_admin(user, "tenant.manage")
    else:
        _require(user, "organisation.manage")

    name = (data.get("organisation_name") or "").strip()

    if not name:
        raise ValueError("Organisation name is required")

    con = connect()
    try:
        row = con.execute(
            """
            SELECT
                organisation_id,
                organisation_code,
                organisation_name,
                active
            FROM organisations
            WHERE organisation_id=?
            """,
            (target_id,)
        ).fetchone()

        if not row:
            raise ValueError("Organisation not found")

        old = dict(row)

        con.execute(
            """
            UPDATE organisations
            SET organisation_name=?
            WHERE organisation_id=?
            """,
            (name, target_id)
        )

        new = dict(old)
        new["organisation_name"] = name

        audit(
            con,
            target_id,
            user["user_id"],
            "organisation",
            str(target_id),
            "UPDATE",
            old,
            new,
        )

        con.commit()
        return target_id
    finally:
        con.close()


def set_organisation_status(user, organisation_id, active):
    """
    Activate or suspend a tenant.

    Only System Administrators may change tenant lifecycle status.
    """
    _require_system_admin(user, "tenant.status.manage")

    # Status administration must be able to target an inactive tenant
    # so that a suspended tenant can be reactivated.
    target_id = int(organisation_id)

    con = connect()
    try:
        target = con.execute(
            """
            SELECT organisation_id
            FROM organisations
            WHERE organisation_id=?
            """,
            (target_id,)
        ).fetchone()
    finally:
        con.close()

    if not target:
        raise ValueError("Organisation not found")

    if not is_system_admin(user):
        raise PermissionError(
            "System Administrator privileges required"
        )

    active_value = 1 if bool(active) else 0

    con = connect()
    try:
        row = con.execute(
            """
            SELECT
                organisation_id,
                organisation_code,
                organisation_name,
                active
            FROM organisations
            WHERE organisation_id=?
            """,
            (target_id,)
        ).fetchone()

        if not row:
            raise ValueError("Organisation not found")

        old = dict(row)

        con.execute(
            """
            UPDATE organisations
            SET active=?
            WHERE organisation_id=?
            """,
            (active_value, target_id)
        )

        new = dict(old)
        new["active"] = active_value

        audit(
            con,
            target_id,
            user["user_id"],
            "organisation",
            str(target_id),
            "STATUS_CHANGE",
            old,
            new,
        )

        con.commit()
        return target_id
    finally:
        con.close()
