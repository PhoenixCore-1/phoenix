"""
Phoenix Inventory v0.1

Generic inventory foundation.
No customer-specific ERP, SKU master, BOM, costing, warehouse or branch rules.
"""

from core import connect, now, audit, has_permission

ITEM_TYPES = ("Stock", "Non-Stock", "Service", "Component", "Finished Good")
TRANSACTION_TYPES = ("Receipt", "Issue", "Adjustment In", "Adjustment Out", "Transfer In", "Transfer Out")
LOCATION_TYPES = ("Warehouse", "Production", "Transit", "Other")
RESERVATION_STATUSES = ("Reserved", "Released", "Consumed", "Cancelled")


def ensure_inventory_permissions():
    con = connect()
    permissions = [
        ("inventory.view", "View Inventory", "Access inventory records and balances"),
        ("inventory.manage", "Manage Inventory", "Create and maintain inventory masters"),
        ("inventory.transact", "Inventory Transactions", "Receive, issue and adjust inventory"),
        ("inventory.reserve", "Reserve Inventory", "Reserve and release available inventory"),
    ]
    for code,name,desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code,name,desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='inventory'"
    ).fetchone()
    if module:
        for code,_,_ in permissions:
            p = con.execute(
                "SELECT permission_id FROM permissions WHERE permission_code=?",
                (code,)
            ).fetchone()
            if p:
                con.execute(
                    "INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",
                    (module["module_id"],p["permission_id"])
                )
    con.commit()
    con.close()


def list_items(user, search=""):
    con = connect()
    clauses = ["i.organisation_id=?"]
    params = [user["organisation_id"]]
    if search:
        like=f"%{search}%"
        clauses.append("(i.item_code LIKE ? OR i.item_name LIKE ? OR COALESCE(i.description,'') LIKE ?)")
        params.extend([like,like,like])
    rows=con.execute(
        f"""SELECT i.* FROM inventory_items i
            WHERE {' AND '.join(clauses)}
            ORDER BY i.active DESC,i.item_code""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_locations(user):
    con=connect()
    rows=con.execute(
        """SELECT * FROM inventory_locations
           WHERE organisation_id=? ORDER BY active DESC,location_code""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def list_balances(user, item_id=None):
    con=connect()
    clauses=["b.organisation_id=?"]
    params=[user["organisation_id"]]
    if item_id:
        clauses.append("b.inventory_item_id=?")
        params.append(int(item_id))
    rows=con.execute(
        f"""SELECT b.*,i.item_code,i.item_name,i.unit_of_measure,l.location_code,l.location_name
            FROM inventory_balances b
            JOIN inventory_items i ON i.inventory_item_id=b.inventory_item_id
            JOIN inventory_locations l ON l.location_id=b.location_id
            WHERE {' AND '.join(clauses)}
            ORDER BY i.item_code,l.location_code""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_item(user,data):
    if not has_permission(user["user_id"],"inventory.manage"):
        raise PermissionError("Inventory management permission required")
    code=(data.get("item_code") or "").strip()
    name=(data.get("item_name") or "").strip()
    if not code or not name:
        raise ValueError("Item code and item name are required")
    item_type=data.get("item_type") or "Stock"
    if item_type not in ITEM_TYPES:
        raise ValueError("Invalid item type")
    uom=(data.get("unit_of_measure") or "EA").strip()
    con=connect()
    try:
        cur=con.execute(
            """INSERT INTO inventory_items(
                organisation_id,item_code,item_name,description,unit_of_measure,
                item_type,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (user["organisation_id"],code,name,
             (data.get("description") or "").strip() or None,uom,item_type,
             user["user_id"],now(),now())
        )
        item_id=cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],"inventory_item",str(item_id),
              "CREATE",None,{"item_code":code,"item_name":name})
        con.commit()
        return item_id
    finally:
        con.close()


def create_location(user,data):
    if not has_permission(user["user_id"],"inventory.manage"):
        raise PermissionError("Inventory management permission required")
    code=(data.get("location_code") or "").strip()
    name=(data.get("location_name") or "").strip()
    if not code or not name:
        raise ValueError("Location code and location name are required")
    location_type=data.get("location_type") or "Warehouse"
    if location_type not in LOCATION_TYPES:
        raise ValueError("Invalid location type")
    con=connect()
    try:
        cur=con.execute(
            """INSERT INTO inventory_locations(
                organisation_id,location_code,location_name,location_type
            ) VALUES(?,?,?,?)""",
            (user["organisation_id"],code,name,location_type)
        )
        location_id=cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],"inventory_location",str(location_id),
              "CREATE",None,{"location_code":code,"location_name":name})
        con.commit()
        return location_id
    finally:
        con.close()


def _item_location(con,org,item_id,location_id):
    item=con.execute(
        "SELECT * FROM inventory_items WHERE inventory_item_id=? AND organisation_id=?",
        (int(item_id),org)
    ).fetchone()
    loc=con.execute(
        "SELECT * FROM inventory_locations WHERE location_id=? AND organisation_id=?",
        (int(location_id),org)
    ).fetchone()
    if not item:
        raise ValueError("Inventory item not found")
    if not loc:
        raise ValueError("Inventory location not found")
    return item,loc


def _ensure_balance(con,org,item_id,location_id):
    row=con.execute(
        """SELECT * FROM inventory_balances
           WHERE inventory_item_id=? AND location_id=?""",
        (item_id,location_id)
    ).fetchone()
    if not row:
        con.execute(
            """INSERT INTO inventory_balances(
                organisation_id,inventory_item_id,location_id,
                quantity_on_hand,quantity_reserved,quantity_available,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",
            (org,item_id,location_id,0,0,0,now())
        )
        row=con.execute(
            "SELECT * FROM inventory_balances WHERE inventory_item_id=? AND location_id=?",
            (item_id,location_id)
        ).fetchone()
    return row


def transact(user,data):
    if not has_permission(user["user_id"],"inventory.transact"):
        raise PermissionError("Inventory transaction permission required")
    item_id=int(data.get("inventory_item_id") or 0)
    location_id=int(data.get("location_id") or 0)
    qty=float(data.get("quantity") or 0)
    ttype=data.get("transaction_type")
    if qty <= 0:
        raise ValueError("Quantity must be greater than zero")
    if ttype not in TRANSACTION_TYPES:
        raise ValueError("Invalid transaction type")
    con=connect()
    try:
        item,loc=_item_location(con,user["organisation_id"],item_id,location_id)
        bal=_ensure_balance(con,user["organisation_id"],item_id,location_id)
        on_hand=float(bal["quantity_on_hand"])
        if ttype in ("Issue","Adjustment Out","Transfer Out") and on_hand < qty:
            raise ValueError("Insufficient quantity on hand")
        delta=-qty if ttype in ("Issue","Adjustment Out","Transfer Out") else qty
        new_on_hand=on_hand+delta
        available=new_on_hand-float(bal["quantity_reserved"])
        if available < 0:
            raise ValueError("Transaction would reduce available inventory below zero")
        con.execute(
            """UPDATE inventory_balances
               SET quantity_on_hand=?,quantity_available=?,updated_at=?
               WHERE inventory_item_id=? AND location_id=?""",
            (new_on_hand,available,now(),item_id,location_id)
        )
        cur=con.execute(
            """INSERT INTO inventory_transactions(
                organisation_id,inventory_item_id,location_id,transaction_type,
                quantity,reference_type,reference_id,reason,user_id,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (user["organisation_id"],item_id,location_id,ttype,qty,
             data.get("reference_type"),data.get("reference_id"),data.get("reason"),
             user["user_id"],now())
        )
        audit(con,user["organisation_id"],user["user_id"],"inventory_item",str(item_id),
              "TRANSACTION",{"quantity_on_hand":on_hand},
              {"quantity_on_hand":new_on_hand,"transaction_type":ttype,"quantity":qty})
        con.commit()
        return {"transaction_id":cur.lastrowid,"quantity_on_hand":new_on_hand,"quantity_available":available}
    finally:
        con.close()


def reserve(user,data):
    if not has_permission(user["user_id"],"inventory.reserve"):
        raise PermissionError("Inventory reservation permission required")
    item_id=int(data.get("inventory_item_id") or 0)
    location_id=int(data.get("location_id") or 0)
    qty=float(data.get("quantity") or 0)
    reference_type=(data.get("reference_type") or "").strip()
    reference_id=int(data.get("reference_id") or 0)
    if qty<=0 or not reference_type or not reference_id:
        raise ValueError("Item, location, quantity and reference are required")
    con=connect()
    try:
        _item_location(con,user["organisation_id"],item_id,location_id)
        bal=_ensure_balance(con,user["organisation_id"],item_id,location_id)
        available=float(bal["quantity_available"])
        if available < qty:
            raise ValueError("Insufficient available inventory")
        cur=con.execute(
            """INSERT INTO inventory_reservations(
                organisation_id,inventory_item_id,location_id,reference_type,reference_id,
                quantity,status,created_by,created_at
            ) VALUES(?,?,?,?,?,?,?,?,?)""",
            (user["organisation_id"],item_id,location_id,reference_type,reference_id,
             qty,"Reserved",user["user_id"],now())
        )
        con.execute(
            """UPDATE inventory_balances
               SET quantity_reserved=quantity_reserved+?,
                   quantity_available=quantity_available-?,updated_at=?
               WHERE inventory_item_id=? AND location_id=?""",
            (qty,qty,now(),item_id,location_id)
        )
        audit(con,user["organisation_id"],user["user_id"],"inventory_item",str(item_id),
              "RESERVE",{"quantity_available":available},{"quantity_available":available-qty},
              f"{reference_type} {reference_id}")
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def release_reservation(user,reservation_id):
    if not has_permission(user["user_id"],"inventory.reserve"):
        raise PermissionError("Inventory reservation permission required")
    con=connect()
    try:
        r=con.execute(
            """SELECT * FROM inventory_reservations
               WHERE reservation_id=? AND organisation_id=?""",
            (reservation_id,user["organisation_id"])
        ).fetchone()
        if not r:
            raise ValueError("Reservation not found")
        if r["status"]!="Reserved":
            raise ValueError("Reservation is not active")
        con.execute(
            """UPDATE inventory_reservations
               SET status='Released',released_at=? WHERE reservation_id=?""",
            (now(),reservation_id)
        )
        con.execute(
            """UPDATE inventory_balances
               SET quantity_reserved=quantity_reserved-?,
                   quantity_available=quantity_available+?,updated_at=?
               WHERE inventory_item_id=? AND location_id=?""",
            (r["quantity"],r["quantity"],now(),r["inventory_item_id"],r["location_id"])
        )
        audit(con,user["organisation_id"],user["user_id"],"inventory_item",str(r["inventory_item_id"]),
              "RELEASE_RESERVATION",None,{"reservation_id":reservation_id})
        con.commit()
    finally:
        con.close()


def dashboard(user):
    con=connect()
    org=user["organisation_id"]
    data={
        "items":con.execute("SELECT COUNT(*) c FROM inventory_items WHERE organisation_id=? AND active=1",(org,)).fetchone()["c"],
        "locations":con.execute("SELECT COUNT(*) c FROM inventory_locations WHERE organisation_id=? AND active=1",(org,)).fetchone()["c"],
        "balances":con.execute("SELECT COUNT(*) c FROM inventory_balances WHERE organisation_id=?",(org,)).fetchone()["c"],
        "units_on_hand":con.execute("SELECT COALESCE(SUM(quantity_on_hand),0) q FROM inventory_balances WHERE organisation_id=?",(org,)).fetchone()["q"],
        "units_reserved":con.execute("SELECT COALESCE(SUM(quantity_reserved),0) q FROM inventory_balances WHERE organisation_id=?",(org,)).fetchone()["q"],
    }
    con.close()
    return data
