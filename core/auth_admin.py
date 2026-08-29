import re
from core import connect, now, audit, hash_password, verify_password, has_permission
MIN_PASSWORD_LENGTH=8

def ensure_auth_admin_permissions():
    con=connect()
    perms=[
        ("auth.users.view","View Users","View organisation users"),
        ("auth.users.manage","Manage Users","Create, activate and deactivate users"),
        ("auth.password.reset","Reset User Passwords","Reset another user's password"),
        ("auth.password.change","Change Own Password","Change the signed-in user's password"),
    ]
    for code,name,desc in perms:
        con.execute("INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",(code,name,desc))
        p=con.execute("SELECT permission_id FROM permissions WHERE permission_code=?",(code,)).fetchone()
        core=con.execute("SELECT module_id FROM modules WHERE module_code='core'").fetchone()
        if p and core:
            con.execute("INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",(core["module_id"],p["permission_id"]))
            # Bootstrap/admin roles receive the Core authentication permissions.
            con.execute(
                """INSERT OR IGNORE INTO role_permissions(role_id,permission_id)
                   SELECT role_id,? FROM roles
                   WHERE organisation_id IS NOT NULL AND role_code='system_admin'""",
                (p["permission_id"],)
            )
    con.commit(); con.close()

def _require(user,p):
    if not has_permission(user["user_id"],p): raise PermissionError(f"Permission required: {p}")

def _validate_password(p):
    if not isinstance(p,str) or len(p)<MIN_PASSWORD_LENGTH: raise ValueError("Password must be at least 8 characters")
    if p.strip()!=p: raise ValueError("Password may not begin or end with spaces")

def _username(u):
    u=(u or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9._@+-]{3,80}",u): raise ValueError("Invalid username")
    return u

def list_users(user):
    _require(user,"auth.users.view"); con=connect()
    rows=con.execute("""SELECT u.user_id,u.username,u.display_name,u.email,u.active,
        u.password_reset_required,u.created_at,r.role_code,r.role_name
        FROM users u JOIN roles r ON r.role_id=u.role_id
        WHERE u.organisation_id=? ORDER BY u.display_name,u.username""",(user["organisation_id"],)).fetchall()
    con.close(); return [dict(r) for r in rows]

def create_user(user,data):
    _require(user,"auth.users.manage")
    username=_username(data.get("username")); display=(data.get("display_name") or "").strip()
    email=(data.get("email") or "").strip().lower() or None; password=data.get("password") or ""
    _validate_password(password)
    if not display: raise ValueError("Display name is required")
    con=connect()
    try:
        role_id=int(data.get("role_id") or 0)
        if not con.execute("SELECT role_id FROM roles WHERE role_id=? AND organisation_id=?",(role_id,user["organisation_id"])).fetchone():
            raise ValueError("Role not found")
        branch_id=data.get("branch_id")
        if branch_id and not con.execute("SELECT branch_id FROM branches WHERE branch_id=? AND organisation_id=?",(int(branch_id),user["organisation_id"])).fetchone():
            raise ValueError("Branch not found")
        if con.execute("SELECT user_id FROM users WHERE organisation_id=? AND username=?",(user["organisation_id"],username)).fetchone():
            raise ValueError("Username already exists")
        cur=con.execute("""INSERT INTO users(organisation_id,username,display_name,email,password_hash,role_id,
            branch_id,access_scope,password_reset_required,active,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(user["organisation_id"],username,display,email,hash_password(password),
            role_id,branch_id,data.get("access_scope") or "LOCATION",1,1,now()))
        uid=cur.lastrowid
        con.execute("INSERT OR IGNORE INTO user_roles(user_id,role_id,created_at) VALUES(?,?,?)",(uid,role_id,now()))
        audit(con,user["organisation_id"],user["user_id"],"user",str(uid),"CREATE",None,{"username":username,"role_id":role_id})
        con.commit(); return uid
    finally: con.close()

def change_own_password(user,current_password,new_password):
    _require(user,"auth.password.change"); _validate_password(new_password)
    con=connect()
    try:
        row=con.execute("SELECT password_hash,password_reset_required FROM users WHERE user_id=? AND active=1",(user["user_id"],)).fetchone()
        if not row: raise ValueError("User not found")
        if not row["password_reset_required"] and not verify_password(current_password or "",row["password_hash"]):
            raise ValueError("Current password is incorrect")
        con.execute("UPDATE users SET password_hash=?,password_reset_required=0 WHERE user_id=?",(hash_password(new_password),user["user_id"]))
        audit(con,user["organisation_id"],user["user_id"],"user",str(user["user_id"]),"PASSWORD_CHANGE")
        con.commit()
    finally: con.close()

def reset_user_password(user,target_user_id,new_password):
    _require(user,"auth.password.reset"); _validate_password(new_password); con=connect()
    try:
        target=con.execute("SELECT user_id,username FROM users WHERE user_id=? AND organisation_id=?",(int(target_user_id),user["organisation_id"])).fetchone()
        if not target: raise ValueError("User not found")
        con.execute("UPDATE users SET password_hash=?,password_reset_required=1 WHERE user_id=?",(hash_password(new_password),target_user_id))
        con.execute("UPDATE sessions SET active=0 WHERE user_id=?",(target_user_id,))
        audit(con,user["organisation_id"],user["user_id"],"user",str(target_user_id),"PASSWORD_RESET",None,{"username":target["username"],"forced_change":True})
        con.commit()
    finally: con.close()
