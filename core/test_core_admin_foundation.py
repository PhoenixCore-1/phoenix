import sqlite3
from pathlib import Path

DB = Path("phoenix_core.db")
REQUIRED_TABLES = [
    "organisations", "users", "permissions",
    "roles", "role_permissions", "user_roles",
    "branches", "user_branches", "module_settings",
    "feature_flags", "number_sequences",
    "custom_field_definitions", "custom_field_values",
    "security_events", "audit_events"
]
REQUIRED_PERMISSIONS = [
    "admin.view", "admin.roles", "admin.users", "admin.branches",
    "admin.settings", "admin.custom_fields", "admin.sequences",
    "admin.security"
]

con = sqlite3.connect(DB)
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
missing = [x for x in REQUIRED_TABLES if x not in tables]
assert not missing, f"Missing tables: {missing}"

permissions = {r[0] for r in con.execute("SELECT permission_code FROM permissions")}
missing_permissions = [x for x in REQUIRED_PERMISSIONS if x not in permissions]
assert not missing_permissions, f"Missing permissions: {missing_permissions}"

core = con.execute(
    "SELECT module_id,core,active FROM modules WHERE module_code='core'"
).fetchone()
assert core is not None and core[1] == 1 and core[2] == 1, "Phoenix Core registration missing"

linked = con.execute("""
    SELECT COUNT(*)
    FROM module_permissions mp
    JOIN modules m ON m.module_id=mp.module_id
    JOIN permissions p ON p.permission_id=mp.permission_id
    WHERE m.module_code='core' AND p.permission_code LIKE 'admin.%'
""").fetchone()[0]
assert linked >= 8, "Admin permissions are not attached to Phoenix Core"

con.close()
print("CORE ADMIN FOUNDATION REGRESSION: PASS")
