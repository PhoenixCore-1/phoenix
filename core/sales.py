"""
Phoenix Sales v0.1

Generic quoting/sales foundation.
No customer-specific price lists, products, ERP rules or Upat business logic.
"""

from decimal import Decimal, ROUND_HALF_UP
from core import connect, now, audit, has_permission

QUOTE_STATUSES = ("Draft", "Sent", "Accepted", "Rejected", "Expired", "Cancelled")
ALLOWED_TRANSITIONS = {
    "Draft": ("Sent", "Cancelled"),
    "Sent": ("Accepted", "Rejected", "Expired", "Cancelled"),
    "Accepted": (),
    "Rejected": (),
    "Expired": (),
    "Cancelled": (),
}

def money(value):
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def ensure_sales_permissions():
    con = connect()
    permissions = [
        ("sales.view", "View Sales", "Access quotes and sales records"),
        ("sales.manage", "Manage Sales", "Create and update quotes"),
        ("sales.approve", "Approve Sales", "Accept or reject quotes"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='sales'"
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

def _account_exists(con, organisation_id, account_id):
    if account_id in (None, "", 0, "0"):
        return None
    row = con.execute(
        "SELECT account_id FROM crm_accounts WHERE account_id=? AND organisation_id=?",
        (int(account_id), organisation_id)
    ).fetchone()
    if not row:
        raise ValueError("CRM account not found in this organisation")
    return int(account_id)

def _project_exists(con, organisation_id, project_id):
    if project_id in (None, "", 0, "0"):
        return None
    row = con.execute(
        "SELECT project_id FROM projects WHERE project_id=? AND organisation_id=?",
        (int(project_id), organisation_id)
    ).fetchone()
    if not row:
        raise ValueError("Project not found in this organisation")
    return int(project_id)

def next_quote_number(organisation_id):
    con = connect()
    count = con.execute(
        "SELECT COUNT(*) c FROM sales_quotes WHERE organisation_id=?",
        (organisation_id,)
    ).fetchone()["c"] + 1
    con.close()
    return f"Q-{count:06d}"

def _recalculate(con, quote_id):
    rows = con.execute(
        """SELECT quantity,unit_price,discount_percent,tax_percent
           FROM sales_quote_lines WHERE quote_id=? ORDER BY line_no""",
        (quote_id,)
    ).fetchall()
    subtotal = Decimal("0")
    discount = Decimal("0")
    tax = Decimal("0")
    total = Decimal("0")
    for r in rows:
        base = money(Decimal(str(r["quantity"])) * Decimal(str(r["unit_price"])))
        disc = money(base * Decimal(str(r["discount_percent"])) / Decimal("100"))
        taxable = base - disc
        line_tax = money(taxable * Decimal(str(r["tax_percent"])) / Decimal("100"))
        line_total = taxable + line_tax
        subtotal += base
        discount += disc
        tax += line_tax
        total += line_total
    con.execute(
        """UPDATE sales_quotes
           SET subtotal=?,discount_total=?,tax_total=?,total=?,updated_at=?
           WHERE quote_id=?""",
        (float(subtotal),float(discount),float(tax),float(total),now(),quote_id)
    )
    return {
        "subtotal": float(subtotal),
        "discount_total": float(discount),
        "tax_total": float(tax),
        "total": float(total),
    }

def list_quotes(user, search=""):
    con = connect()
    clauses = ["q.organisation_id=?"]
    params = [user["organisation_id"]]
    if search:
        like = f"%{search}%"
        clauses.append(
            "(q.quote_number LIKE ? OR COALESCE(a.account_name,'') LIKE ? OR COALESCE(p.project_name,'') LIKE ?)"
        )
        params.extend([like,like,like])
    rows = con.execute(
        f"""SELECT q.*,a.account_name,p.project_name,u.display_name AS owner_name
            FROM sales_quotes q
            LEFT JOIN crm_accounts a ON a.account_id=q.account_id
            LEFT JOIN projects p ON p.project_id=q.project_id
            LEFT JOIN users u ON u.user_id=q.owner_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY q.quote_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]

def get_quote(user, quote_id):
    con = connect()
    quote = con.execute(
        """SELECT q.*,a.account_name,p.project_name,u.display_name AS owner_name
           FROM sales_quotes q
           LEFT JOIN crm_accounts a ON a.account_id=q.account_id
           LEFT JOIN projects p ON p.project_id=q.project_id
           LEFT JOIN users u ON u.user_id=q.owner_user_id
           WHERE q.quote_id=? AND q.organisation_id=?""",
        (quote_id,user["organisation_id"])
    ).fetchone()
    if not quote:
        con.close()
        raise ValueError("Quote not found")
    lines = con.execute(
        "SELECT * FROM sales_quote_lines WHERE quote_id=? ORDER BY line_no",
        (quote_id,)
    ).fetchall()
    history = con.execute(
        """SELECT h.*,u.display_name
           FROM sales_quote_status_history h
           JOIN users u ON u.user_id=h.user_id
           WHERE h.quote_id=? ORDER BY h.history_id""",
        (quote_id,)
    ).fetchall()
    con.close()
    result = dict(quote)
    result["lines"] = [dict(x) for x in lines]
    result["history"] = [dict(x) for x in history]
    return result

def create_quote(user, data):
    if not has_permission(user["user_id"], "sales.manage"):
        raise PermissionError("Sales management permission required")
    con = connect()
    try:
        account_id = _account_exists(con,user["organisation_id"],data.get("account_id"))
        project_id = _project_exists(con,user["organisation_id"],data.get("project_id"))
        quote_number = (data.get("quote_number") or "").strip() or next_quote_number(user["organisation_id"])
        quote_date = data.get("quote_date") or now()[:10]
        valid_until = data.get("valid_until") or None
        currency = (data.get("currency") or "ZAR").strip().upper()
        cur = con.execute(
            """INSERT INTO sales_quotes(
                organisation_id,quote_number,account_id,project_id,quote_date,
                valid_until,status,currency,owner_user_id,notes,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],quote_number,account_id,project_id,
                quote_date,valid_until,"Draft",currency,
                data.get("owner_user_id") or user["user_id"],
                (data.get("notes") or "").strip() or None,
                user["user_id"],now(),now()
            )
        )
        quote_id = cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],
              "quote",str(quote_id),"CREATE",None,{"quote_number":quote_number})
        con.commit()
        return quote_id
    finally:
        con.close()

def add_line(user, quote_id, data):
    if not has_permission(user["user_id"], "sales.manage"):
        raise PermissionError("Sales management permission required")
    con = connect()
    quote = con.execute(
        "SELECT * FROM sales_quotes WHERE quote_id=? AND organisation_id=?",
        (quote_id,user["organisation_id"])
    ).fetchone()
    if not quote:
        con.close()
        raise ValueError("Quote not found")
    if quote["status"] != "Draft":
        con.close()
        raise ValueError("Only Draft quotes can be edited")
    desc = (data.get("description") or "").strip()
    if not desc:
        con.close()
        raise ValueError("Line description is required")
    qty = Decimal(str(data.get("quantity",1)))
    price = Decimal(str(data.get("unit_price",0)))
    disc = Decimal(str(data.get("discount_percent",0)))
    tax = Decimal(str(data.get("tax_percent",0)))
    if qty <= 0 or price < 0 or disc < 0 or disc > 100 or tax < 0:
        con.close()
        raise ValueError("Invalid line values")
    line_no = con.execute(
        "SELECT COALESCE(MAX(line_no),0)+1 n FROM sales_quote_lines WHERE quote_id=?",
        (quote_id,)
    ).fetchone()["n"]
    base = money(qty*price)
    discount = money(base*disc/Decimal("100"))
    line_tax = money((base-discount)*tax/Decimal("100"))
    total = base-discount+line_tax
    cur = con.execute(
        """INSERT INTO sales_quote_lines(
            quote_id,line_no,description,quantity,unit_price,discount_percent,tax_percent,
            line_subtotal,line_discount,line_tax,line_total
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (quote_id,line_no,desc,float(qty),float(price),float(disc),float(tax),
         float(base),float(discount),float(line_tax),float(total))
    )
    totals = _recalculate(con,quote_id)
    audit(con,user["organisation_id"],user["user_id"],
          "quote",str(quote_id),"ADD_LINE",None,{"description":desc,"line_no":line_no})
    con.commit()
    con.close()
    return {"quote_line_id":cur.lastrowid,**totals}

def change_status(user, quote_id, new_status, notes=None):
    if new_status not in QUOTE_STATUSES:
        raise ValueError("Invalid quote status")
    if new_status in ("Accepted","Rejected"):
        if not has_permission(user["user_id"], "sales.approve"):
            raise PermissionError("Sales approval permission required")
    elif not has_permission(user["user_id"], "sales.manage"):
        raise PermissionError("Sales management permission required")
    con = connect()
    quote = con.execute(
        "SELECT * FROM sales_quotes WHERE quote_id=? AND organisation_id=?",
        (quote_id,user["organisation_id"])
    ).fetchone()
    if not quote:
        con.close()
        raise ValueError("Quote not found")
    if new_status not in ALLOWED_TRANSITIONS.get(quote["status"],()):
        con.close()
        raise ValueError(f"Cannot move quote from {quote['status']} to {new_status}")
    con.execute(
        "UPDATE sales_quotes SET status=?,updated_at=? WHERE quote_id=?",
        (new_status,now(),quote_id)
    )
    con.execute(
        """INSERT INTO sales_quote_status_history(
            quote_id,from_status,to_status,user_id,notes,created_at
        ) VALUES(?,?,?,?,?,?)""",
        (quote_id,quote["status"],new_status,user["user_id"],notes,now())
    )
    audit(con,user["organisation_id"],user["user_id"],
          "quote",str(quote_id),"STATUS_CHANGE",
          {"status":quote["status"]},{"status":new_status},notes)
    con.commit()
    con.close()

def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    data = {
        "quotes": con.execute("SELECT COUNT(*) c FROM sales_quotes WHERE organisation_id=?",(org,)).fetchone()["c"],
        "draft": con.execute("SELECT COUNT(*) c FROM sales_quotes WHERE organisation_id=? AND status='Draft'",(org,)).fetchone()["c"],
        "sent": con.execute("SELECT COUNT(*) c FROM sales_quotes WHERE organisation_id=? AND status='Sent'",(org,)).fetchone()["c"],
        "accepted": con.execute("SELECT COUNT(*) c FROM sales_quotes WHERE organisation_id=? AND status='Accepted'",(org,)).fetchone()["c"],
        "pipeline_value": con.execute(
            "SELECT COALESCE(SUM(total),0) v FROM sales_quotes WHERE organisation_id=? AND status IN ('Draft','Sent')",
            (org,)
        ).fetchone()["v"],
        "accepted_value": con.execute(
            "SELECT COALESCE(SUM(total),0) v FROM sales_quotes WHERE organisation_id=? AND status='Accepted'",
            (org,)
        ).fetchone()["v"],
    }
    con.close()
    return data
