"""
Phoenix Core Module Licensing & Entitlements v1.0

Commercial access chain:
Catalogue -> Licence/Entitlement -> Enabled -> User Permission -> Access
"""

from datetime import date
from core import connect, now, audit, has_permission


def ensure_module_licensing_permissions():
    con=connect()
    perms=[
        ("licensing.view","View Module Licensing","View organisation module licences"),
        ("licensing.manage","Manage Module Licensing","Create/change/suspend module licences"),
    ]
    for code,name,desc in perms:
        con.execute("INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",(code,name,desc))
        p=con.execute("SELECT permission_id FROM permissions WHERE permission_code=?",(code,)).fetchone()
        core=con.execute("SELECT module_id FROM modules WHERE module_code='core'").fetchone()
        if p and core:
            con.execute("INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",(core["module_id"],p["permission_id"]))
            con.execute("""INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
                           SELECT role_id,? FROM roles WHERE role_code='system_admin'""",(p["permission_id"],))
    con.commit(); con.close()


def _require(user,p):
    if not has_permission(user["user_id"],p):
        raise PermissionError(f"Permission required: {p}")


def _normalise_status(status):
    status=(status or "ACTIVE").upper()
    allowed={"TRIAL","ACTIVE","EXPIRED","SUSPENDED","NOT_LICENSED"}
    if status not in allowed:
        raise ValueError("Invalid licence status")
    return status


def licence_is_valid(row):
    if not row:
        return False
    status=row["licence_status"]
    if status not in ("ACTIVE","TRIAL"):
        return False
    expiry=row["expiry_date"]
    if expiry and expiry < date.today().isoformat():
        return False
    return True


def list_licences(user):
    _require(user,"licensing.view")
    con=connect()
    rows=con.execute("""SELECT m.module_id,m.module_code,m.module_name,COALESCE(oma.enabled,0) AS enabled,
                              l.licence_id,l.licence_status,l.licence_type,
                              l.start_date,l.expiry_date,l.seats,l.auto_enable
                       FROM modules m
                       LEFT JOIN module_licences l
                         ON l.module_id=m.module_id AND l.organisation_id=?
                       LEFT JOIN organisation_module_access oma
                         ON oma.module_id=m.module_id AND oma.organisation_id=?
                       ORDER BY m.module_name""",(user["organisation_id"],user["organisation_id"])).fetchall()
    con.close()
    result=[]
    for r in rows:
        d=dict(r)
        d["licence_valid"]=licence_is_valid(r)
        result.append(d)
    return result


def set_licence(user,module_id,status="ACTIVE",licence_type="COMMERCIAL",
                start_date=None,expiry_date=None,seats=None,auto_enable=False,notes=None):
    _require(user,"licensing.manage")
    status=_normalise_status(status)
    con=connect()
    try:
        module=con.execute("SELECT module_id,module_code,module_name FROM modules WHERE module_id=?",(int(module_id),)).fetchone()
        if not module:
            raise ValueError("Module not found")

        # A module cannot be enabled unless its licence is valid.
        if status in ("NOT_LICENSED","EXPIRED","SUSPENDED"):
            con.execute("""INSERT INTO organisation_module_access(organisation_id,module_id,enabled,enabled_at,updated_at)
                            VALUES(?,?,0,NULL,?)
                            ON CONFLICT(organisation_id,module_id) DO UPDATE SET enabled=0,updated_at=?""",
                         (user["organisation_id"],module_id,now(),now()))
            auto_enable=False

        existing=con.execute("""SELECT licence_id FROM module_licences
                                WHERE organisation_id=? AND module_id=?""",
                             (user["organisation_id"],module_id)).fetchone()
        if existing:
            con.execute("""UPDATE module_licences
                           SET licence_status=?,licence_type=?,start_date=?,expiry_date=?,
                               seats=?,auto_enable=?,notes=?,updated_at=?
                           WHERE licence_id=?""",
                        (status,licence_type,start_date,expiry_date,seats,1 if auto_enable else 0,
                         notes,now(),existing["licence_id"]))
            licence_id=existing["licence_id"]
        else:
            cur=con.execute("""INSERT INTO module_licences
                (organisation_id,module_id,licence_status,licence_type,start_date,expiry_date,seats,auto_enable,notes,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (user["organisation_id"],module_id,status,licence_type,start_date,expiry_date,seats,
                 1 if auto_enable else 0,notes,now(),now()))
            licence_id=cur.lastrowid

        if status in ("ACTIVE","TRIAL") and auto_enable:
            con.execute("""INSERT INTO organisation_module_access(organisation_id,module_id,enabled,enabled_at,updated_at)
                            VALUES(?,?,1,?,?)
                            ON CONFLICT(organisation_id,module_id) DO UPDATE SET enabled=1,enabled_at=?,updated_at=?""",
                         (user["organisation_id"],module_id,now(),now(),now(),now()))

        audit(con,user["organisation_id"],user["user_id"],"module",str(module_id),
              "LICENCE_UPDATE",None,{"status":status,"licence_type":licence_type,"auto_enable":bool(auto_enable)})
        con.commit()
        return licence_id
    finally:
        con.close()


def enable_module(user,module_id):
    # This is deliberately licensing-gated.
    _require(user,"licensing.manage")
    con=connect()
    try:
        licence=con.execute("""SELECT * FROM module_licences
                               WHERE organisation_id=? AND module_id=?""",
                            (user["organisation_id"],int(module_id))).fetchone()
        if not licence or not licence_is_valid(licence):
            raise PermissionError("A valid active/trial licence is required before this module can be enabled")
        con.execute("""INSERT INTO organisation_module_access(organisation_id,module_id,enabled,enabled_at,updated_at)
                            VALUES(?,?,1,?,?)
                            ON CONFLICT(organisation_id,module_id) DO UPDATE SET enabled=1,enabled_at=?,updated_at=?""",
                         (user["organisation_id"],module_id,now(),now(),now(),now()))
        audit(con,user["organisation_id"],user["user_id"],"module",str(module_id),"ENABLE",None,{"licence_id":licence["licence_id"]})
        con.commit()
    finally:
        con.close()


def disable_module(user,module_id):
    _require(user,"licensing.manage")
    con=connect()
    try:
        con.execute("""INSERT INTO organisation_module_access(organisation_id,module_id,enabled,enabled_at,updated_at)
                            VALUES(?,?,0,NULL,?)
                            ON CONFLICT(organisation_id,module_id) DO UPDATE SET enabled=0,updated_at=?""",
                         (user["organisation_id"],module_id,now(),now()))
        audit(con,user["organisation_id"],user["user_id"],"module",str(module_id),"DISABLE")
        con.commit()
    finally:
        con.close()


def check_module_access(user,module_id,permission_code=None):
    con=connect()
    try:
        module=con.execute("SELECT * FROM modules WHERE module_id=? AND active=1",(int(module_id),)).fetchone()
        access=con.execute("""SELECT enabled FROM organisation_module_access
                              WHERE organisation_id=? AND module_id=?""",
                           (user["organisation_id"],int(module_id))).fetchone()
        if not module or not access or not access["enabled"]:
            return False
        licence=con.execute("""SELECT * FROM module_licences
                               WHERE organisation_id=? AND module_id=?""",
                            (user["organisation_id"],int(module_id))).fetchone()
        if not licence_is_valid(licence):
            return False
        if permission_code:
            return has_permission(user["user_id"],permission_code)
        return True
    finally:
        con.close()
