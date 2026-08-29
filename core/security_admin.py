"""
Phoenix Security & Administration v0.1

Generic platform administration layer.

This module provides:
- roles and role permissions
- user-role assignment
- branch/location administration
- user-branch assignment
- module settings
- feature flags
- number sequences
- custom-field definitions/values
- security event log
- administrative dashboard

It does not embed customer-specific configuration.
"""

import json
import secrets
from core import connect, now, audit, has_permission

CUSTOM_FIELD_TYPES = ("text", "number", "date", "boolean")
SETTING_TYPES = ("string", "number", "boolean", "json")


def ensure_security_admin_permissions():
    con = connect()
    permissions = [
        ("admin.view", "View Administration", "Access platform administration"),
        ("admin.roles", "Manage Roles", "Create roles and assign permissions"),
        ("admin.users", "Manage Users", "Manage users and role/branch assignments"),
        ("admin.branches", "Manage Branches", "Manage organisation branches"),
        ("admin.settings", "Manage Settings", "Manage module settings and feature flags"),
        ("admin.custom_fields", "Manage Custom Fields", "Manage configurable custom fields"),
        ("admin.sequences", "Manage Number Sequences", "Manage document numbering sequences"),
        ("admin.security", "View Security Events", "View security and administrative events"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    # Security & Administration is part of Phoenix Core.
    # It is deliberately NOT registered as an optional customer module.
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='core'"
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


def _require(user, permission):
    if not has_permission(user["user_id"], permission):
        raise PermissionError(f"Permission required: {permission}")


def list_permissions(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        "SELECT * FROM permissions ORDER BY permission_code"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_roles(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        """SELECT r.*,COUNT(rp.permission_id) AS permission_count
           FROM roles r
           LEFT JOIN role_permissions rp ON rp.role_id=r.role_id
           WHERE r.organisation_id=?
           GROUP BY r.role_id
           ORDER BY r.active DESC,r.role_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_role(user, role_id):
    _require(user, "admin.view")
    con = connect()
    role = con.execute(
        "SELECT * FROM roles WHERE role_id=? AND organisation_id=?",
        (role_id, user["organisation_id"])
    ).fetchone()
    if not role:
        con.close()
        raise ValueError("Role not found")
    permissions = con.execute(
        """SELECT p.* FROM permissions p
           JOIN role_permissions rp ON rp.permission_id=p.permission_id
           WHERE rp.role_id=?
           ORDER BY p.permission_code""",
        (role_id,)
    ).fetchall()
    users = con.execute(
        """SELECT u.user_id,u.display_name,u.username,u.status
           FROM users u
           JOIN user_roles ur ON ur.user_id=u.user_id
           WHERE ur.role_id=?
           ORDER BY u.display_name""",
        (role_id,)
    ).fetchall()
    con.close()
    result = dict(role)
    result["permissions"] = [dict(p) for p in permissions]
    result["users"] = [dict(u) for u in users]
    return result


def create_role(user, data):
    _require(user, "admin.roles")
    code = (data.get("role_code") or "").strip()
    name = (data.get("role_name") or "").strip()
    if not code or not name:
        raise ValueError("Role code and role name are required")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO roles(
                organisation_id,role_code,role_name,description,
                created_at,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            (user["organisation_id"], code, name, data.get("description"), now(), now())
        )
        role_id = cur.lastrowid
        audit(
            con,user["organisation_id"],user["user_id"],
            "role",str(role_id),"CREATE",None,{"role_code":code,"role_name":name}
        )
        con.commit()
        return role_id
    finally:
        con.close()


def set_role_permissions(user, role_id, permission_ids):
    _require(user, "admin.roles")
    con = connect()
    try:
        role = con.execute(
            "SELECT * FROM roles WHERE role_id=? AND organisation_id=?",
            (role_id,user["organisation_id"])
        ).fetchone()
        if not role:
            raise ValueError("Role not found")

        con.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
        for pid in permission_ids or []:
            exists = con.execute(
                "SELECT permission_id FROM permissions WHERE permission_id=?",
                (int(pid),)
            ).fetchone()
            if exists:
                con.execute(
                    "INSERT OR IGNORE INTO role_permissions(role_id,permission_id,created_at) VALUES(?,?,?)",
                    (role_id,int(pid),now())
                )
        audit(
            con,user["organisation_id"],user["user_id"],
            "role",str(role_id),"SET_PERMISSIONS",None,
            {"permission_ids":[int(x) for x in (permission_ids or [])]}
        )
        con.commit()
    finally:
        con.close()


def list_users(user):
    _require(user, "admin.users")
    con = connect()
    rows = con.execute(
        """SELECT u.user_id,u.username,u.display_name,u.email,u.status,
                  u.created_at,u.updated_at,
                  GROUP_CONCAT(DISTINCT r.role_name) AS roles
           FROM users u
           LEFT JOIN user_roles ur ON ur.user_id=u.user_id
           LEFT JOIN roles r ON r.role_id=ur.role_id
           WHERE u.organisation_id=?
           GROUP BY u.user_id
           ORDER BY u.display_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def assign_user_role(user, target_user_id, role_id):
    _require(user, "admin.users")
    con = connect()
    try:
        target = con.execute(
            "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
            (target_user_id,user["organisation_id"])
        ).fetchone()
        role = con.execute(
            "SELECT role_id FROM roles WHERE role_id=? AND organisation_id=?",
            (role_id,user["organisation_id"])
        ).fetchone()
        if not target or not role:
            raise ValueError("User or role not found")
        con.execute(
            "INSERT OR IGNORE INTO user_roles(user_id,role_id,created_at) VALUES(?,?,?)",
            (target_user_id,role_id,now())
        )
        audit(
            con,user["organisation_id"],user["user_id"],
            "user",str(target_user_id),"ASSIGN_ROLE",None,{"role_id":role_id}
        )
        con.commit()
    finally:
        con.close()


def remove_user_role(user, target_user_id, role_id):
    _require(user, "admin.users")
    con = connect()
    try:
        con.execute(
            """DELETE FROM user_roles
               WHERE user_id=? AND role_id=?
                 AND user_id IN (SELECT user_id FROM users WHERE organisation_id=?)""",
            (target_user_id,role_id,user["organisation_id"])
        )
        audit(
            con,user["organisation_id"],user["user_id"],
            "user",str(target_user_id),"REMOVE_ROLE",None,{"role_id":role_id}
        )
        con.commit()
    finally:
        con.close()


def list_branches(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        """SELECT b.*,COUNT(ub.user_id) AS user_count
           FROM branches b
           LEFT JOIN user_branches ub ON ub.branch_id=b.branch_id
           WHERE b.organisation_id=?
           GROUP BY b.branch_id
           ORDER BY b.active DESC,b.branch_name""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_branch(user, data):
    _require(user, "admin.branches")
    code = (data.get("branch_code") or "").strip()
    name = (data.get("branch_name") or "").strip()
    if not code or not name:
        raise ValueError("Branch code and name are required")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO branches(
                organisation_id,branch_code,branch_name,description,
                created_at,updated_at
            ) VALUES(?,?,?,?,?,?)""",
            (user["organisation_id"],code,name,data.get("description"),now(),now())
        )
        branch_id = cur.lastrowid
        audit(
            con,user["organisation_id"],user["user_id"],
            "branch",str(branch_id),"CREATE",None,{"branch_code":code,"branch_name":name}
        )
        con.commit()
        return branch_id
    finally:
        con.close()


def assign_user_branch(user, target_user_id, branch_id, is_primary=False):
    _require(user, "admin.users")
    con = connect()
    try:
        target = con.execute(
            "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
            (target_user_id,user["organisation_id"])
        ).fetchone()
        branch = con.execute(
            "SELECT branch_id FROM branches WHERE branch_id=? AND organisation_id=?",
            (branch_id,user["organisation_id"])
        ).fetchone()
        if not target or not branch:
            raise ValueError("User or branch not found")

        if is_primary:
            con.execute(
                """UPDATE user_branches SET is_primary=0
                   WHERE user_id=?""",
                (target_user_id,)
            )
        con.execute(
            """INSERT INTO user_branches(user_id,branch_id,is_primary,created_at)
               VALUES(?,?,?,?)
               ON CONFLICT(user_id,branch_id)
               DO UPDATE SET is_primary=excluded.is_primary""",
            (target_user_id,branch_id,1 if is_primary else 0,now())
        )
        con.commit()
    finally:
        con.close()


def list_module_settings(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        """SELECT * FROM module_settings
           WHERE organisation_id=?
           ORDER BY module_code,setting_key""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def set_module_setting(user, data):
    _require(user, "admin.settings")
    module = (data.get("module_code") or "").strip()
    key = (data.get("setting_key") or "").strip()
    value_type = data.get("value_type") or "string"
    if not module or not key:
        raise ValueError("Module code and setting key are required")
    if value_type not in SETTING_TYPES:
        raise ValueError("Invalid setting type")

    value = data.get("setting_value")
    if value_type == "json":
        value = json.dumps(value if not isinstance(value,str) else json.loads(value))
    elif value_type == "boolean":
        value = "1" if bool(value) else "0"
    else:
        value = str(value) if value is not None else ""

    con = connect()
    try:
        con.execute(
            """INSERT INTO module_settings(
                organisation_id,module_code,setting_key,setting_value,
                value_type,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,module_code,setting_key)
            DO UPDATE SET setting_value=excluded.setting_value,
                          value_type=excluded.value_type,
                          updated_at=excluded.updated_at""",
            (user["organisation_id"],module,key,value,value_type,now(),now())
        )
        con.commit()
    finally:
        con.close()


def list_feature_flags(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        "SELECT * FROM feature_flags WHERE organisation_id=? ORDER BY flag_code",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def set_feature_flag(user, data):
    _require(user, "admin.settings")
    code = (data.get("flag_code") or "").strip()
    name = (data.get("flag_name") or "").strip()
    if not code or not name:
        raise ValueError("Feature flag code and name are required")

    con = connect()
    try:
        con.execute(
            """INSERT INTO feature_flags(
                organisation_id,flag_code,flag_name,enabled,description,
                created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,flag_code)
            DO UPDATE SET flag_name=excluded.flag_name,
                          enabled=excluded.enabled,
                          description=excluded.description,
                          updated_at=excluded.updated_at""",
            (
                user["organisation_id"],code,name,
                1 if data.get("enabled") else 0,
                data.get("description"),now(),now()
            )
        )
        con.commit()
    finally:
        con.close()


def list_sequences(user):
    _require(user, "admin.view")
    con = connect()
    rows = con.execute(
        """SELECT * FROM number_sequences
           WHERE organisation_id=?
           ORDER BY sequence_code""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_sequence(user, data):
    _require(user, "admin.sequences")
    code = (data.get("sequence_code") or "").strip()
    name = (data.get("sequence_name") or "").strip()
    if not code or not name:
        raise ValueError("Sequence code and name are required")
    padding = int(data.get("padding") or 5)
    next_number = int(data.get("next_number") or 1)
    if padding < 1 or padding > 12:
        raise ValueError("Padding must be between 1 and 12")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO number_sequences(
                organisation_id,sequence_code,sequence_name,prefix,
                next_number,padding,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],code,name,data.get("prefix") or "",
                next_number,padding,now(),now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def next_sequence_number(user, sequence_code):
    _require(user, "admin.sequences")
    con = connect()
    try:
        row = con.execute(
            """SELECT * FROM number_sequences
               WHERE organisation_id=? AND sequence_code=? AND active=1""",
            (user["organisation_id"],sequence_code)
        ).fetchone()
        if not row:
            raise ValueError("Number sequence not found")

        number = row["next_number"]
        formatted = f'{row["prefix"] or ""}{number:0{row["padding"]}d}'
        con.execute(
            """UPDATE number_sequences
               SET next_number=next_number+1,updated_at=?
               WHERE number_sequence_id=?""",
            (now(),row["number_sequence_id"])
        )
        con.commit()
        return formatted
    finally:
        con.close()


def list_custom_fields(user, entity_type=None):
    _require(user, "admin.view")
    con = connect()
    if entity_type:
        rows = con.execute(
            """SELECT * FROM custom_field_definitions
               WHERE organisation_id=? AND entity_type=?
               ORDER BY field_name""",
            (user["organisation_id"],entity_type)
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT * FROM custom_field_definitions
               WHERE organisation_id=?
               ORDER BY entity_type,field_name""",
            (user["organisation_id"],)
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_custom_field(user, data):
    _require(user, "admin.custom_fields")
    entity_type = (data.get("entity_type") or "").strip()
    code = (data.get("field_code") or "").strip()
    name = (data.get("field_name") or "").strip()
    field_type = data.get("field_type") or "text"
    if not entity_type or not code or not name:
        raise ValueError("Entity type, field code and field name are required")
    if field_type not in CUSTOM_FIELD_TYPES:
        raise ValueError("Invalid custom field type")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO custom_field_definitions(
                organisation_id,entity_type,field_code,field_name,
                field_type,required,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],entity_type,code,name,field_type,
                1 if data.get("required") else 0,now(),now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def set_custom_field_value(user, data):
    _require(user, "admin.custom_fields")
    definition_id = int(data.get("custom_field_definition_id") or 0)
    entity_type = (data.get("entity_type") or "").strip()
    entity_id = int(data.get("entity_id") or 0)

    con = connect()
    try:
        definition = con.execute(
            """SELECT * FROM custom_field_definitions
               WHERE custom_field_definition_id=? AND organisation_id=?""",
            (definition_id,user["organisation_id"])
        ).fetchone()
        if not definition:
            raise ValueError("Custom field definition not found")
        if definition["entity_type"] != entity_type:
            raise ValueError("Entity type does not match custom field")

        values = {"value_text":None,"value_number":None,"value_date":None,"value_boolean":None}
        ft = definition["field_type"]
        value = data.get("value")
        if ft == "text":
            values["value_text"] = str(value) if value is not None else ""
        elif ft == "number":
            values["value_number"] = float(value)
        elif ft == "date":
            values["value_date"] = str(value)
        elif ft == "boolean":
            values["value_boolean"] = 1 if bool(value) else 0

        con.execute(
            """INSERT INTO custom_field_values(
                organisation_id,custom_field_definition_id,entity_type,entity_id,
                value_text,value_number,value_date,value_boolean,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,custom_field_definition_id,entity_type,entity_id)
            DO UPDATE SET value_text=excluded.value_text,
                          value_number=excluded.value_number,
                          value_date=excluded.value_date,
                          value_boolean=excluded.value_boolean,
                          updated_at=excluded.updated_at""",
            (
                user["organisation_id"],definition_id,entity_type,entity_id,
                values["value_text"],values["value_number"],
                values["value_date"],values["value_boolean"],now(),now()
            )
        )
        con.commit()
    finally:
        con.close()


def list_security_events(user):
    _require(user, "admin.security")
    con = connect()
    rows = con.execute(
        """SELECT s.*,u.display_name
           FROM security_events s
           LEFT JOIN users u ON u.user_id=s.user_id
           WHERE s.organisation_id=?
           ORDER BY s.security_event_id DESC
           LIMIT 200""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def record_security_event(organisation_id, user_id, event_type, success=True, details=None):
    con = connect()
    try:
        con.execute(
            """INSERT INTO security_events(
                organisation_id,user_id,event_type,success,details_json,created_at
            ) VALUES(?,?,?,?,?,?)""",
            (
                organisation_id,user_id,event_type,1 if success else 0,
                json.dumps(details or {}),now()
            )
        )
        con.commit()
    finally:
        con.close()


def dashboard(user):
    _require(user, "admin.view")
    con = connect()
    org = user["organisation_id"]
    result = {
        "users": con.execute(
            "SELECT COUNT(*) c FROM users WHERE organisation_id=?",
            (org,)
        ).fetchone()["c"],
        "active_users": con.execute(
            "SELECT COUNT(*) c FROM users WHERE organisation_id=? AND status='Active'",
            (org,)
        ).fetchone()["c"],
        "roles": con.execute(
            "SELECT COUNT(*) c FROM roles WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "branches": con.execute(
            "SELECT COUNT(*) c FROM branches WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "feature_flags": con.execute(
            "SELECT COUNT(*) c FROM feature_flags WHERE organisation_id=? AND enabled=1",
            (org,)
        ).fetchone()["c"],
        "custom_fields": con.execute(
            "SELECT COUNT(*) c FROM custom_field_definitions WHERE organisation_id=? AND active=1",
            (org,)
        ).fetchone()["c"],
        "security_events": con.execute(
            "SELECT COUNT(*) c FROM security_events WHERE organisation_id=?",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return result
