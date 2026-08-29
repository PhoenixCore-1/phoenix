from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
DB = ROOT / "phoenix_core_admin_isolation_test.db"

sys.path.insert(0, str(ROOT))

import core

# IMPORTANT:
# Redirect Core's database path only inside this regression test.
# The real phoenix_core.db is never modified.
core.DB_PATH = DB

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

try:
    tenant1 = con.execute("""
        SELECT organisation_id
        FROM organisations
        WHERE organisation_code='DEMO'
          AND active=1
    """).fetchone()

    tenant2 = con.execute("""
        SELECT organisation_id
        FROM organisations
        WHERE organisation_code='TEST2'
          AND active=1
    """).fetchone()

    assert tenant1 is not None, "TEST FAILURE: DEMO tenant missing"
    assert tenant2 is not None, "TEST FAILURE: TEST2 tenant missing"

    tenant1_id = tenant1["organisation_id"]
    tenant2_id = tenant2["organisation_id"]

    system_row = con.execute("""
        SELECT
            u.user_id,
            u.organisation_id,
            u.role_id,
            u.access_scope,
            r.role_code,
            r.system_role
        FROM users u
        JOIN roles r ON r.role_id=u.role_id
        WHERE r.role_code='system_admin'
        LIMIT 1
    """).fetchone()

    assert system_row is not None, "TEST FAILURE: system_admin user missing"

    system_user = dict(system_row)

    company_role = con.execute("""
        SELECT
            role_id,
            organisation_id,
            role_code,
            system_role
        FROM roles
        WHERE organisation_id=?
          AND role_code='company_admin'
    """, (tenant1_id,)).fetchone()

    assert company_role is not None, \
        "TEST FAILURE: Tenant 1 company_admin role missing"

    company_user = {
        "user_id": 999001,
        "organisation_id": tenant1_id,
        "role_id": company_role["role_id"],
        "role_code": company_role["role_code"],
        "system_role": company_role["system_role"],
    }

    # ------------------------------------------------------------
    # SYSTEM ADMIN
    # ------------------------------------------------------------

    assert core.is_system_admin(system_user) is True

    assert core.resolve_admin_organisation(
        system_user,
        tenant1_id
    ) == tenant1_id

    assert core.resolve_admin_organisation(
        system_user,
        tenant2_id
    ) == tenant2_id

    # ------------------------------------------------------------
    # COMPANY ADMIN
    # ------------------------------------------------------------

    assert core.is_system_admin(company_user) is False

    assert core.resolve_admin_organisation(
        company_user
    ) == tenant1_id

    try:
        core.resolve_admin_organisation(
            company_user,
            tenant2_id
        )
    except PermissionError:
        pass
    else:
        raise AssertionError(
            "SECURITY FAILURE: Company Administrator "
            "was allowed to target another organisation."
        )

    # ------------------------------------------------------------
    # AUTHENTICATED IDENTITY MUST NOT CHANGE
    # ------------------------------------------------------------

    assert system_user["organisation_id"] == tenant1_id
    assert company_user["organisation_id"] == tenant1_id

    print("PCA ADMIN SCOPE CONTRACT REGRESSION: PASS")
    print("System Administrator identification: PASS")
    print("System Administrator -> Tenant 1: ALLOW")
    print("System Administrator -> Tenant 2: ALLOW")
    print("Company Administrator -> own tenant: ALLOW")
    print("Company Administrator -> other tenant: DENIED")
    print("Authenticated organisation identity immutable: PASS")

finally:
    con.close()
