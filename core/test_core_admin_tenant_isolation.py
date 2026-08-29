from pathlib import Path
import sqlite3

DB = Path(__file__).with_name("phoenix_core_admin_isolation_test.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
con.execute("PRAGMA foreign_keys=ON")

try:
    tenant1 = con.execute(
        "SELECT organisation_id FROM organisations WHERE organisation_code='DEMO'"
    ).fetchone()

    assert tenant1 is not None, "Tenant 1 DEMO organisation missing"
    tenant1_id = tenant1["organisation_id"]

    tenant2 = con.execute(
        "SELECT organisation_id FROM organisations WHERE organisation_code='TEST2'"
    ).fetchone()

    if tenant2:
        tenant2_id = tenant2["organisation_id"]
    else:
        con.execute(
            """
            INSERT INTO organisations(
                organisation_code,
                organisation_name,
                active,
                created_at
            )
            VALUES(
                'TEST2',
                'Isolation Test Organisation',
                1,
                '2026-08-21T00:00:00+00:00'
            )
            """
        )

        tenant2_id = con.execute(
            "SELECT organisation_id FROM organisations WHERE organisation_code='TEST2'"
        ).fetchone()["organisation_id"]

    tenant2_role = con.execute(
        """
        SELECT role_id
        FROM roles
        WHERE organisation_id=?
          AND role_code='company_admin'
        """,
        (tenant2_id,),
    ).fetchone()

    if not tenant2_role:
        con.execute(
            """
            INSERT INTO roles(
                organisation_id,
                role_code,
                role_name,
                system_role,
                active
            )
            VALUES(
                ?,
                'company_admin',
                'Company Administrator',
                0,
                1
            )
            """,
            (tenant2_id,),
        )

    tenant1_role = con.execute(
        """
        SELECT role_id, organisation_id, role_code, system_role
        FROM roles
        WHERE organisation_id=?
          AND role_code='company_admin'
        """,
        (tenant1_id,),
    ).fetchone()

    tenant2_role = con.execute(
        """
        SELECT role_id, organisation_id, role_code, system_role
        FROM roles
        WHERE organisation_id=?
          AND role_code='company_admin'
        """,
        (tenant2_id,),
    ).fetchone()

    assert tenant1_role is not None
    assert tenant2_role is not None

    assert tenant1_role["system_role"] == 0
    assert tenant2_role["system_role"] == 0

    cross_tenant = con.execute(
        """
        SELECT role_id
        FROM roles
        WHERE role_id=?
          AND organisation_id=?
        """,
        (tenant2_role["role_id"], tenant1_id),
    ).fetchone()

    assert cross_tenant is None

    system_admin = con.execute(
        """
        SELECT role_id, organisation_id, role_code, system_role
        FROM roles
        WHERE role_code='system_admin'
        """
    ).fetchone()

    assert system_admin is not None
    assert system_admin["system_role"] == 1

    con.commit()

    print("PCA TENANT ISOLATION REGRESSION: PASS")
    print("Tenant 1 Company Administrator: PASS")
    print("Tenant 2 Company Administrator: PASS")
    print("Cross-tenant Company Administrator lookup: DENIED")
    print("System Administrator platform role: PASS")

finally:
    con.close()
