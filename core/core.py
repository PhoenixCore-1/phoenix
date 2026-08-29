import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from modules import MODULES
from module_contract import BUILTIN_MODULES, module_catalog

DB_PATH = Path(__file__).with_name("phoenix_core.db")
SESSION_HOURS = 12
REMEMBER_SESSION_DAYS = 30

CORE_MODULES = [(m["code"], m["name"], m["description"], int(m["core"])) for m in MODULES]
PERMISSIONS = [
    ("dashboard.view", "View dashboard", "Access the Phoenix dashboard"),
    ("users.view", "View users", "View organisation users"),
    ("users.manage", "Manage users", "Create and manage users"),
    ("roles.view", "View roles", "View roles and permissions"),
    ("roles.manage", "Manage roles", "Manage roles and permissions"),
    ("organisation.manage", "Manage organisation", "Manage organisation configuration"),
    ("tenant.view", "View companies", "View Phoenix tenant companies"),
    ("tenant.create", "Create companies", "Create Phoenix tenant companies"),
    ("tenant.manage", "Manage companies", "Manage Phoenix tenant company details"),
    ("tenant.status.manage", "Manage company status", "Activate or suspend Phoenix tenant companies"),
    ("modules.view", "View modules", "View enabled modules"),
    ("modules.manage", "Manage modules", "Enable or disable modules"),
    ("workflow.view", "View workflows", "View workflow definitions"),
    ("workflow.manage", "Manage workflows", "Manage workflow definitions"),
    ("approval.view", "View approvals", "View approval requests"),
    ("approval.manage", "Manage approvals", "Approve or reject requests"),
    ("audit.view", "View audit", "View audit events"),
]

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con

def hash_password(password):
    salt = secrets.token_bytes(16)
    iterations = 310000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode()
    )

def verify_password(password, stored):
    try:
        algo, iterations, salt_b64, digest_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(),
            base64.b64decode(salt_b64),
            int(iterations)
        )
        return hmac.compare_digest(
            digest,
            base64.b64decode(digest_b64)
        )
    except Exception:
        return False

def migrate_legacy_core_schema(con):
    """Add columns introduced by later Core patches to existing local databases."""
    migrations = {
        "branches": [
            ("branch_type", "TEXT DEFAULT 'BRANCH'"),
            ("address", "TEXT"),
            ("updated_at", "TEXT"),
        ],
        "locations": [
            ("updated_at", "TEXT"),
        ],
        "users": [
            ("email", "TEXT"),
            ("status", "TEXT NOT NULL DEFAULT 'Active'"),
            ("updated_at", "TEXT"),
        ],
    }
    for table, additions in migrations.items():
        exists = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            continue
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, definition in additions:
            if name not in cols:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        if table == "users":
            con.execute("UPDATE users SET status=CASE WHEN active=1 THEN 'Active' ELSE 'Inactive' END WHERE status IS NULL OR status=''")
            con.execute("UPDATE users SET updated_at=created_at WHERE updated_at IS NULL OR updated_at=''")

def migrate_legacy_workflow_schema(con):
    """Migrate older Phoenix workflow_instances tables to the current workflow engine shape."""
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='workflow_instances'"
    ).fetchone()
    if not row:
        return

    cols = {r["name"] for r in con.execute("PRAGMA table_info(workflow_instances)").fetchall()}
    additions = [
        ("workflow_definition_id", "INTEGER"),
        ("current_step_no", "INTEGER NOT NULL DEFAULT 1"),
        ("started_by", "INTEGER"),
        ("updated_at", "TEXT"),
    ]
    for name, definition in additions:
        if name not in cols:
            con.execute(f"ALTER TABLE workflow_instances ADD COLUMN {name} {definition}")

def init_db():
    con = connect()
    schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
    con.executescript(schema)
    migrate_legacy_workflow_schema(con)
    migrate_legacy_core_schema(con)

    for code, name, desc, core in CORE_MODULES:
        con.execute(
            "INSERT OR IGNORE INTO modules(module_code,module_name,description,core,active) VALUES(?,?,?,?,1)",
            (code, name, desc, core)
        )

    for code, name, desc in PERMISSIONS:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )

    org = con.execute("SELECT * FROM organisations ORDER BY organisation_id LIMIT 1").fetchone()
    if not org:
        cur = con.execute(
            "INSERT INTO organisations(organisation_code,organisation_name,created_at) VALUES(?,?,?)",
            ("DEMO", "Demo Organisation", now())
        )
        org_id = cur.lastrowid

        branch = con.execute(
            "INSERT INTO branches(organisation_id,branch_code,branch_name,created_at) VALUES(?,?,?,?)",
            (org_id, "HQ", "Head Office", now())
        )
        branch_id = branch.lastrowid

        location = con.execute(
            "INSERT INTO locations(organisation_id,branch_id,location_code,location_name,created_at) VALUES(?,?,?,?,?)",
            (org_id, branch_id, "HQ", "Head Office", now())
        )
        location_id = location.lastrowid

        role = con.execute(
            "INSERT INTO roles(organisation_id,role_code,role_name,system_role) VALUES(?,?,?,1)",
            (org_id, "system_admin", "System Administrator")
        )
        role_id = role.lastrowid

        # Phoenix Platform System Administrator receives only
        # platform/Core permissions.
        #
        # Business-module permissions are deliberately excluded.
        # Module access belongs to the Company Platform and is
        # additionally controlled by tenant module entitlement.
        #
        # Examples excluded here:
        #   production.*
        #   crm.*
        #   inventory.*
        #   sales.*
        #   projects.*
        #   procurement.*
        #   accounts.*
        #
        # Platform licensing/trial/billing permissions remain
        # available to System Administrator.

        perm_ids = con.execute(
            """
            SELECT permission_id
            FROM permissions
            WHERE
                permission_code NOT LIKE 'production.%'
                AND permission_code NOT LIKE 'crm.%'
                AND permission_code NOT LIKE 'inventory.%'
                AND permission_code NOT LIKE 'sales.%'
                AND permission_code NOT LIKE 'projects.%'
                AND permission_code NOT LIKE 'procurement.%'
                AND permission_code NOT LIKE 'accounts.%'
            """
        ).fetchall()

        for p in perm_ids:
            con.execute(
                "INSERT OR IGNORE INTO role_permissions(role_id,permission_id) VALUES(?,?)",
                (role_id, p["permission_id"])
            )

        user = con.execute(
            """INSERT INTO users(
                organisation_id,username,display_name,email,password_hash,role_id,
                branch_id,location_id,access_scope,password_reset_required,active,status,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                org_id, "admin", "Phoenix Administrator", None,
                hash_password("Admin123!"), role_id,
                branch_id, location_id, "ALL", 0, 1, "Active", now(), now()
            )
        )
        admin_id = user.lastrowid

        core_module = con.execute(
            "SELECT module_id FROM modules WHERE module_code='core'"
        ).fetchone()
        con.execute(
            "INSERT INTO organisation_modules(organisation_id,module_id,enabled) VALUES(?,?,1)",
            (org_id, core_module["module_id"])
        )

        audit(
            con, org_id, admin_id, "organisation", str(org_id),
            "BOOTSTRAP", None, {"organisation": "Demo Organisation"}
        )

    con.commit()
    con.close()
    install_builtin_module_contracts()
    try:
        from crm import ensure_crm_permissions
        ensure_crm_permissions()
    except Exception:
        pass
    try:
        from projects import ensure_projects_permissions
        ensure_projects_permissions()
    except Exception:
        pass
    try:
        from sales import ensure_sales_permissions
        ensure_sales_permissions()
    except Exception:
        pass
    try:
        from production import ensure_production_permissions
        ensure_production_permissions()
    except Exception:
        pass
    try:
        from inventory import ensure_inventory_permissions
        ensure_inventory_permissions()
    except Exception:
        pass
    try:
        from procurement import ensure_procurement_permissions
        ensure_procurement_permissions()
    except Exception:
        pass
    try:
        from accounts import ensure_accounts_permissions
        ensure_accounts_permissions()
    except Exception:
        pass
    try:
        from workflow import ensure_workflow_permissions
        ensure_workflow_permissions()
    except Exception:
        pass
    try:
        from reporting import ensure_reporting_permissions
        ensure_reporting_permissions()
    except Exception:
        pass
    try:
        from integrations import ensure_integrations_permissions
        ensure_integrations_permissions()
    except Exception:
        pass
    try:
        from security_admin import ensure_security_admin_permissions
        ensure_security_admin_permissions()
    except Exception:
        pass
    try:
        from notifications import ensure_notifications_permissions
        ensure_notifications_permissions()
    except Exception:
        pass
    try:
        from auth_admin import ensure_auth_admin_permissions
        ensure_auth_admin_permissions()
    except Exception:
        pass
    try:
        from organisation_admin import ensure_organisation_permissions
        ensure_organisation_permissions()
    except Exception:
        pass
    try:
        from module_licensing import ensure_module_licensing_permissions
        ensure_module_licensing_permissions()
    except Exception:
        pass

    # Platform Administrator is the Core super-administrator for the local
    # Core baseline. Newly registered Core permissions are granted here too.
    try:
        con = connect()
        con.execute(
            """INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
               SELECT r.role_id,p.permission_id
               FROM roles r CROSS JOIN permissions p
               WHERE r.role_code='system_admin'"""
        )
        con.commit()
        con.close()
    except Exception:
        pass

def audit(con, organisation_id, user_id, entity_type, entity_id, action, old=None, new=None, notes=None):
    con.execute(
        """INSERT INTO audit_events(
            organisation_id,user_id,entity_type,entity_id,action,
            old_value_json,new_value_json,notes,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?)""",
        (
            organisation_id, user_id, entity_type, entity_id, action,
            json.dumps(old) if old is not None else None,
            json.dumps(new) if new is not None else None,
            notes, now()
        )
    )

def user_from_session(token):
    con = connect()
    row = con.execute(
        """SELECT u.*, o.organisation_name, r.role_code, r.role_name, r.system_role
           FROM sessions s
           JOIN users u ON u.user_id=s.user_id
           JOIN organisations o ON o.organisation_id=u.organisation_id
           JOIN roles r ON r.role_id=u.role_id
           WHERE s.session_id=? AND s.active=1 AND u.active=1""",
        (token,)
    ).fetchone()
    con.close()
    return row

def create_session(user_id, remember_me=False):
    token = secrets.token_urlsafe(32)
    created = datetime.now(timezone.utc)
    expires = created + (timedelta(days=REMEMBER_SESSION_DAYS) if remember_me else timedelta(hours=SESSION_HOURS))
    con = connect()
    con.execute(
        "INSERT INTO sessions(session_id,user_id,created_at,expires_at) VALUES(?,?,?,?)",
        (token, user_id, created.isoformat(timespec="seconds"), expires.isoformat(timespec="seconds"))
    )
    con.commit()
    con.close()
    return token

def permission_set(user_id):
    con = connect()
    rows = con.execute(
        """SELECT p.permission_code
           FROM users u
           JOIN role_permissions rp ON rp.role_id=u.role_id
           JOIN permissions p ON p.permission_id=rp.permission_id
           WHERE u.user_id=?""",
        (user_id,)
    ).fetchall()
    con.close()
    return {r["permission_code"] for r in rows}

def _module_code_from_permission(permission):
    """
    Resolve a business-module permission to its module code.

    Core/platform permissions such as auth.*, admin.*, audit.*,
    licensing.* and organisation.* remain ordinary role permissions.

    Business-module permissions use the module code as their prefix,
    for example:

        production.view
        crm.view
        inventory.manage
    """
    if not permission or "." not in permission:
        return None

    module_code = str(permission).split(".", 1)[0].strip().lower()

    if module_code in {
        "auth",
        "admin",
        "audit",
        "licensing",
        "modules",
        "organisation",
        "org",
        "platform",
        "billing",
        "security",
        "reporting",
    }:
        return None

    return module_code


def has_module_entitlement(user_id, module_code):
    """
    Return True only when the user's organisation has:

      1. an active Phoenix module,
      2. a valid ACTIVE/TRIAL licence,
      3. an enabled organisation module access record.

    This is a tenant-scoped entitlement check.

    System Administrators do not receive an operational-module
    bypass. Platform authority does not grant access to customer
    business data.
    """
    if not user_id or not module_code:
        return False

    con = connect()

    try:
        row = con.execute(
            """
            SELECT
                m.module_id,
                m.module_code,
                m.active AS module_active,
                l.licence_status,
                l.start_date,
                l.expiry_date,
                oma.enabled
            FROM users u
            JOIN modules m
              ON lower(m.module_code)=lower(?)
            LEFT JOIN module_licences l
              ON l.organisation_id=u.organisation_id
             AND l.module_id=m.module_id
            LEFT JOIN organisation_module_access oma
              ON oma.organisation_id=u.organisation_id
             AND oma.module_id=m.module_id
            WHERE
                u.user_id=?
                AND u.active=1
            """,
            (module_code, user_id)
        ).fetchone()

        if not row:
            return False

        if not row["module_active"]:
            return False

        if not row["enabled"]:
            return False

        if row["licence_status"] not in ("ACTIVE", "TRIAL"):
            return False

        expiry = row["expiry_date"]

        if expiry:
            from datetime import date

            if expiry < date.today().isoformat():
                return False

        return True

    finally:
        con.close()


def has_permission(user_id, permission):
    """
    Central Phoenix authorization contract.

    Core/platform permissions are evaluated through the user's role.

    Business-module permissions require BOTH:

      1. the user's role permission, and
      2. a valid tenant/module entitlement.

    This prevents System Administrator platform authority from
    becoming an automatic bypass into customer business modules.
    """
    if permission not in permission_set(user_id):
        return False

    module_code = _module_code_from_permission(permission)

    if not module_code:
        return True

    return has_module_entitlement(
        user_id,
        module_code
    )

def is_system_admin(user):
    """
    Return True only for the Phoenix platform System Administrator.

    System Administrator is a platform role. This helper deliberately
    checks the authenticated user's role rather than trusting a caller-
    supplied organisation or access scope.
    """
    if not user:
        return False

    return (
        str(user.get("role_code") or "").lower() == "system_admin"
        and int(user.get("system_role") or 0) == 1
    )


def resolve_admin_organisation(user, target_organisation_id=None):
    """
    Resolve the organisation an administrative operation is allowed to
    operate against.

    Rules:
      - Company Administrator is permanently tenant-scoped.
      - System Administrator may explicitly target another active tenant.
      - The authenticated user's organisation_id is never modified.

    Returns:
        int organisation_id

    Raises:
        PermissionError for cross-tenant Company Administrator access.
        ValueError for invalid/inactive target organisations.
    """
    if not user:
        raise PermissionError("Authenticated user is required.")

    own_organisation_id = user.get("organisation_id")

    if own_organisation_id is None:
        raise PermissionError(
            "Authenticated user has no organisation."
        )

    if target_organisation_id is None:
        return int(own_organisation_id)

    try:
        target_organisation_id = int(target_organisation_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid target organisation.")

    if is_system_admin(user):
        from core import connect

        con = connect()
        try:
            row = con.execute(
                """
                SELECT organisation_id
                FROM organisations
                WHERE organisation_id=?
                  AND active=1
                """,
                (target_organisation_id,),
            ).fetchone()
        finally:
            con.close()

        if not row:
            raise ValueError("Target organisation not found or inactive.")

        return int(row["organisation_id"])

    if int(target_organisation_id) != int(own_organisation_id):
        raise PermissionError(
            "Company Administrator cannot access another organisation."
        )

    return int(own_organisation_id)


def can_access_location(user, location_id):
    scope = (user["access_scope"] or "LOCATION").upper()
    if scope == "ALL":
        return True
    con = connect()
    loc = con.execute(
        "SELECT branch_id FROM locations WHERE location_id=? AND organisation_id=?",
        (location_id, user["organisation_id"])
    ).fetchone()
    con.close()
    if not loc:
        return False
    if scope == "LOCATION":
        return user["location_id"] is not None and int(user["location_id"]) == int(location_id)
    if scope == "BRANCH":
        return user["branch_id"] is not None and loc["branch_id"] == user["branch_id"]
    return False


def company_module_status(user):
    """
    Read-only tenant-scoped Phoenix module status.

    Company Administrators may see which Phoenix
    modules are available and active for their
    organisation.

    This function does NOT grant licensing authority.

    Licensing changes remain restricted to
    licensing.manage.
    """
    if not user:
        raise PermissionError(
            "Authentication required"
        )

    if not has_permission(
        user["user_id"],
        "modules.view"
    ):
        raise PermissionError(
            "Permission denied"
        )

    con = connect()

    try:
        rows = con.execute(
            """
            SELECT
                m.module_id,
                m.module_code,
                m.module_name,
                m.description,
                m.core,
                m.active AS module_active,
                COALESCE(
                    oma.enabled,
                    0
                ) AS enabled,
                l.licence_status,
                l.licence_type,
                l.start_date,
                l.expiry_date
            FROM modules m
            LEFT JOIN organisation_module_access oma
              ON oma.module_id = m.module_id
             AND oma.organisation_id = ?
            LEFT JOIN module_licences l
              ON l.module_id = m.module_id
             AND l.organisation_id = ?
            WHERE m.active = 1
            ORDER BY
                m.core DESC,
                m.module_name
            """,
            (
                user["organisation_id"],
                user["organisation_id"],
            ),
        ).fetchall()

        result = []

        from datetime import date

        for row in rows:
            item = dict(row)

            status = item.get(
                "licence_status"
            )

            expiry = item.get(
                "expiry_date"
            )

            licence_valid = (
                status in ("ACTIVE", "TRIAL")
            )

            if licence_valid and expiry:
                try:
                    licence_valid = (
                        date.fromisoformat(
                            expiry
                        )
                        >= date.today()
                    )
                except Exception:
                    licence_valid = False

            item["licence_valid"] = bool(
                licence_valid
            )

            item["active"] = bool(
                item["module_active"]
                and item["enabled"]
                and item["licence_valid"]
            )

            result.append(item)

        return result

    finally:
        con.close()

def enabled_modules(organisation_id):
    con = connect()
    rows = con.execute(
        """SELECT m.module_code,m.module_name,m.description,m.core,om.configuration_json
           FROM organisation_modules om
           JOIN modules m ON m.module_id=om.module_id
           WHERE om.organisation_id=? AND om.enabled=1 AND m.active=1
           ORDER BY m.core DESC,m.module_name""",
        (organisation_id,)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def set_setting(organisation_id, key, value):
    con = connect()
    con.execute(
        """INSERT INTO organisation_settings(organisation_id,setting_key,setting_value,updated_at)
           VALUES(?,?,?,?)
           ON CONFLICT(organisation_id,setting_key)
           DO UPDATE SET setting_value=excluded.setting_value,updated_at=excluded.updated_at""",
        (organisation_id, key, str(value), now())
    )
    con.commit()
    con.close()

def get_settings(organisation_id):
    con = connect()
    rows = con.execute(
        "SELECT setting_key,setting_value FROM organisation_settings WHERE organisation_id=? ORDER BY setting_key",
        (organisation_id,)
    ).fetchall()
    con.close()
    return {r["setting_key"]: r["setting_value"] for r in rows}

def emit_event(organisation_id, user_id, event_type, payload=None):
    con = connect()
    con.execute(
        "INSERT INTO system_events(organisation_id,user_id,event_type,payload_json,created_at) VALUES(?,?,?,?,?)",
        (organisation_id, user_id, event_type, json.dumps(payload or {}), now())
    )
    con.commit()
    con.close()


def register_module_contract(con, module):
    cur = con.execute(
        "INSERT OR IGNORE INTO modules(module_code,module_name,description,core,active) VALUES(?,?,?,?,1)",
        (module.code, module.name, module.description, int(module.core))
    )
    row = con.execute(
        "SELECT module_id FROM modules WHERE module_code=?", (module.code,)
    ).fetchone()
    module_id = row["module_id"]

    for perm in module.permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (perm.code, perm.name, perm.description)
        )
        p = con.execute(
            "SELECT permission_id FROM permissions WHERE permission_code=?", (perm.code,)
        ).fetchone()
        con.execute(
            "INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",
            (module_id, p["permission_id"])
        )

    for item in module.menu:
        con.execute(
            """INSERT OR IGNORE INTO module_menu_items(
                module_id,menu_code,label,route,permission_code,display_order,active
            ) VALUES(?,?,?,?,?,?,1)""",
            (module_id,item.code,item.label,item.route,item.permission,item.order)
        )

def install_builtin_module_contracts():
    con = connect()
    for module in BUILTIN_MODULES:
        register_module_contract(con, module)
    con.commit()
    con.close()

def menu_for_user(user_id):
    con = connect()
    rows = con.execute(
        """SELECT m.module_code,m.module_name,mi.menu_code,mi.label,mi.route,
                  mi.permission_code,mi.display_order
           FROM module_menu_items mi
           JOIN modules m ON m.module_id=mi.module_id
           JOIN organisation_modules om ON om.module_id=m.module_id
           JOIN users u ON u.organisation_id=om.organisation_id
           WHERE u.user_id=? AND om.enabled=1 AND m.active=1 AND mi.active=1
           ORDER BY mi.display_order,mi.menu_id""",
        (user_id,)
    ).fetchall()
    con.close()
    perms = permission_set(user_id)
    return [
        dict(r) for r in rows
        if not r["permission_code"] or r["permission_code"] in perms
    ]

def start_workflow(user_id, workflow_id, entity_type, entity_id):
    con = connect()
    user = con.execute(
        "SELECT organisation_id FROM users WHERE user_id=? AND active=1",
        (user_id,)
    ).fetchone()
    wf = con.execute(
        "SELECT * FROM workflows WHERE workflow_id=? AND organisation_id=? AND active=1",
        (workflow_id, user["organisation_id"] if user else -1)
    ).fetchone() if user else None
    if not user or not wf:
        con.close()
        raise ValueError("Workflow not available")

    first = con.execute(
        """SELECT * FROM workflow_stages
           WHERE workflow_id=? AND active=1
           ORDER BY sequence_no LIMIT 1""",
        (workflow_id,)
    ).fetchone()
    if not first:
        con.close()
        raise ValueError("Workflow has no active stages")

    cur = con.execute(
        """INSERT INTO workflow_instances(
            organisation_id,workflow_id,entity_type,entity_id,
            current_stage_id,status,started_at
        ) VALUES(?,?,?,?,?,?,?)""",
        (
            user["organisation_id"],workflow_id,entity_type,str(entity_id),
            first["stage_id"],"Active",now()
        )
    )
    instance_id = cur.lastrowid
    con.execute(
        """INSERT INTO workflow_instance_events(
            workflow_instance_id,to_stage_id,action,user_id,created_at
        ) VALUES(?,?,?,?,?)""",
        (instance_id,first["stage_id"],"START",user_id,now())
    )
    audit(
        con,user["organisation_id"],user_id,entity_type,str(entity_id),
        "WORKFLOW_START",None,{"workflow_id":workflow_id,"stage_id":first["stage_id"]}
    )
    con.commit()
    con.close()
    return instance_id

def advance_workflow(user_id, instance_id, notes=None):
    con = connect()
    inst = con.execute(
        """SELECT wi.*,u.organisation_id
           FROM workflow_instances wi
           JOIN users u ON u.user_id=?
           WHERE wi.workflow_instance_id=? AND wi.organisation_id=u.organisation_id""",
        (user_id,instance_id)
    ).fetchone()
    if not inst:
        con.close()
        raise ValueError("Workflow instance not found")
    current = con.execute(
        "SELECT * FROM workflow_stages WHERE stage_id=?",
        (inst["current_stage_id"],)
    ).fetchone()
    nxt = con.execute(
        """SELECT * FROM workflow_stages
           WHERE workflow_id=? AND active=1 AND sequence_no>?
           ORDER BY sequence_no LIMIT 1""",
        (inst["workflow_id"],current["sequence_no"])
    ).fetchone()

    if nxt:
        con.execute(
            "UPDATE workflow_instances SET current_stage_id=? WHERE workflow_instance_id=?",
            (nxt["stage_id"],instance_id)
        )
        action = "ADVANCE"
        to_stage = nxt["stage_id"]
        status = "Active"
    else:
        con.execute(
            "UPDATE workflow_instances SET status='Completed',completed_at=? WHERE workflow_instance_id=?",
            (now(),instance_id)
        )
        action = "COMPLETE"
        to_stage = current["stage_id"]
        status = "Completed"

    con.execute(
        """INSERT INTO workflow_instance_events(
            workflow_instance_id,from_stage_id,to_stage_id,action,user_id,notes,created_at
        ) VALUES(?,?,?,?,?,?,?)""",
        (instance_id,current["stage_id"],to_stage,action,user_id,notes,now())
    )
    audit(
        con,inst["organisation_id"],user_id,inst["entity_type"],inst["entity_id"],
        "WORKFLOW_"+action,
        {"stage_id":current["stage_id"]},
        {"stage_id":to_stage,"status":status},
        notes
    )
    con.commit()
    con.close()
    return {"status":status,"stage_id":to_stage}
