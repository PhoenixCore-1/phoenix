import sqlite3
import tempfile
from pathlib import Path
import shutil

import core


ROOT = Path(__file__).resolve().parent
LIVE_DB = ROOT / "phoenix_core.db"

TEST_DB = (
    Path(tempfile.gettempdir())
    / "phoenix_core_control_plane_boundary_test.db"
)

if TEST_DB.exists():
    TEST_DB.unlink()

shutil.copy2(LIVE_DB, TEST_DB)

# Make Core use the isolated test database.
core.DB_PATH = str(TEST_DB)


def section(title):
    print("")
    print("=" * 72)
    print(title)
    print("=" * 72)


def get_user(username):
    con = sqlite3.connect(TEST_DB)
    con.row_factory = sqlite3.Row

    row = con.execute(
        """
        SELECT
            u.*,
            r.role_code,
            r.role_name,
            r.system_role
        FROM users u
        JOIN roles r
            ON r.role_id = u.role_id
        WHERE u.username=?
        """,
        (username,)
    ).fetchone()

    con.close()

    if not row:
        raise RuntimeError(
            f"Required test user not found: {username}"
        )

    return dict(row)


def assert_result(label, actual, expected):
    if actual != expected:
        raise AssertionError(
            f"{label}: expected {expected}, got {actual}"
        )

    print(f"{label}: PASS")


try:

    # ============================================================
    # CORE CONTROL PLANE
    # ============================================================

    section("CORE CONTROL PLANE SECURITY REGRESSION")

    system_admin = get_user("admin")
    company_admin = get_user(
        "pca_test_company_admin"
    )

    print(
        "System Admin:",
        system_admin["username"],
        system_admin["organisation_id"],
        system_admin["role_code"]
    )

    print(
        "Company Admin:",
        company_admin["username"],
        company_admin["organisation_id"],
        company_admin["role_code"]
    )


    # ============================================================
    # SYSTEM ADMINISTRATOR BOUNDARY
    # ============================================================

    section("SYSTEM ADMINISTRATOR BOUNDARY")

    # System Administrator retains Phoenix platform authority.

    assert_result(
        "System Admin licensing.manage",
        core.has_permission(
            system_admin["user_id"],
            "licensing.manage"
        ),
        True
    )

    # System Administrator must NOT have operational
    # business-module permissions.

    assert_result(
        "System Admin production.view",
        core.has_permission(
            system_admin["user_id"],
            "production.view"
        ),
        False
    )

    assert_result(
        "System Admin production.manage",
        core.has_permission(
            system_admin["user_id"],
            "production.manage"
        ),
        False
    )

    assert_result(
        "System Admin production.operate",
        core.has_permission(
            system_admin["user_id"],
            "production.operate"
        ),
        False
    )

    assert_result(
        "System Admin crm.view",
        core.has_permission(
            system_admin["user_id"],
            "crm.view"
        ),
        False
    )

    assert_result(
        "System Admin inventory.view",
        core.has_permission(
            system_admin["user_id"],
            "inventory.view"
        ),
        False
    )


    # ============================================================
    # COMPANY ADMINISTRATOR CORE BOUNDARY
    # ============================================================

    section("COMPANY ADMINISTRATOR BOUNDARY")

    # Company Administrator cannot control licensing.

    assert_result(
        "Company Admin licensing.manage",
        core.has_permission(
            company_admin["user_id"],
            "licensing.manage"
        ),
        False
    )

    # Company Administrator manages company users.

    assert_result(
        "Company Admin admin.users",
        core.has_permission(
            company_admin["user_id"],
            "admin.users"
        ),
        True
    )

    # Company Administrator manages own organisation structure.

    assert_result(
        "Company Admin organisation structure",
        core.has_permission(
            company_admin["user_id"],
            "org.structure.manage"
        ),
        True
    )


    # ============================================================
    # COMPANY ADMIN MODULE VISIBILITY / REPORTING
    # ============================================================

    section(
        "COMPANY ADMIN MODULE VISIBILITY / REPORTING"
    )

    # Company Administrator can see available modules.

    assert_result(
        "Company Admin modules.view",
        core.has_permission(
            company_admin["user_id"],
            "modules.view"
        ),
        True
    )

    # Company Administrator can view reports and dashboards.

    assert_result(
        "Company Admin reporting.view",
        core.has_permission(
            company_admin["user_id"],
            "reporting.view"
        ),
        True
    )

    # Company Administrator cannot create or maintain reports.

    assert_result(
        "Company Admin reporting.manage",
        core.has_permission(
            company_admin["user_id"],
            "reporting.manage"
        ),
        False
    )

    # Company Administrator cannot create or maintain dashboards.

    assert_result(
        "Company Admin reporting.dashboard",
        core.has_permission(
            company_admin["user_id"],
            "reporting.dashboard"
        ),
        False
    )


    # ============================================================
    # COMPANY ADMIN OPERATIONAL ISOLATION
    # ============================================================

    section(
        "COMPANY ADMIN OPERATIONAL ISOLATION"
    )

    # Company Administrator must not become a Production user
    # simply because the company has a Production entitlement.

    assert_result(
        "Company Admin production.view",
        core.has_permission(
            company_admin["user_id"],
            "production.view"
        ),
        False
    )

    assert_result(
        "Company Admin production.manage",
        core.has_permission(
            company_admin["user_id"],
            "production.manage"
        ),
        False
    )

    assert_result(
        "Company Admin production.operate",
        core.has_permission(
            company_admin["user_id"],
            "production.operate"
        ),
        False
    )

    assert_result(
        "Company Admin production.hold",
        core.has_permission(
            company_admin["user_id"],
            "production.hold"
        ),
        False
    )

    assert_result(
        "Company Admin production.resume",
        core.has_permission(
            company_admin["user_id"],
            "production.resume"
        ),
        False
    )


    # ============================================================
    # PRODUCTION TENANT ENTITLEMENT
    # ============================================================

    section(
        "TENANT MODULE ENTITLEMENT"
    )

    # The company itself still has Production entitlement.
    #
    # This proves that:
    #
    # Company entitlement != Company Admin operational permission.

    assert_result(
        "Company Production entitlement",
        core.has_module_entitlement(
            company_admin["user_id"],
            "production"
        ),
        True
    )


    # ============================================================
    # LICENCE SUSPENSION ENFORCEMENT
    # ============================================================

    section(
        "MODULE LICENCE ENFORCEMENT"
    )

    con = sqlite3.connect(TEST_DB)

    production_module = con.execute(
        """
        SELECT module_id
        FROM modules
        WHERE module_code='production'
        """
    ).fetchone()

    if not production_module:
        con.close()
        raise RuntimeError(
            "Production module not found."
        )

    production_module_id = production_module[0]

    con.execute(
        """
        UPDATE module_licences
        SET licence_status='SUSPENDED'
        WHERE
            organisation_id=?
            AND module_id=?
        """,
        (
            company_admin["organisation_id"],
            production_module_id
        )
    )

    con.commit()
    con.close()


    # Tenant entitlement must now be denied.

    assert_result(
        "Production entitlement after suspension",
        core.has_module_entitlement(
            company_admin["user_id"],
            "production"
        ),
        False
    )


    # Company Admin already has no production permission,
    # but this confirms the permission layer remains denied.

    assert_result(
        "Company Admin production.manage after suspension",
        core.has_permission(
            company_admin["user_id"],
            "production.manage"
        ),
        False
    )


    # ============================================================
    # RESTORE TEST LICENCE
    # ============================================================

    con = sqlite3.connect(TEST_DB)

    con.execute(
        """
        UPDATE module_licences
        SET licence_status='TRIAL'
        WHERE
            organisation_id=?
            AND module_id=?
        """,
        (
            company_admin["organisation_id"],
            production_module_id
        )
    )

    con.commit()
    con.close()


    # ============================================================
    # SYSTEM ROLE CONTRACT
    # ============================================================

    section("SYSTEM ROLE CONTRACT")

    assert_result(
        "System Admin platform role",
        core.is_system_admin(system_admin),
        True
    )

    assert_result(
        "Company Admin platform role",
        core.is_system_admin(company_admin),
        False
    )


    # ============================================================
    # TENANT IDENTITY
    # ============================================================

    section("TENANT IDENTITY")

    if system_admin["organisation_id"] != 1:
        raise AssertionError(
            "System Admin organisation identity is incorrect."
        )

    if company_admin["organisation_id"] != 1:
        raise AssertionError(
            "Company Admin organisation identity is incorrect."
        )

    print(
        "Authenticated organisation identity: PASS"
    )


    # ============================================================
    # COMPANY ADMIN LICENSING ISOLATION
    # ============================================================

    section(
        "COMPANY ADMIN LICENSING ISOLATION"
    )

    assert_result(
        "Company Admin licensing.manage",
        core.has_permission(
            company_admin["user_id"],
            "licensing.manage"
        ),
        False
    )


    # ============================================================
    # TEST DATABASE INTEGRITY
    # ============================================================

    section("TEST DATABASE INTEGRITY")

    con = sqlite3.connect(TEST_DB)

    integrity = con.execute(
        "PRAGMA integrity_check"
    ).fetchone()[0]

    foreign_keys = con.execute(
        "PRAGMA foreign_key_check"
    ).fetchall()

    con.close()

    assert_result(
        "SQLite integrity",
        integrity,
        "ok"
    )

    assert_result(
        "Foreign key violations",
        foreign_keys,
        []
    )


    # ============================================================
    # COMPLETE
    # ============================================================

    section("REGRESSION COMPLETE")

    print(
        "PCA CORE CONTROL PLANE BOUNDARY REGRESSION: PASS"
    )

    print("")
    print("SYSTEM ADMINISTRATOR:")
    print("  Platform authority: PASS")
    print("  Licensing authority: PASS")
    print("  Production access: DENIED")
    print("  CRM access: DENIED")
    print("  Inventory access: DENIED")

    print("")
    print("COMPANY ADMINISTRATOR:")
    print("  User administration: PASS")
    print("  Organisation administration: PASS")
    print("  Module visibility: PASS")
    print("  Reporting view: PASS")
    print("  Reporting administration: DENIED")
    print("  Licensing administration: DENIED")
    print("  Production operations: DENIED")

    print("")
    print("TENANT:")
    print("  Production entitlement: PASS")
    print("  Licence suspension enforcement: PASS")

    print("")
    print("DATABASE:")
    print("  SQLite integrity: PASS")
    print("  Foreign key integrity: PASS")

    print("")
    print("=" * 72)
    print(
        "PCA CORE CONTROL PLANE SECURITY REGRESSION: PASS"
    )
    print("=" * 72)


finally:

    if TEST_DB.exists():
        TEST_DB.unlink()