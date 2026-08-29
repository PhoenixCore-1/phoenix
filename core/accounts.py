"""
Phoenix Accounts / Finance v0.1

Generic financial foundation.

This is deliberately NOT a full accounting package. It provides:
- account master
- supplier/customer financial documents
- document lines
- generic financial transaction ledger
- landed-cost records and allocation preparation

It deliberately excludes:
- Sage/ERP integration
- statutory/tax compliance
- full double-entry accounting engine
- bank reconciliation
- payment processing
- customer-specific accounting rules
- Upat-specific costing logic
"""

from decimal import Decimal, ROUND_HALF_UP
from core import connect, now, audit, has_permission

ACCOUNT_TYPES = (
    "Asset", "Liability", "Equity", "Revenue", "Cost of Sales",
    "Expense", "Other Income", "Other Expense"
)
DOCUMENT_TYPES = ("Supplier Invoice", "Customer Invoice", "Credit Note", "Debit Note", "Journal")
DOCUMENT_STATUSES = ("Draft", "Posted", "Cancelled")
LANDED_COST_TYPES = (
    "Freight", "Customs Duty", "Clearing", "Insurance",
    "Handling", "Import Fees", "Other"
)
ALLOCATION_METHODS = ("Value", "Quantity", "Weight", "Equal")


def money(v):
    return Decimal(str(v or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ensure_accounts_permissions():
    con = connect()
    permissions = [
        ("accounts.view", "View Accounts", "Access financial accounts and documents"),
        ("accounts.manage", "Manage Accounts", "Create and maintain financial masters"),
        ("accounts.post", "Post Financial Documents", "Post financial documents to the ledger"),
        ("accounts.landed_cost", "Manage Landed Costs", "Create and allocate landed costs"),
    ]
    for code, name, desc in permissions:
        con.execute(
            "INSERT OR IGNORE INTO permissions(permission_code,permission_name,description) VALUES(?,?,?)",
            (code, name, desc)
        )
    module = con.execute(
        "SELECT module_id FROM modules WHERE module_code='accounts'"
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


def list_accounts(user, search=""):
    con = connect()
    clauses = ["a.organisation_id=?"]
    params = [user["organisation_id"]]
    if search:
        like = f"%{search}%"
        clauses.append("(a.account_code LIKE ? OR a.account_name LIKE ?)")
        params += [like, like]
    rows = con.execute(
        f"""SELECT * FROM accounts a
            WHERE {' AND '.join(clauses)}
            ORDER BY a.active DESC, a.account_code""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def create_account(user, data):
    if not has_permission(user["user_id"], "accounts.manage"):
        raise PermissionError("Accounts management permission required")
    code = (data.get("account_code") or "").strip()
    name = (data.get("account_name") or "").strip()
    account_type = data.get("account_type") or "Expense"
    if not code or not name:
        raise ValueError("Account code and account name are required")
    if account_type not in ACCOUNT_TYPES:
        raise ValueError("Invalid account type")

    con = connect()
    try:
        cur = con.execute(
            """INSERT INTO accounts(
                organisation_id,account_code,account_name,account_type,currency,
                created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], code, name, account_type,
                data.get("currency") or "ZAR",
                user["user_id"], now(), now()
            )
        )
        account_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "account", str(account_id), "CREATE", None,
            {"account_code": code, "account_name": name, "account_type": account_type}
        )
        con.commit()
        return account_id
    finally:
        con.close()


def list_financial_documents(user, search=""):
    con = connect()
    clauses = ["d.organisation_id=?"]
    params = [user["organisation_id"]]
    if search:
        like = f"%{search}%"
        clauses.append(
            "(d.document_number LIKE ? OR COALESCE(s.supplier_name,'') LIKE ?)"
        )
        params += [like, like]

    rows = con.execute(
        f"""SELECT d.*,s.supplier_name,c.account_name AS customer_name,p.po_number
            FROM financial_documents d
            LEFT JOIN suppliers s ON s.supplier_id=d.supplier_id
            LEFT JOIN crm_accounts c ON c.account_id=d.customer_account_id
            LEFT JOIN purchase_orders p ON p.purchase_order_id=d.purchase_order_id
            WHERE {' AND '.join(clauses)}
            ORDER BY d.financial_document_id DESC""",
        tuple(params)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def get_financial_document(user, document_id):
    con = connect()
    doc = con.execute(
        """SELECT d.*,s.supplier_name,c.account_name AS customer_name,p.po_number
           FROM financial_documents d
           LEFT JOIN suppliers s ON s.supplier_id=d.supplier_id
           LEFT JOIN crm_accounts c ON c.account_id=d.customer_account_id
           LEFT JOIN purchase_orders p ON p.purchase_order_id=d.purchase_order_id
           WHERE d.financial_document_id=? AND d.organisation_id=?""",
        (document_id, user["organisation_id"])
    ).fetchone()
    if not doc:
        con.close()
        raise ValueError("Financial document not found")

    lines = con.execute(
        """SELECT l.*,a.account_code,a.account_name,a.account_type
           FROM financial_document_lines l
           JOIN accounts a ON a.account_id=l.account_id
           WHERE l.financial_document_id=?
           ORDER BY l.line_no""",
        (document_id,)
    ).fetchall()
    con.close()
    result = dict(doc)
    result["lines"] = [dict(x) for x in lines]
    return result


def create_financial_document(user, data):
    if not has_permission(user["user_id"], "accounts.manage"):
        raise PermissionError("Accounts management permission required")

    doc_type = data.get("document_type") or "Supplier Invoice"
    if doc_type not in DOCUMENT_TYPES:
        raise ValueError("Invalid financial document type")

    con = connect()
    try:
        supplier_id = data.get("supplier_id")
        customer_id = data.get("customer_account_id")
        po_id = data.get("purchase_order_id")

        if supplier_id:
            row = con.execute(
                "SELECT supplier_id FROM suppliers WHERE supplier_id=? AND organisation_id=?",
                (int(supplier_id), user["organisation_id"])
            ).fetchone()
            if not row:
                raise ValueError("Supplier not found")

        if customer_id:
            row = con.execute(
                "SELECT account_id FROM crm_accounts WHERE account_id=? AND organisation_id=?",
                (int(customer_id), user["organisation_id"])
            ).fetchone()
            if not row:
                raise ValueError("Customer account not found")

        if po_id:
            row = con.execute(
                "SELECT purchase_order_id FROM purchase_orders WHERE purchase_order_id=? AND organisation_id=?",
                (int(po_id), user["organisation_id"])
            ).fetchone()
            if not row:
                raise ValueError("Purchase order not found")

        count = con.execute(
            "SELECT COUNT(*) c FROM financial_documents WHERE organisation_id=?",
            (user["organisation_id"],)
        ).fetchone()["c"] + 1
        doc_number = (data.get("document_number") or "").strip() or f"FIN-{count:06d}"

        cur = con.execute(
            """INSERT INTO financial_documents(
                organisation_id,document_number,document_type,supplier_id,
                customer_account_id,purchase_order_id,document_date,currency,
                notes,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"], doc_number, doc_type,
                int(supplier_id) if supplier_id else None,
                int(customer_id) if customer_id else None,
                int(po_id) if po_id else None,
                data.get("document_date") or now()[:10],
                data.get("currency") or "ZAR",
                data.get("notes"),
                user["user_id"], now(), now()
            )
        )
        document_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "financial_document", str(document_id), "CREATE", None,
            {"document_number": doc_number, "document_type": doc_type}
        )
        con.commit()
        return document_id
    finally:
        con.close()


def add_document_line(user, document_id, data):
    if not has_permission(user["user_id"], "accounts.manage"):
        raise PermissionError("Accounts management permission required")

    qty = Decimal(str(data.get("quantity") or 1))
    unit = Decimal(str(data.get("unit_amount") or 0))
    tax = Decimal(str(data.get("tax_percent") or 0))
    if qty <= 0 or unit < 0 or tax < 0:
        raise ValueError("Invalid financial line values")

    con = connect()
    try:
        doc = con.execute(
            "SELECT * FROM financial_documents WHERE financial_document_id=? AND organisation_id=?",
            (document_id, user["organisation_id"])
        ).fetchone()
        if not doc:
            raise ValueError("Financial document not found")
        if doc["status"] != "Draft":
            raise ValueError("Only Draft financial documents can be edited")

        account_id = int(data.get("account_id") or 0)
        account = con.execute(
            "SELECT account_id FROM accounts WHERE account_id=? AND organisation_id=? AND active=1",
            (account_id, user["organisation_id"])
        ).fetchone()
        if not account:
            raise ValueError("Active financial account not found")

        line_no = con.execute(
            "SELECT COALESCE(MAX(line_no),0)+1 n FROM financial_document_lines WHERE financial_document_id=?",
            (document_id,)
        ).fetchone()["n"]

        subtotal = money(qty * unit)
        tax_value = money(subtotal * tax / Decimal("100"))
        total = subtotal + tax_value

        cur = con.execute(
            """INSERT INTO financial_document_lines(
                financial_document_id,line_no,account_id,description,
                quantity,unit_amount,tax_percent,line_subtotal,line_tax,line_total
            ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                document_id, line_no, account_id, data.get("description"),
                float(qty), float(unit), float(tax),
                float(subtotal), float(tax_value), float(total)
            )
        )

        recalculate_document(con, document_id)
        audit(
            con, user["organisation_id"], user["user_id"],
            "financial_document", str(document_id), "ADD_LINE", None,
            {"line_no": line_no, "account_id": account_id}
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


def recalculate_document(con, document_id):
    rows = con.execute(
        "SELECT quantity,unit_amount,tax_percent FROM financial_document_lines WHERE financial_document_id=?",
        (document_id,)
    ).fetchall()
    subtotal = Decimal("0")
    tax_total = Decimal("0")
    for row in rows:
        line_sub = money(Decimal(str(row["quantity"])) * Decimal(str(row["unit_amount"])))
        subtotal += line_sub
        tax_total += money(
            line_sub * Decimal(str(row["tax_percent"])) / Decimal("100")
        )
    total = subtotal + tax_total

    con.execute(
        """UPDATE financial_documents
           SET subtotal=?,tax_total=?,total=?,updated_at=?
           WHERE financial_document_id=?""",
        (float(subtotal), float(tax_total), float(total), now(), document_id)
    )
    return {
        "subtotal": float(subtotal),
        "tax_total": float(tax_total),
        "total": float(total),
    }


def post_document(user, document_id):
    if not has_permission(user["user_id"], "accounts.post"):
        raise PermissionError("Financial posting permission required")

    con = connect()
    try:
        doc = con.execute(
            "SELECT * FROM financial_documents WHERE financial_document_id=? AND organisation_id=?",
            (document_id, user["organisation_id"])
        ).fetchone()
        if not doc:
            raise ValueError("Financial document not found")
        if doc["status"] != "Draft":
            raise ValueError("Only Draft documents can be posted")

        lines = con.execute(
            "SELECT * FROM financial_document_lines WHERE financial_document_id=? ORDER BY line_no",
            (document_id,)
        ).fetchall()
        if not lines:
            raise ValueError("Cannot post a document without lines")

        # Generic ledger representation:
        # Supplier invoice -> debit expense/cost accounts, credit Accounts Payable.
        # Customer invoice -> debit Accounts Receivable, credit revenue accounts.
        # Journal -> one-sided line representation is deliberately not treated as
        # a full accounting engine in this version.
        count = con.execute(
            "SELECT COUNT(*) c FROM financial_transactions WHERE organisation_id=?",
            (user["organisation_id"],)
        ).fetchone()["c"]

        if doc["document_type"] == "Supplier Invoice":
            ap = con.execute(
                """SELECT account_id FROM accounts
                   WHERE organisation_id=? AND account_type='Liability' AND
                         (LOWER(account_name) LIKE '%payable%' OR LOWER(account_code)='2000')
                   ORDER BY account_id LIMIT 1""",
                (user["organisation_id"],)
            ).fetchone()
            if not ap:
                raise ValueError("Create a Liability account for Accounts Payable before posting supplier invoices")

            for line in lines:
                count += 1
                con.execute(
                    """INSERT INTO financial_transactions(
                        organisation_id,transaction_number,transaction_type,
                        document_type,document_id,account_id,debit,credit,
                        currency,transaction_date,description,created_by,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        user["organisation_id"], f"FT-{count:06d}", "Document",
                        doc["document_type"], document_id, line["account_id"],
                        line["line_total"], 0, doc["currency"], doc["document_date"],
                        line["description"], user["user_id"], now()
                    )
                )
            count += 1
            con.execute(
                """INSERT INTO financial_transactions(
                    organisation_id,transaction_number,transaction_type,
                    document_type,document_id,account_id,debit,credit,
                    currency,transaction_date,description,created_by,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user["organisation_id"], f"FT-{count:06d}", "Document",
                    doc["document_type"], document_id, ap["account_id"],
                    0, doc["total"], doc["currency"], doc["document_date"],
                    "Accounts Payable", user["user_id"], now()
                )
            )

        elif doc["document_type"] == "Customer Invoice":
            ar = con.execute(
                """SELECT account_id FROM accounts
                   WHERE organisation_id=? AND account_type='Asset' AND
                         (LOWER(account_name) LIKE '%receivable%' OR LOWER(account_code)='1100')
                   ORDER BY account_id LIMIT 1""",
                (user["organisation_id"],)
            ).fetchone()
            if not ar:
                raise ValueError("Create an Asset account for Accounts Receivable before posting customer invoices")

            for line in lines:
                count += 1
                con.execute(
                    """INSERT INTO financial_transactions(
                        organisation_id,transaction_number,transaction_type,
                        document_type,document_id,account_id,debit,credit,
                        currency,transaction_date,description,created_by,created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        user["organisation_id"], f"FT-{count:06d}", "Document",
                        doc["document_type"], document_id, line["account_id"],
                        0, line["line_total"], doc["currency"], doc["document_date"],
                        line["description"], user["user_id"], now()
                    )
                )
            count += 1
            con.execute(
                """INSERT INTO financial_transactions(
                    organisation_id,transaction_number,transaction_type,
                    document_type,document_id,account_id,debit,credit,
                    currency,transaction_date,description,created_by,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user["organisation_id"], f"FT-{count:06d}", "Document",
                    doc["document_type"], document_id, ar["account_id"],
                    doc["total"], 0, doc["currency"], doc["document_date"],
                    "Accounts Receivable", user["user_id"], now()
                )
            )
        else:
            raise ValueError("This document type is not yet enabled for generic posting")

        con.execute(
            "UPDATE financial_documents SET status='Posted',updated_at=? WHERE financial_document_id=?",
            (now(), document_id)
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "financial_document", str(document_id), "POST",
            {"status": "Draft"}, {"status": "Posted"}
        )
        con.commit()
    finally:
        con.close()


def create_landed_cost(user, data):
    if not has_permission(user["user_id"], "accounts.landed_cost"):
        raise PermissionError("Landed-cost permission required")

    amount = Decimal(str(data.get("amount") or 0))
    if amount <= 0:
        raise ValueError("Landed cost amount must be greater than zero")

    cost_type = data.get("cost_type") or "Other"
    method = data.get("allocation_method") or "Value"
    if cost_type not in LANDED_COST_TYPES:
        raise ValueError("Invalid landed-cost type")
    if method not in ALLOCATION_METHODS:
        raise ValueError("Invalid landed-cost allocation method")

    con = connect()
    try:
        po_id = data.get("purchase_order_id")
        if po_id:
            po = con.execute(
                "SELECT purchase_order_id FROM purchase_orders WHERE purchase_order_id=? AND organisation_id=?",
                (int(po_id), user["organisation_id"])
            ).fetchone()
            if not po:
                raise ValueError("Purchase order not found")

        fin_id = data.get("financial_document_id")
        if fin_id:
            doc = con.execute(
                "SELECT financial_document_id FROM financial_documents WHERE financial_document_id=? AND organisation_id=?",
                (int(fin_id), user["organisation_id"])
            ).fetchone()
            if not doc:
                raise ValueError("Financial document not found")

        cur = con.execute(
            """INSERT INTO landed_costs(
                organisation_id,purchase_order_id,financial_document_id,
                cost_type,description,amount,currency,allocation_method,
                status,created_by,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user["organisation_id"],
                int(po_id) if po_id else None,
                int(fin_id) if fin_id else None,
                cost_type,
                data.get("description"),
                float(amount),
                data.get("currency") or "ZAR",
                method,
                "Draft",
                user["user_id"], now(), now()
            )
        )
        landed_id = cur.lastrowid
        audit(
            con, user["organisation_id"], user["user_id"],
            "landed_cost", str(landed_id), "CREATE", None,
            {"cost_type": cost_type, "amount": float(amount), "allocation_method": method}
        )
        con.commit()
        return landed_id
    finally:
        con.close()


def allocate_landed_cost(user, landed_cost_id):
    if not has_permission(user["user_id"], "accounts.landed_cost"):
        raise PermissionError("Landed-cost permission required")

    con = connect()
    try:
        lc = con.execute(
            """SELECT * FROM landed_costs
               WHERE landed_cost_id=? AND organisation_id=?""",
            (landed_cost_id, user["organisation_id"])
        ).fetchone()
        if not lc:
            raise ValueError("Landed cost not found")
        if lc["status"] != "Draft":
            raise ValueError("Only Draft landed costs can be allocated")
        if not lc["purchase_order_id"]:
            raise ValueError("A purchase order is required for allocation")

        lines = con.execute(
            """SELECT * FROM purchase_order_lines
               WHERE purchase_order_id=? AND quantity_received>0
               ORDER BY line_no""",
            (lc["purchase_order_id"],)
        ).fetchall()
        if not lines:
            raise ValueError("No received purchase lines are available for allocation")

        bases = []
        for line in lines:
            if lc["allocation_method"] == "Quantity":
                base = Decimal(str(line["quantity_received"]))
            else:
                # Generic v0.1 uses received line value as the default value basis.
                base = Decimal(str(line["quantity_received"])) * Decimal(str(line["unit_price"]))
            if base > 0:
                bases.append((line, base))

        total_base = sum((b for _, b in bases), Decimal("0"))
        if total_base <= 0:
            raise ValueError("No positive allocation basis exists")

        # Remove prior draft allocations for a repeatable calculation.
        con.execute(
            "DELETE FROM landed_cost_allocations WHERE landed_cost_id=?",
            (landed_cost_id,)
        )

        allocated = Decimal("0")
        for idx, (line, base) in enumerate(bases):
            if idx == len(bases) - 1:
                share = money(Decimal(str(lc["amount"])) - allocated)
            else:
                share = money(Decimal(str(lc["amount"])) * base / total_base)
                allocated += share

            con.execute(
                """INSERT INTO landed_cost_allocations(
                    landed_cost_id,purchase_order_line_id,allocated_amount
                ) VALUES(?,?,?)""",
                (landed_cost_id, line["purchase_order_line_id"], float(share))
            )

        con.execute(
            "UPDATE landed_costs SET status='Allocated',updated_at=? WHERE landed_cost_id=?",
            (now(), landed_cost_id)
        )
        audit(
            con, user["organisation_id"], user["user_id"],
            "landed_cost", str(landed_cost_id), "ALLOCATE",
            {"status": "Draft"}, {"status": "Allocated"}
        )
        con.commit()
    finally:
        con.close()


def list_landed_costs(user):
    con = connect()
    rows = con.execute(
        """SELECT l.*,p.po_number
           FROM landed_costs l
           LEFT JOIN purchase_orders p ON p.purchase_order_id=l.purchase_order_id
           WHERE l.organisation_id=?
           ORDER BY l.landed_cost_id DESC""",
        (user["organisation_id"],)
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def dashboard(user):
    con = connect()
    org = user["organisation_id"]
    d = {
        "accounts": con.execute(
            "SELECT COUNT(*) c FROM accounts WHERE organisation_id=? AND active=1", (org,)
        ).fetchone()["c"],
        "draft_documents": con.execute(
            "SELECT COUNT(*) c FROM financial_documents WHERE organisation_id=? AND status='Draft'", (org,)
        ).fetchone()["c"],
        "posted_documents": con.execute(
            "SELECT COUNT(*) c FROM financial_documents WHERE organisation_id=? AND status='Posted'", (org,)
        ).fetchone()["c"],
        "landed_costs": con.execute(
            "SELECT COUNT(*) c FROM landed_costs WHERE organisation_id=?", (org,)
        ).fetchone()["c"],
        "landed_cost_value": con.execute(
            "SELECT COALESCE(SUM(amount),0) v FROM landed_costs WHERE organisation_id=? AND status='Allocated'", (org,)
        ).fetchone()["v"],
        "ledger_debits": con.execute(
            "SELECT COALESCE(SUM(debit),0) v FROM financial_transactions WHERE organisation_id=?", (org,)
        ).fetchone()["v"],
        "ledger_credits": con.execute(
            "SELECT COALESCE(SUM(credit),0) v FROM financial_transactions WHERE organisation_id=?", (org,)
        ).fetchone()["v"],
    }
    con.close()
    return d
