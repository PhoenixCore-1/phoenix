"""
Phoenix Procurement v0.1

Generic supplier and purchasing foundation.
No customer-specific supplier data, ERP integration, buying rules or costing.
"""

from decimal import Decimal, ROUND_HALF_UP
from core import connect, now, audit, has_permission
from inventory import transact

PO_STATUSES = ("Draft","Issued","Partially Received","Received","Cancelled")
ALLOWED_TRANSITIONS = {
    "Draft": ("Issued","Cancelled"),
    "Issued": ("Partially Received","Received","Cancelled"),
    "Partially Received": ("Received","Cancelled"),
    "Received": (),
    "Cancelled": (),
}

def money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)

def ensure_procurement_permissions():
    con=connect()
    permissions=[
        ("procurement.view","View Procurement","Access suppliers and purchase orders"),
        ("procurement.manage","Manage Procurement","Create and maintain suppliers and purchase orders"),
        ("procurement.issue","Issue Purchase Orders","Issue purchase orders to suppliers"),
        ("procurement.receive","Receive Purchases","Record goods received against purchase orders"),
    ]
    for code,name,desc in permissions:
        con.execute("INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",(code,name,desc))
    module=con.execute("SELECT module_id FROM modules WHERE module_code='procurement'").fetchone()
    if module:
        for code,_,_ in permissions:
            p=con.execute("SELECT permission_id FROM permissions WHERE permission_code=?",(code,)).fetchone()
            if p:
                con.execute("INSERT OR IGNORE INTO module_permissions(module_id,permission_id) VALUES(?,?)",(module["module_id"],p["permission_id"]))
    con.commit();con.close()

def list_suppliers(user,search=""):
    con=connect()
    clauses=["s.organisation_id=?"];params=[user["organisation_id"]]
    if search:
        like=f"%{search}%";clauses.append("(s.supplier_code LIKE ? OR s.supplier_name LIKE ?)")
        params += [like,like]
    rows=con.execute(f"SELECT * FROM suppliers s WHERE {' AND '.join(clauses)} ORDER BY s.active DESC,s.supplier_name",tuple(params)).fetchall()
    con.close();return [dict(r) for r in rows]

def list_purchase_orders(user,search=""):
    con=connect();clauses=["p.organisation_id=?"];params=[user["organisation_id"]]
    if search:
        like=f"%{search}%";clauses.append("(p.po_number LIKE ? OR s.supplier_name LIKE ?)")
        params += [like,like]
    rows=con.execute(f"""SELECT p.*,s.supplier_name,pr.project_name
                         FROM purchase_orders p
                         JOIN suppliers s ON s.supplier_id=p.supplier_id
                         LEFT JOIN projects pr ON pr.project_id=p.project_id
                         WHERE {' AND '.join(clauses)}
                         ORDER BY p.purchase_order_id DESC""",tuple(params)).fetchall()
    con.close();return [dict(r) for r in rows]

def get_purchase_order(user,po_id):
    con=connect()
    po=con.execute("""SELECT p.*,s.supplier_name,pr.project_name
                      FROM purchase_orders p JOIN suppliers s ON s.supplier_id=p.supplier_id
                      LEFT JOIN projects pr ON pr.project_id=p.project_id
                      WHERE p.purchase_order_id=? AND p.organisation_id=?""",(po_id,user["organisation_id"])).fetchone()
    if not po: con.close();raise ValueError("Purchase order not found")
    lines=con.execute("""SELECT l.*,i.item_code,i.item_name,i.unit_of_measure
                         FROM purchase_order_lines l JOIN inventory_items i ON i.inventory_item_id=l.inventory_item_id
                         WHERE l.purchase_order_id=? ORDER BY l.line_no""",(po_id,)).fetchall()
    receipts=con.execute("""SELECT r.*,l.line_no,i.item_code,i.item_name,loc.location_code,u.display_name
                            FROM purchase_receipts r
                            JOIN purchase_order_lines l ON l.purchase_order_line_id=r.purchase_order_line_id
                            JOIN inventory_items i ON i.inventory_item_id=l.inventory_item_id
                            JOIN inventory_locations loc ON loc.location_id=r.location_id
                            JOIN users u ON u.user_id=r.received_by
                            WHERE r.purchase_order_id=? ORDER BY r.purchase_receipt_id DESC""",(po_id,)).fetchall()
    con.close()
    d=dict(po);d["lines"]=[dict(x) for x in lines];d["receipts"]=[dict(x) for x in receipts];return d

def _supplier_ok(con,org,supplier_id):
    r=con.execute("SELECT supplier_id FROM suppliers WHERE supplier_id=? AND organisation_id=? AND active=1",(int(supplier_id),org)).fetchone()
    if not r: raise ValueError("Active supplier not found")
    return int(supplier_id)

def _project_ok(con,org,project_id):
    if project_id in (None,"",0,"0"): return None
    r=con.execute("SELECT project_id FROM projects WHERE project_id=? AND organisation_id=?",(int(project_id),org)).fetchone()
    if not r: raise ValueError("Project not found")
    return int(project_id)

def _item_ok(con,org,item_id):
    r=con.execute("SELECT inventory_item_id FROM inventory_items WHERE inventory_item_id=? AND organisation_id=? AND active=1",(int(item_id),org)).fetchone()
    if not r: raise ValueError("Active inventory item not found")
    return int(item_id)

def next_po_number(org):
    con=connect();n=con.execute("SELECT COUNT(*) c FROM purchase_orders WHERE organisation_id=?",(org,)).fetchone()["c"]+1;con.close()
    return f"PO-{n:06d}"

def create_supplier(user,data):
    if not has_permission(user["user_id"],"procurement.manage"): raise PermissionError("Procurement management permission required")
    code=(data.get("supplier_code") or "").strip();name=(data.get("supplier_name") or "").strip()
    if not code or not name: raise ValueError("Supplier code and supplier name are required")
    con=connect()
    try:
        cur=con.execute("""INSERT INTO suppliers(
            organisation_id,supplier_code,supplier_name,contact_name,email,phone,currency,payment_terms,created_by,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(user["organisation_id"],code,name,data.get("contact_name"),data.get("email"),data.get("phone"),data.get("currency") or "ZAR",data.get("payment_terms"),user["user_id"],now(),now()))
        sid=cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],"supplier",str(sid),"CREATE",None,{"supplier_code":code,"supplier_name":name})
        con.commit();return sid
    finally: con.close()

def create_purchase_order(user,data):
    if not has_permission(user["user_id"],"procurement.manage"): raise PermissionError("Procurement management permission required")
    con=connect()
    try:
        sid=_supplier_ok(con,user["organisation_id"],data.get("supplier_id"))
        pid=_project_ok(con,user["organisation_id"],data.get("project_id"))
        po_number=(data.get("po_number") or "").strip() or next_po_number(user["organisation_id"])
        cur=con.execute("""INSERT INTO purchase_orders(
            organisation_id,po_number,supplier_id,project_id,status,order_date,required_date,currency,notes,created_by,created_at,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",(user["organisation_id"],po_number,sid,pid,"Draft",data.get("order_date") or now()[:10],data.get("required_date"),data.get("currency") or "ZAR",data.get("notes"),user["user_id"],now(),now()))
        poid=cur.lastrowid
        audit(con,user["organisation_id"],user["user_id"],"purchase_order",str(poid),"CREATE",None,{"po_number":po_number})
        con.commit();return poid
    finally: con.close()

def add_line(user,po_id,data):
    if not has_permission(user["user_id"],"procurement.manage"): raise PermissionError("Procurement management permission required")
    con=connect()
    try:
        po=con.execute("SELECT * FROM purchase_orders WHERE purchase_order_id=? AND organisation_id=?",(po_id,user["organisation_id"])).fetchone()
        if not po: raise ValueError("Purchase order not found")
        if po["status"]!="Draft": raise ValueError("Only Draft purchase orders can be edited")
        item_id=_item_ok(con,user["organisation_id"],data.get("inventory_item_id"))
        qty=Decimal(str(data.get("quantity_ordered") or 0));price=Decimal(str(data.get("unit_price") or 0));tax=Decimal(str(data.get("tax_percent") or 0))
        if qty<=0 or price<0 or tax<0: raise ValueError("Invalid line values")
        line_no=con.execute("SELECT COALESCE(MAX(line_no),0)+1 n FROM purchase_order_lines WHERE purchase_order_id=?",(po_id,)).fetchone()["n"]
        subtotal=money(qty*price);taxval=money(subtotal*tax/Decimal("100"));total=subtotal+taxval
        cur=con.execute("""INSERT INTO purchase_order_lines(
            purchase_order_id,line_no,inventory_item_id,description,quantity_ordered,unit_price,tax_percent,
            line_subtotal,line_tax,line_total
        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",(po_id,line_no,item_id,data.get("description"),float(qty),float(price),float(tax),float(subtotal),float(taxval),float(total)))
        totals=recalculate(con,po_id)
        audit(con,user["organisation_id"],user["user_id"],"purchase_order",str(po_id),"ADD_LINE",None,{"line_no":line_no,"inventory_item_id":item_id})
        con.commit();return {"purchase_order_line_id":cur.lastrowid,**totals}
    finally: con.close()

def recalculate(con,po_id):
    rows=con.execute("SELECT quantity_ordered,unit_price,tax_percent FROM purchase_order_lines WHERE purchase_order_id=?",(po_id,)).fetchall()
    sub=Decimal("0");tax=Decimal("0")
    for r in rows:
        line=money(Decimal(str(r["quantity_ordered"]))*Decimal(str(r["unit_price"])))
        sub += line;tax += money(line*Decimal(str(r["tax_percent"]))/Decimal("100"))
    total=sub+tax
    con.execute("UPDATE purchase_orders SET subtotal=?,tax_total=?,total=?,updated_at=? WHERE purchase_order_id=?",(float(sub),float(tax),float(total),now(),po_id))
    return {"subtotal":float(sub),"tax_total":float(tax),"total":float(total)}

def change_status(user,po_id,new_status):
    if new_status not in PO_STATUSES: raise ValueError("Invalid purchase order status")
    if new_status=="Issued":
        if not has_permission(user["user_id"],"procurement.issue"): raise PermissionError("Purchase order issue permission required")
    else:
        if not has_permission(user["user_id"],"procurement.manage"): raise PermissionError("Procurement management permission required")
    con=connect()
    try:
        po=con.execute("SELECT * FROM purchase_orders WHERE purchase_order_id=? AND organisation_id=?",(po_id,user["organisation_id"])).fetchone()
        if not po: raise ValueError("Purchase order not found")
        if new_status not in ALLOWED_TRANSITIONS.get(po["status"],()): raise ValueError(f"Cannot move PO from {po['status']} to {new_status}")
        con.execute("UPDATE purchase_orders SET status=?,updated_at=? WHERE purchase_order_id=?",(new_status,now(),po_id))
        audit(con,user["organisation_id"],user["user_id"],"purchase_order",str(po_id),"STATUS_CHANGE",{"status":po["status"]},{"status":new_status})
        con.commit()
    finally: con.close()

def receive_line(user,po_id,line_id,location_id,qty,notes=""):
    if not has_permission(user["user_id"],"procurement.receive"): raise PermissionError("Purchase receiving permission required")
    qty=float(qty or 0)
    if qty<=0: raise ValueError("Receipt quantity must be greater than zero")
    con=connect()
    try:
        po=con.execute("SELECT * FROM purchase_orders WHERE purchase_order_id=? AND organisation_id=?",(po_id,user["organisation_id"])).fetchone()
        if not po: raise ValueError("Purchase order not found")
        if po["status"] not in ("Issued","Partially Received"): raise ValueError("PO is not open for receiving")
        line=con.execute("SELECT * FROM purchase_order_lines WHERE purchase_order_line_id=? AND purchase_order_id=?",(line_id,po_id)).fetchone()
        if not line: raise ValueError("Purchase order line not found")
        remaining=float(line["quantity_ordered"])-float(line["quantity_received"])
        if qty>remaining: raise ValueError(f"Receipt exceeds remaining quantity ({remaining})")
        loc=con.execute("SELECT * FROM inventory_locations WHERE location_id=? AND organisation_id=? AND active=1",(int(location_id),user["organisation_id"])).fetchone()
        if not loc: raise ValueError("Active inventory location not found")
        con.execute("UPDATE purchase_order_lines SET quantity_received=quantity_received+? WHERE purchase_order_line_id=?",(qty,line_id))
        cur=con.execute("""INSERT INTO purchase_receipts(
            organisation_id,purchase_order_id,purchase_order_line_id,location_id,quantity_received,received_by,received_at,notes
        ) VALUES(?,?,?,?,?,?,?,?)""",(user["organisation_id"],po_id,line_id,int(location_id),qty,user["user_id"],now(),notes or None))
        # Reuse Inventory's generic receipt transaction logic directly at ledger level.
        bal=con.execute("SELECT * FROM inventory_balances WHERE inventory_item_id=? AND location_id=?",(line["inventory_item_id"],int(location_id))).fetchone()
        if not bal:
            con.execute("""INSERT INTO inventory_balances(
                organisation_id,inventory_item_id,location_id,quantity_on_hand,quantity_reserved,quantity_available,updated_at
            ) VALUES(?,?,?,?,?,?,?)""",(user["organisation_id"],line["inventory_item_id"],int(location_id),0,0,0,now()))
            bal=con.execute("SELECT * FROM inventory_balances WHERE inventory_item_id=? AND location_id=?",(line["inventory_item_id"],int(location_id))).fetchone()
        new_on=float(bal["quantity_on_hand"])+qty
        avail=new_on-float(bal["quantity_reserved"])
        con.execute("UPDATE inventory_balances SET quantity_on_hand=?,quantity_available=?,updated_at=? WHERE inventory_item_id=? AND location_id=?",(new_on,avail,now(),line["inventory_item_id"],int(location_id)))
        con.execute("""INSERT INTO inventory_transactions(
            organisation_id,inventory_item_id,location_id,transaction_type,quantity,reference_type,reference_id,reason,user_id,created_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?)""",(user["organisation_id"],line["inventory_item_id"],int(location_id),"Receipt",qty,"PurchaseOrder",po_id,"Goods received",user["user_id"],now()))
        remaining_after=remaining-qty
        open_remaining=con.execute("SELECT COALESCE(SUM(quantity_ordered-quantity_received),0) q FROM purchase_order_lines WHERE purchase_order_id=?",(po_id,)).fetchone()["q"]
        new_status="Received" if float(open_remaining)<=0 else "Partially Received"
        con.execute("UPDATE purchase_orders SET status=?,updated_at=? WHERE purchase_order_id=?",(new_status,now(),po_id))
        audit(con,user["organisation_id"],user["user_id"],"purchase_order",str(po_id),"RECEIPT",{"status":po["status"]},{"status":new_status},{"quantity":qty,"line_id":line_id})
        con.commit();return {"receipt_id":cur.lastrowid,"remaining_line":remaining_after,"po_status":new_status,"quantity_on_hand":new_on}
    finally: con.close()

def dashboard(user):
    con=connect();org=user["organisation_id"]
    d={
        "suppliers":con.execute("SELECT COUNT(*) c FROM suppliers WHERE organisation_id=? AND active=1",(org,)).fetchone()["c"],
        "draft":con.execute("SELECT COUNT(*) c FROM purchase_orders WHERE organisation_id=? AND status='Draft'",(org,)).fetchone()["c"],
        "issued":con.execute("SELECT COUNT(*) c FROM purchase_orders WHERE organisation_id=? AND status='Issued'",(org,)).fetchone()["c"],
        "partially_received":con.execute("SELECT COUNT(*) c FROM purchase_orders WHERE organisation_id=? AND status='Partially Received'",(org,)).fetchone()["c"],
        "received":con.execute("SELECT COUNT(*) c FROM purchase_orders WHERE organisation_id=? AND status='Received'",(org,)).fetchone()["c"],
        "open_commitment":con.execute("SELECT COALESCE(SUM(total),0) v FROM purchase_orders WHERE organisation_id=? AND status IN ('Issued','Partially Received')",(org,)).fetchone()["v"],
    }
    con.close();return d
