"""
Phoenix Notifications & Communications v0.1

Generic Core communication service.

Channels are represented as provider-neutral records. v0.1 supports:
- in-app notification creation and reading
- email queueing
- notification templates
- user preferences
- delivery status/history
- notification events
- Core permissions

External email/SMS/push providers are adapters, not embedded customer logic.
"""

import json
from core import connect, now, audit, has_permission

CHANNELS = ("in_app", "email")
SEVERITIES = ("info", "success", "warning", "error")
DELIVERY_STATUSES = ("queued", "sent", "failed", "cancelled")

def ensure_notifications_permissions():
    con = connect()
    permissions = [
        ("notifications.view", "View Notifications", "View notification history"),
        ("notifications.manage", "Manage Notifications", "Create and manage notifications"),
        ("notifications.templates", "Manage Notification Templates", "Create and manage notification templates"),
        ("notifications.preferences", "Manage Notification Preferences", "Manage user notification preferences"),
        ("notifications.deliveries", "Manage Notification Deliveries", "View and manage delivery records"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code,name,desc)
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
                (core["module_id"],p["permission_id"])
            )
    con.commit()
    con.close()

def _require(user, permission):
    if not has_permission(user["user_id"], permission):
        raise PermissionError(f"Permission required: {permission}")

def _pref(con, org_id, user_id, code):
    return con.execute(
        """SELECT * FROM notification_preferences
           WHERE organisation_id=? AND user_id=? AND notification_code=?""",
        (org_id,user_id,code)
    ).fetchone()

def create_template(user, data):
    _require(user, "notifications.templates")
    code = (data.get("template_code") or "").strip()
    name = (data.get("template_name") or "").strip()
    channel = data.get("channel") or "email"
    body = data.get("body_template") or ""
    if not code or not name or not body:
        raise ValueError("Template code, name and body are required")
    if channel not in CHANNELS:
        raise ValueError("Unsupported channel")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO notification_templates(
                organisation_id,template_code,template_name,channel,
                subject_template,body_template,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],code,name,channel,
                data.get("subject_template"),body,now(),now()
            )
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()

def list_templates(user):
    _require(user, "notifications.view")
    con = connect()
    rows = con.execute(
        """SELECT * FROM notification_templates
           WHERE organisation_id=? OR organisation_id IS NULL
           ORDER BY template_code,channel""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def set_preference(user, data):
    _require(user, "notifications.preferences")
    target_user = int(data.get("user_id") or user["user_id"])
    code = (data.get("notification_code") or "").strip()
    if not code:
        raise ValueError("Notification code is required")

    con = connect()
    try:
        valid = con.execute(
            "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
            (target_user,user["organisation_id"])
        ).fetchone()
        if not valid:
            raise ValueError("User not found")
        con.execute(
            """INSERT INTO notification_preferences(
                organisation_id,user_id,notification_code,
                in_app_enabled,email_enabled,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(organisation_id,user_id,notification_code)
            DO UPDATE SET in_app_enabled=excluded.in_app_enabled,
                          email_enabled=excluded.email_enabled,
                          updated_at=excluded.updated_at""",
            (
                user["organisation_id"],target_user,code,
                1 if data.get("in_app_enabled",True) else 0,
                1 if data.get("email_enabled",True) else 0,
                now(),now()
            )
        )
        con.commit()
    finally:
        con.close()

def list_preferences(user, target_user_id=None):
    _require(user, "notifications.view")
    target = int(target_user_id or user["user_id"])
    con = connect()
    valid = con.execute(
        "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
        (target,user["organisation_id"])
    ).fetchone()
    if not valid:
        con.close()
        raise ValueError("User not found")
    rows = con.execute(
        """SELECT * FROM notification_preferences
           WHERE organisation_id=? AND user_id=?
           ORDER BY notification_code""",
        (user["organisation_id"],target)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def create_notification(user, data):
    _require(user, "notifications.manage")
    recipient = int(data.get("recipient_user_id") or 0)
    code = (data.get("notification_code") or "system.general").strip()
    title = (data.get("title") or "").strip()
    message = (data.get("message") or "").strip()
    severity = data.get("severity") or "info"
    if not recipient or not title or not message:
        raise ValueError("Recipient, title and message are required")
    if severity not in SEVERITIES:
        raise ValueError("Invalid severity")

    con = connect()
    try:
        valid = con.execute(
            "SELECT user_id FROM users WHERE user_id=? AND organisation_id=?",
            (recipient,user["organisation_id"])
        ).fetchone()
        if not valid:
            raise ValueError("Recipient not found")

        cur = con.execute(
            """INSERT INTO notifications(
                organisation_id,recipient_user_id,notification_code,
                title,message,severity,source_module,
                source_entity_type,source_entity_id,action_url,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],recipient,code,title,message,severity,
                data.get("source_module"),data.get("source_entity_type"),
                data.get("source_entity_id"),data.get("action_url"),now()
            )
        )
        nid = cur.lastrowid

        pref = _pref(con,user["organisation_id"],recipient,code)
        in_app = True if pref is None else bool(pref["in_app_enabled"])
        email = True if pref is None else bool(pref["email_enabled"])

        if in_app:
            con.execute(
                """INSERT INTO notification_deliveries(
                    organisation_id,notification_id,channel,status,queued_at
                ) VALUES(?,?,?,?,?)""",
                (user["organisation_id"],nid,"in_app","queued",now())
            )
        if email:
            con.execute(
                """INSERT INTO notification_deliveries(
                    organisation_id,notification_id,channel,status,provider_code,queued_at
                ) VALUES(?,?,?,?,?,?)""",
                (user["organisation_id"],nid,"email","queued","email.default",now())
            )

        con.execute(
            """INSERT INTO notification_events(
                organisation_id,notification_id,event_type,details_json,created_at
            ) VALUES(?,?,?,?,?)""",
            (
                user["organisation_id"],nid,"created",
                json.dumps({"code":code,"recipient_user_id":recipient}),now()
            )
        )
        audit(
            con,user["organisation_id"],user["user_id"],
            "notification",str(nid),"CREATE",None,
            {"recipient_user_id":recipient,"notification_code":code}
        )
        con.commit()
        return nid
    finally:
        con.close()

def list_notifications(user, unread_only=False, limit=100):
    _require(user, "notifications.view")
    con = connect()
    sql = """SELECT * FROM notifications
             WHERE organisation_id=? AND recipient_user_id=?"""
    params = [user["organisation_id"],user["user_id"]]
    if unread_only:
        sql += " AND read_at IS NULL"
    sql += " ORDER BY notification_id DESC LIMIT ?"
    params.append(int(limit))
    rows = con.execute(sql,params).fetchall()
    con.close()
    return [dict(r) for r in rows]

def mark_read(user, notification_id):
    _require(user, "notifications.view")
    con = connect()
    try:
        row = con.execute(
            """SELECT notification_id FROM notifications
               WHERE notification_id=? AND organisation_id=? AND recipient_user_id=?""",
            (notification_id,user["organisation_id"],user["user_id"])
        ).fetchone()
        if not row:
            raise ValueError("Notification not found")
        con.execute(
            "UPDATE notifications SET read_at=? WHERE notification_id=?",
            (now(),notification_id)
        )
        con.execute(
            """INSERT INTO notification_events(
                organisation_id,notification_id,event_type,channel,created_at
            ) VALUES(?,?,?,?,?)""",
            (user["organisation_id"],notification_id,"read","in_app",now())
        )
        con.commit()
    finally:
        con.close()

def list_deliveries(user, notification_id=None, limit=200):
    _require(user, "notifications.deliveries")
    con = connect()
    if notification_id:
        rows = con.execute(
            """SELECT * FROM notification_deliveries
               WHERE organisation_id=? AND notification_id=?
               ORDER BY notification_delivery_id DESC""",
            (user["organisation_id"],int(notification_id))
        ).fetchall()
    else:
        rows = con.execute(
            """SELECT d.* FROM notification_deliveries d
               WHERE d.organisation_id=?
               ORDER BY d.notification_delivery_id DESC LIMIT ?""",
            (user["organisation_id"],int(limit))
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def update_delivery_status(user, delivery_id, status, error=None, provider_message_id=None):
    _require(user, "notifications.deliveries")
    if status not in DELIVERY_STATUSES:
        raise ValueError("Invalid delivery status")
    con = connect()
    try:
        row = con.execute(
            """SELECT * FROM notification_deliveries
               WHERE notification_delivery_id=? AND organisation_id=?""",
            (delivery_id,user["organisation_id"])
        ).fetchone()
        if not row:
            raise ValueError("Delivery not found")

        sent_at = now() if status == "sent" else None
        failed_at = now() if status == "failed" else None
        con.execute(
            """UPDATE notification_deliveries
               SET status=?,attempts=attempts+1,last_error=?,
                   provider_message_id=?,sent_at=COALESCE(?,sent_at),
                   failed_at=COALESCE(?,failed_at)
               WHERE notification_delivery_id=?""",
            (status,error,provider_message_id,sent_at,failed_at,delivery_id)
        )
        con.execute(
            """INSERT INTO notification_events(
                organisation_id,notification_id,event_type,channel,details_json,created_at
            ) VALUES(?,?,?,?,?,?)""",
            (
                user["organisation_id"],row["notification_id"],
                "delivery_"+status,row["channel"],
                json.dumps({"error":error,"provider_message_id":provider_message_id}),now()
            )
        )
        con.commit()
    finally:
        con.close()

def dashboard(user):
    _require(user, "notifications.view")
    con = connect()
    org = user["organisation_id"]
    result = {
        "total": con.execute(
            "SELECT COUNT(*) c FROM notifications WHERE organisation_id=?",
            (org,)
        ).fetchone()["c"],
        "unread_for_user": con.execute(
            """SELECT COUNT(*) c FROM notifications
               WHERE organisation_id=? AND recipient_user_id=? AND read_at IS NULL""",
            (org,user["user_id"])
        ).fetchone()["c"],
        "queued_deliveries": con.execute(
            "SELECT COUNT(*) c FROM notification_deliveries WHERE organisation_id=? AND status='queued'",
            (org,)
        ).fetchone()["c"],
        "sent_deliveries": con.execute(
            "SELECT COUNT(*) c FROM notification_deliveries WHERE organisation_id=? AND status='sent'",
            (org,)
        ).fetchone()["c"],
        "failed_deliveries": con.execute(
            "SELECT COUNT(*) c FROM notification_deliveries WHERE organisation_id=? AND status='failed'",
            (org,)
        ).fetchone()["c"],
        "templates": con.execute(
            """SELECT COUNT(*) c FROM notification_templates
               WHERE organisation_id=? OR organisation_id IS NULL""",
            (org,)
        ).fetchone()["c"],
    }
    con.close()
    return result
