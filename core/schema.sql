PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS organisations (
    organisation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_code TEXT NOT NULL UNIQUE,
    organisation_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS branches (
    branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    branch_code TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(organisation_id, branch_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);


CREATE TABLE IF NOT EXISTS warehouses (
    warehouse_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,
    warehouse_code TEXT NOT NULL,
    warehouse_name TEXT NOT NULL,
    warehouse_type TEXT DEFAULT 'STANDARD',
    address TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
    UNIQUE (organisation_id, warehouse_code)
);

CREATE TABLE IF NOT EXISTS locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    branch_id INTEGER,
    location_code TEXT NOT NULL,
    location_name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE(organisation_id, location_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(branch_id) REFERENCES branches(branch_id)
);

CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    role_code TEXT NOT NULL,
    role_name TEXT NOT NULL,
    system_role INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(organisation_id, role_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS permissions (
    permission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_code TEXT NOT NULL UNIQUE,
    permission_name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY(role_id, permission_id),
    FOREIGN KEY(role_id) REFERENCES roles(role_id),
    FOREIGN KEY(permission_id) REFERENCES permissions(permission_id)
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT NOT NULL,
    email TEXT,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    branch_id INTEGER,
    location_id INTEGER,
    access_scope TEXT NOT NULL DEFAULT 'LOCATION',
    manager_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'Active',
    password_reset_required INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT,
    UNIQUE(organisation_id, username),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(role_id) REFERENCES roles(role_id),
    FOREIGN KEY(branch_id) REFERENCES branches(branch_id),
    FOREIGN KEY(location_id) REFERENCES locations(location_id),
    FOREIGN KEY(manager_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS modules (
    module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_code TEXT NOT NULL UNIQUE,
    module_name TEXT NOT NULL,
    description TEXT,
    core INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);


CREATE TABLE IF NOT EXISTS module_licences (
    licence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    licence_status TEXT NOT NULL DEFAULT 'NOT_LICENSED',
    licence_type TEXT NOT NULL DEFAULT 'COMMERCIAL',
    start_date TEXT,
    expiry_date TEXT,
    seats INTEGER,
    auto_enable INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY (module_id) REFERENCES modules(module_id),
    UNIQUE (organisation_id, module_id)
);


CREATE TABLE IF NOT EXISTS organisation_module_access (
    organisation_module_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    enabled_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY (module_id) REFERENCES modules(module_id),
    UNIQUE (organisation_id, module_id)
);

CREATE TABLE IF NOT EXISTS module_entitlements (
    entitlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    entitlement_code TEXT NOT NULL,
    entitlement_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY (module_id) REFERENCES modules(module_id),
    UNIQUE (organisation_id, module_id, entitlement_code)
);

CREATE TABLE IF NOT EXISTS organisation_modules (
    organisation_id INTEGER NOT NULL,
    module_id INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    configuration_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY(organisation_id, module_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(module_id) REFERENCES modules(module_id)
);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    user_id INTEGER,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    action TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    workflow_code TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(organisation_id, workflow_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS workflow_stages (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    stage_code TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    sequence_no INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(workflow_id, stage_code),
    FOREIGN KEY(workflow_id) REFERENCES workflows(workflow_id)
);

CREATE TABLE IF NOT EXISTS approval_requests (
    approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    requested_by INTEGER NOT NULL,
    approver_user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Pending',
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decision_notes TEXT,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(requested_by) REFERENCES users(user_id),
    FOREIGN KEY(approver_user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS organisation_settings (
    organisation_id INTEGER NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(organisation_id, setting_key),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS system_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS module_permissions (
    module_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    PRIMARY KEY(module_id, permission_id),
    FOREIGN KEY(module_id) REFERENCES modules(module_id),
    FOREIGN KEY(permission_id) REFERENCES permissions(permission_id)
);

CREATE TABLE IF NOT EXISTS module_menu_items (
    menu_id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL,
    menu_code TEXT NOT NULL,
    label TEXT NOT NULL,
    route TEXT NOT NULL,
    permission_code TEXT,
    display_order INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(module_id, menu_code),
    FOREIGN KEY(module_id) REFERENCES modules(module_id)
);

CREATE TABLE IF NOT EXISTS workflow_instances (
    workflow_instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    workflow_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    current_stage_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Active',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(organisation_id, workflow_id, entity_type, entity_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(workflow_id) REFERENCES workflows(workflow_id),
    FOREIGN KEY(current_stage_id) REFERENCES workflow_stages(stage_id)
);

CREATE TABLE IF NOT EXISTS workflow_instance_events (
    instance_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_instance_id INTEGER NOT NULL,
    from_stage_id INTEGER,
    to_stage_id INTEGER,
    action TEXT NOT NULL,
    user_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(workflow_instance_id) REFERENCES workflow_instances(workflow_instance_id),
    FOREIGN KEY(from_stage_id) REFERENCES workflow_stages(stage_id),
    FOREIGN KEY(to_stage_id) REFERENCES workflow_stages(stage_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS crm_accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    account_code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'Customer',
    industry TEXT,
    website TEXT,
    phone TEXT,
    email TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    owner_user_id INTEGER,
    branch_id INTEGER,
    location_id INTEGER,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, account_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(branch_id) REFERENCES branches(branch_id),
    FOREIGN KEY(location_id) REFERENCES locations(location_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS crm_contacts (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    account_id INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    job_title TEXT,
    department TEXT,
    email TEXT,
    phone TEXT,
    mobile TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    owner_user_id INTEGER,
    notes TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS crm_activities (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    activity_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT,
    account_id INTEGER,
    contact_id INTEGER,
    owner_user_id INTEGER,
    due_at TEXT,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'Open',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(contact_id) REFERENCES crm_contacts(contact_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS crm_tags (
    tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    UNIQUE(organisation_id, tag_name),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS crm_account_tags (
    account_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY(account_id, tag_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(tag_id) REFERENCES crm_tags(tag_id)
);


CREATE TABLE IF NOT EXISTS project_statuses (
    status_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    status_code TEXT NOT NULL,
    status_name TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 100,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(organisation_id, status_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    project_code TEXT NOT NULL,
    project_name TEXT NOT NULL,
    description TEXT,
    status_id INTEGER NOT NULL,
    account_id INTEGER,
    owner_user_id INTEGER,
    manager_user_id INTEGER,
    branch_id INTEGER,
    location_id INTEGER,
    start_date TEXT,
    target_date TEXT,
    completed_date TEXT,
    priority TEXT NOT NULL DEFAULT 'Normal',
    notes TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, project_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(status_id) REFERENCES project_statuses(status_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(manager_user_id) REFERENCES users(user_id),
    FOREIGN KEY(branch_id) REFERENCES branches(branch_id),
    FOREIGN KEY(location_id) REFERENCES locations(location_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS project_tasks (
    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    parent_task_id INTEGER,
    task_code TEXT NOT NULL,
    task_name TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'Open',
    priority TEXT NOT NULL DEFAULT 'Normal',
    owner_user_id INTEGER,
    start_date TEXT,
    due_date TEXT,
    completed_at TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, task_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(parent_task_id) REFERENCES project_tasks(task_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS project_milestones (
    milestone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    milestone_code TEXT NOT NULL,
    milestone_name TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'Open',
    owner_user_id INTEGER,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, milestone_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS project_activity_links (
    project_id INTEGER NOT NULL,
    activity_id INTEGER NOT NULL,
    PRIMARY KEY(project_id, activity_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(activity_id) REFERENCES crm_activities(activity_id)
);


CREATE TABLE IF NOT EXISTS sales_quotes (
    quote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    quote_number TEXT NOT NULL,
    account_id INTEGER,
    project_id INTEGER,
    quote_date TEXT NOT NULL,
    valid_until TEXT,
    status TEXT NOT NULL DEFAULT 'Draft',
    currency TEXT NOT NULL DEFAULT 'ZAR',
    subtotal REAL NOT NULL DEFAULT 0,
    discount_total REAL NOT NULL DEFAULT 0,
    tax_total REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    owner_user_id INTEGER,
    notes TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, quote_number),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(owner_user_id) REFERENCES users(user_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS sales_quote_lines (
    quote_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    unit_price REAL NOT NULL DEFAULT 0,
    discount_percent REAL NOT NULL DEFAULT 0,
    tax_percent REAL NOT NULL DEFAULT 0,
    line_subtotal REAL NOT NULL DEFAULT 0,
    line_discount REAL NOT NULL DEFAULT 0,
    line_tax REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    FOREIGN KEY(quote_id) REFERENCES sales_quotes(quote_id)
);

CREATE TABLE IF NOT EXISTS sales_quote_status_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id INTEGER NOT NULL,
    from_status TEXT,
    to_status TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(quote_id) REFERENCES sales_quotes(quote_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS production_orders (
    production_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    order_number TEXT NOT NULL,
    purpose TEXT NOT NULL DEFAULT 'Customer Order',
    account_id INTEGER,
    project_id INTEGER,
    quote_id INTEGER,
    product_ref TEXT NOT NULL,
    product_description TEXT,
    quantity_ordered REAL NOT NULL,
    required_date TEXT,
    customer_reference TEXT,
    priority TEXT NOT NULL DEFAULT 'Normal',
    status TEXT NOT NULL DEFAULT 'Released to Production',
    current_stage_id INTEGER,
    current_location TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, order_number),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(quote_id) REFERENCES sales_quotes(quote_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS production_stage_templates (
    template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    stage_code TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    stage_sequence INTEGER NOT NULL,
    default_location TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(organisation_id, stage_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS production_stages (
    stage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL,
    stage_code TEXT NOT NULL,
    stage_name TEXT NOT NULL,
    stage_sequence INTEGER NOT NULL,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'Waiting',
    start_datetime TEXT,
    finish_datetime TEXT,
    quantity_completed REAL NOT NULL DEFAULT 0,
    quantity_rejected REAL NOT NULL DEFAULT 0,
    notes TEXT,
    UNIQUE(production_order_id, stage_sequence),
    FOREIGN KEY(production_order_id) REFERENCES production_orders(production_order_id)
);

CREATE TABLE IF NOT EXISTS production_holds (
    hold_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    production_order_id INTEGER NOT NULL,
    stage_id INTEGER NOT NULL,
    problem_type TEXT NOT NULL DEFAULT 'Production Problem',
    description TEXT NOT NULL,
    affected_quantity REAL NOT NULL DEFAULT 0,
    reported_by INTEGER NOT NULL,
    reported_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Open',
    resolution TEXT,
    resolved_by INTEGER,
    resolved_at TEXT,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(production_order_id) REFERENCES production_orders(production_order_id),
    FOREIGN KEY(stage_id) REFERENCES production_stages(stage_id),
    FOREIGN KEY(reported_by) REFERENCES users(user_id),
    FOREIGN KEY(resolved_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS production_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    production_order_id INTEGER NOT NULL,
    stage_id INTEGER,
    event_type TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(production_order_id) REFERENCES production_orders(production_order_id),
    FOREIGN KEY(stage_id) REFERENCES production_stages(stage_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT NOT NULL,
    description TEXT,
    unit_of_measure TEXT NOT NULL DEFAULT 'EA',
    item_type TEXT NOT NULL DEFAULT 'Stock',
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, item_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS inventory_locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    location_code TEXT NOT NULL,
    location_name TEXT NOT NULL,
    location_type TEXT NOT NULL DEFAULT 'Warehouse',
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(organisation_id, location_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS inventory_balances (
    inventory_balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    quantity_on_hand REAL NOT NULL DEFAULT 0,
    quantity_reserved REAL NOT NULL DEFAULT 0,
    quantity_available REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    UNIQUE(inventory_item_id, location_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(inventory_item_id) REFERENCES inventory_items(inventory_item_id),
    FOREIGN KEY(location_id) REFERENCES inventory_locations(location_id)
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    inventory_transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    reference_type TEXT,
    reference_id INTEGER,
    reason TEXT,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(inventory_item_id) REFERENCES inventory_items(inventory_item_id),
    FOREIGN KEY(location_id) REFERENCES inventory_locations(location_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS inventory_reservations (
    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    reference_type TEXT NOT NULL,
    reference_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'Reserved',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    released_at TEXT,
    UNIQUE(inventory_item_id, location_id, reference_type, reference_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(inventory_item_id) REFERENCES inventory_items(inventory_item_id),
    FOREIGN KEY(location_id) REFERENCES inventory_locations(location_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    supplier_code TEXT NOT NULL,
    supplier_name TEXT NOT NULL,
    contact_name TEXT,
    email TEXT,
    phone TEXT,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    payment_terms TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, supplier_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    purchase_order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    po_number TEXT NOT NULL,
    supplier_id INTEGER NOT NULL,
    project_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Draft',
    order_date TEXT NOT NULL,
    required_date TEXT,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_total REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    notes TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, po_number),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
    purchase_order_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_order_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    inventory_item_id INTEGER NOT NULL,
    description TEXT,
    quantity_ordered REAL NOT NULL,
    unit_price REAL NOT NULL DEFAULT 0,
    tax_percent REAL NOT NULL DEFAULT 0,
    quantity_received REAL NOT NULL DEFAULT 0,
    line_subtotal REAL NOT NULL DEFAULT 0,
    line_tax REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    UNIQUE(purchase_order_id, line_no),
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY(inventory_item_id) REFERENCES inventory_items(inventory_item_id)
);

CREATE TABLE IF NOT EXISTS purchase_receipts (
    purchase_receipt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    purchase_order_id INTEGER NOT NULL,
    purchase_order_line_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    quantity_received REAL NOT NULL,
    received_by INTEGER NOT NULL,
    received_at TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY(purchase_order_line_id) REFERENCES purchase_order_lines(purchase_order_line_id),
    FOREIGN KEY(location_id) REFERENCES inventory_locations(location_id),
    FOREIGN KEY(received_by) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS accounts (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    account_code TEXT NOT NULL,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'Expense',
    currency TEXT NOT NULL DEFAULT 'ZAR',
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, account_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS financial_documents (
    financial_document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    document_number TEXT NOT NULL,
    document_type TEXT NOT NULL,
    supplier_id INTEGER,
    customer_account_id INTEGER,
    purchase_order_id INTEGER,
    document_date TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    subtotal REAL NOT NULL DEFAULT 0,
    tax_total REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Draft',
    notes TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, document_number),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(supplier_id) REFERENCES suppliers(supplier_id),
    FOREIGN KEY(customer_account_id) REFERENCES crm_accounts(account_id),
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS financial_document_lines (
    financial_document_line_id INTEGER PRIMARY KEY AUTOINCREMENT,
    financial_document_id INTEGER NOT NULL,
    line_no INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    description TEXT,
    quantity REAL NOT NULL DEFAULT 1,
    unit_amount REAL NOT NULL DEFAULT 0,
    tax_percent REAL NOT NULL DEFAULT 0,
    line_subtotal REAL NOT NULL DEFAULT 0,
    line_tax REAL NOT NULL DEFAULT 0,
    line_total REAL NOT NULL DEFAULT 0,
    UNIQUE(financial_document_id, line_no),
    FOREIGN KEY(financial_document_id) REFERENCES financial_documents(financial_document_id),
    FOREIGN KEY(account_id) REFERENCES accounts(account_id)
);

CREATE TABLE IF NOT EXISTS financial_transactions (
    financial_transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    transaction_number TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    document_type TEXT,
    document_id INTEGER,
    account_id INTEGER NOT NULL,
    debit REAL NOT NULL DEFAULT 0,
    credit REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    transaction_date TEXT NOT NULL,
    description TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(organisation_id, transaction_number),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(account_id) REFERENCES accounts(account_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS landed_costs (
    landed_cost_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    purchase_order_id INTEGER,
    financial_document_id INTEGER,
    cost_type TEXT NOT NULL,
    description TEXT,
    amount REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'ZAR',
    allocation_method TEXT NOT NULL DEFAULT 'Value',
    status TEXT NOT NULL DEFAULT 'Draft',
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(purchase_order_id) REFERENCES purchase_orders(purchase_order_id),
    FOREIGN KEY(financial_document_id) REFERENCES financial_documents(financial_document_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS landed_cost_allocations (
    landed_cost_allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    landed_cost_id INTEGER NOT NULL,
    purchase_order_line_id INTEGER NOT NULL,
    allocated_amount REAL NOT NULL,
    FOREIGN KEY(landed_cost_id) REFERENCES landed_costs(landed_cost_id),
    FOREIGN KEY(purchase_order_line_id) REFERENCES purchase_order_lines(purchase_order_line_id),
    UNIQUE(landed_cost_id, purchase_order_line_id)
);


CREATE TABLE IF NOT EXISTS workflow_definitions (
    workflow_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    workflow_code TEXT NOT NULL,
    workflow_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, workflow_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    workflow_step_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_definition_id INTEGER NOT NULL,
    step_no INTEGER NOT NULL,
    step_code TEXT NOT NULL,
    step_name TEXT NOT NULL,
    action_type TEXT NOT NULL DEFAULT 'Manual',
    required_permission TEXT,
    next_step_no INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(workflow_definition_id, step_no),
    FOREIGN KEY(workflow_definition_id) REFERENCES workflow_definitions(workflow_definition_id)
);

CREATE TABLE IF NOT EXISTS workflow_instances (
    workflow_instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    workflow_definition_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Active',
    current_step_no INTEGER NOT NULL DEFAULT 1,
    started_by INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, workflow_definition_id, entity_type, entity_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(workflow_definition_id) REFERENCES workflow_definitions(workflow_definition_id),
    FOREIGN KEY(started_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS workflow_actions (
    workflow_action_id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_instance_id INTEGER NOT NULL,
    workflow_step_id INTEGER,
    action_type TEXT NOT NULL,
    from_step_no INTEGER,
    to_step_no INTEGER,
    user_id INTEGER NOT NULL,
    reason TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(workflow_instance_id) REFERENCES workflow_instances(workflow_instance_id),
    FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(workflow_step_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS workflow_tasks (
    workflow_task_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    workflow_instance_id INTEGER NOT NULL,
    workflow_step_id INTEGER NOT NULL,
    assigned_to INTEGER,
    status TEXT NOT NULL DEFAULT 'Open',
    due_at TEXT,
    completed_at TEXT,
    completed_by INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(workflow_instance_id) REFERENCES workflow_instances(workflow_instance_id),
    FOREIGN KEY(workflow_step_id) REFERENCES workflow_steps(workflow_step_id),
    FOREIGN KEY(assigned_to) REFERENCES users(user_id),
    FOREIGN KEY(completed_by) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS report_definitions (
    report_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    report_code TEXT NOT NULL,
    report_name TEXT NOT NULL,
    description TEXT,
    report_type TEXT NOT NULL DEFAULT 'Table',
    source_module TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, report_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS dashboard_definitions (
    dashboard_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    dashboard_code TEXT NOT NULL,
    dashboard_name TEXT NOT NULL,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, dashboard_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS dashboard_widgets (
    dashboard_widget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dashboard_definition_id INTEGER NOT NULL,
    widget_code TEXT NOT NULL,
    widget_name TEXT NOT NULL,
    widget_type TEXT NOT NULL DEFAULT 'KPI',
    source_module TEXT NOT NULL,
    metric_code TEXT NOT NULL,
    position_no INTEGER NOT NULL DEFAULT 1,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(dashboard_definition_id, widget_code),
    FOREIGN KEY(dashboard_definition_id) REFERENCES dashboard_definitions(dashboard_definition_id)
);

CREATE TABLE IF NOT EXISTS saved_report_filters (
    saved_report_filter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    report_definition_id INTEGER NOT NULL,
    filter_name TEXT NOT NULL,
    filter_json TEXT NOT NULL,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, report_definition_id, filter_name),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(report_definition_id) REFERENCES report_definitions(report_definition_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS integration_definitions (
    integration_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    integration_code TEXT NOT NULL,
    integration_name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    description TEXT,
    direction TEXT NOT NULL DEFAULT 'Both',
    active INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, integration_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(created_by) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS integration_endpoints (
    integration_endpoint_id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_definition_id INTEGER NOT NULL,
    endpoint_code TEXT NOT NULL,
    endpoint_name TEXT NOT NULL,
    endpoint_type TEXT NOT NULL DEFAULT 'API',
    base_url TEXT,
    method TEXT DEFAULT 'POST',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(integration_definition_id, endpoint_code),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id)
);

CREATE TABLE IF NOT EXISTS integration_credentials (
    integration_credential_id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_definition_id INTEGER NOT NULL,
    credential_name TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    secret_reference TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(integration_definition_id, credential_name),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id)
);

CREATE TABLE IF NOT EXISTS integration_mappings (
    integration_mapping_id INTEGER PRIMARY KEY AUTOINCREMENT,
    integration_definition_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    local_field TEXT NOT NULL,
    external_field TEXT NOT NULL,
    transform_code TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(integration_definition_id, entity_type, local_field, external_field),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id)
);

CREATE TABLE IF NOT EXISTS integration_jobs (
    integration_job_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    integration_definition_id INTEGER NOT NULL,
    endpoint_id INTEGER,
    job_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    status TEXT NOT NULL DEFAULT 'Queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    request_reference TEXT,
    response_reference TEXT,
    error_message TEXT,
    queued_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id),
    FOREIGN KEY(endpoint_id) REFERENCES integration_endpoints(integration_endpoint_id)
);

CREATE TABLE IF NOT EXISTS integration_events (
    integration_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    integration_definition_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    entity_type TEXT,
    entity_id INTEGER,
    direction TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Received',
    external_reference TEXT,
    payload_reference TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id)
);

CREATE TABLE IF NOT EXISTS integration_sync_state (
    integration_sync_state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    integration_definition_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    last_external_cursor TEXT,
    last_sync_at TEXT,
    status TEXT NOT NULL DEFAULT 'Idle',
    error_message TEXT,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, integration_definition_id, entity_type),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(integration_definition_id) REFERENCES integration_definitions(integration_definition_id)
);


CREATE TABLE IF NOT EXISTS roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    role_code TEXT NOT NULL,
    role_name TEXT NOT NULL,
    description TEXT,
    system_role INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, role_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(role_id, permission_id),
    FOREIGN KEY(role_id) REFERENCES roles(role_id),
    FOREIGN KEY(permission_id) REFERENCES permissions(permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, role_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(role_id) REFERENCES roles(role_id)
);

CREATE TABLE IF NOT EXISTS branches (
    branch_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    branch_code TEXT NOT NULL,
    branch_name TEXT NOT NULL,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, branch_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS user_branches (
    user_id INTEGER NOT NULL,
    branch_id INTEGER NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    PRIMARY KEY(user_id, branch_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(branch_id) REFERENCES branches(branch_id)
);

CREATE TABLE IF NOT EXISTS module_settings (
    module_setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    module_code TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    value_type TEXT NOT NULL DEFAULT 'string',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, module_code, setting_key),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS feature_flags (
    feature_flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    flag_code TEXT NOT NULL,
    flag_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 0,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, flag_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS number_sequences (
    number_sequence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    sequence_code TEXT NOT NULL,
    sequence_name TEXT NOT NULL,
    prefix TEXT,
    next_number INTEGER NOT NULL DEFAULT 1,
    padding INTEGER NOT NULL DEFAULT 5,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, sequence_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS custom_field_definitions (
    custom_field_definition_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    field_code TEXT NOT NULL,
    field_name TEXT NOT NULL,
    field_type TEXT NOT NULL DEFAULT 'text',
    required INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, entity_type, field_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS custom_field_values (
    custom_field_value_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    custom_field_definition_id INTEGER NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    value_text TEXT,
    value_number REAL,
    value_date TEXT,
    value_boolean INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, custom_field_definition_id, entity_type, entity_id),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(custom_field_definition_id) REFERENCES custom_field_definitions(custom_field_definition_id)
);

CREATE TABLE IF NOT EXISTS security_events (
    security_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER,
    user_id INTEGER,
    event_type TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 1,
    ip_reference TEXT,
    user_agent_reference TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);


CREATE TABLE IF NOT EXISTS notification_templates (
    notification_template_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER,
    template_code TEXT NOT NULL,
    template_name TEXT NOT NULL,
    channel TEXT NOT NULL,
    subject_template TEXT,
    body_template TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    system_template INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, template_code, channel),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id)
);

CREATE TABLE IF NOT EXISTS notification_preferences (
    notification_preference_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    notification_code TEXT NOT NULL,
    in_app_enabled INTEGER NOT NULL DEFAULT 1,
    email_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(organisation_id, user_id, notification_code),
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    recipient_user_id INTEGER NOT NULL,
    notification_code TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    source_module TEXT,
    source_entity_type TEXT,
    source_entity_id INTEGER,
    action_url TEXT,
    read_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(recipient_user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    notification_delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    notification_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    provider_code TEXT,
    provider_message_id TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    queued_at TEXT NOT NULL,
    sent_at TEXT,
    failed_at TEXT,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(notification_id) REFERENCES notifications(notification_id)
);

CREATE TABLE IF NOT EXISTS notification_events (
    notification_event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_id INTEGER NOT NULL,
    notification_id INTEGER,
    event_type TEXT NOT NULL,
    channel TEXT,
    details_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(organisation_id) REFERENCES organisations(organisation_id),
    FOREIGN KEY(notification_id) REFERENCES notifications(notification_id)
);
