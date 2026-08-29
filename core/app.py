import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from module_adapters.production import configure_production_module, get_eta_operational_snapshot

from core import (
    init_db, connect, create_session, user_from_session,
    verify_password, permission_set, enabled_modules, has_permission,
    audit, now, get_settings, set_setting, emit_event, menu_for_user,
    module_catalog, start_workflow, advance_workflow,
    company_module_status
)
from crm import (
    list_accounts, list_contacts, list_activities,
    create_account, create_contact, create_activity,
    complete_activity, dashboard as crm_dashboard
)
from projects import (
    list_projects, list_tasks, list_milestones,
    create_project, create_task, complete_task,
    create_milestone, complete_milestone, dashboard as projects_dashboard
)
from sales import (
    list_quotes, get_quote, create_quote, add_line, change_status,
    dashboard as sales_dashboard
)
from production import (
    list_orders, get_order, create_order,
    release_order,
      start_order,
    start_stage, finish_stage, hold_stage, resume_stage,
    dashboard as production_dashboard
)
from inventory import (
    list_items, list_locations, list_balances,
    create_item, create_location, transact, reserve, release_reservation,
    dashboard as inventory_dashboard
)
from procurement import (
    list_suppliers, list_purchase_orders, get_purchase_order,
    create_supplier, create_purchase_order, add_line, change_status, receive_line,
    dashboard as procurement_dashboard
)
from accounts import (
    list_accounts, create_account,
    list_financial_documents, get_financial_document,
    create_financial_document, add_document_line, post_document,
    create_landed_cost, allocate_landed_cost, list_landed_costs,
    dashboard as accounts_dashboard
)
from workflow import (
    list_definitions, get_definition, create_definition, add_step,
    start_workflow, list_instances, get_instance, advance_workflow,
    set_instance_state, create_task, complete_task, list_tasks,
    dashboard as workflow_dashboard
)
from reporting import (
    list_report_definitions, create_report_definition,
    list_dashboards, get_dashboard, create_dashboard, add_widget,
    dashboard_data, module_snapshot, save_filter, list_saved_filters,
    dashboard as reporting_dashboard
)
from integrations import (
    list_integrations, get_integration, create_integration,
    add_endpoint, add_credential, add_mapping, queue_job,
    update_job_status, receive_event, update_sync_state,
    list_jobs, list_events, dashboard as integrations_dashboard
)
from notifications import (
    create_template, list_templates, set_preference, list_preferences,
    create_notification, list_notifications, mark_read,
    list_deliveries, update_delivery_status, dashboard as notifications_dashboard
)
from module_licensing import (
    list_licences as list_module_licences,
    set_licence as set_module_licence,
    enable_module as license_enable_module,
    disable_module as license_disable_module
)
from organisation_admin import (
    get_structure as get_org_structure,
    create_branch as create_org_branch,
    create_warehouse as create_org_warehouse,
    list_organisations as list_org_companies,
    get_organisation as get_org_company,
    create_organisation as create_org_company,
    update_organisation as update_org_company,
    set_organisation_status as set_org_company_status
)
from auth_admin import (
    list_users as auth_list_users, create_user as auth_create_user,
    change_own_password, reset_user_password
)
from security_admin import (
    list_permissions, list_roles, get_role, create_role, set_role_permissions,
    list_users, assign_user_role, remove_user_role,
    list_branches, create_branch, assign_user_branch,
    list_module_settings, set_module_setting,
    list_feature_flags, set_feature_flag,
    list_sequences, create_sequence, next_sequence_number,
    list_custom_fields, create_custom_field, set_custom_field_value,
    list_security_events, dashboard as admin_dashboard
)
HOST = "0.0.0.0"
PORT = 8080

def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if not length:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8"))

def send_json(handler, payload, status=200, headers=None):
    body = json.dumps(payload, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    if headers:
        for k, v in headers.items():
            handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)

def cookie_token(handler):
    raw = handler.headers.get("Cookie", "")
    for item in raw.split(";"):
        if item.strip().startswith("phoenix_session="):
            return item.strip().split("=", 1)[1]
    return None

def require_user(handler):
    token = cookie_token(handler)
    if not token:
        send_json(handler, {"error":"Authentication required","code":"AUTH_REQUIRED"}, 401)
        return None
    user = user_from_session(token)
    if not user:
        send_json(handler, {"error":"Session expired","code":"SESSION_EXPIRED"}, 401)
        return None
    return user

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            try:
                base_dir = Path(__file__).resolve().parent
                index_path = base_dir / "index.html"
                body = index_path.read_bytes()

                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/html; charset=utf-8"
                )
                self.send_header(
                    "Content-Length",
                    str(len(body))
                )
                self.end_headers()
                self.wfile.write(body)

            except Exception:
                send_json(
                    self,
                    {
                        "error": "Phoenix UI unavailable"
                    },
                    500
                )

            return

        if path in ("/phoenix_logo.png", "/phoenix_login_background.png"):
            try:
                asset_name = path.lstrip("/")
                base_dir = Path(__file__).resolve().parent
                asset_path = base_dir / asset_name
                body = asset_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type","image/png")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return

        if path == "/favicon.ico":
            try:
                body = open("favicon.ico","rb").read()
                self.send_response(200)
                self.send_header("Content-Type","image/x-icon")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(204)
                self.end_headers()
            return

        if path == "/api/health":
            send_json(self, {
                "status": "ok",
                "application": "Phoenix Core",
                "version": "0.2"
            })
            return

        if path == "/api/session":
            user = require_user(self)
            if not user:
                return
            send_json(self, {
                "authenticated": True,
                "user": {
                    "user_id": user["user_id"],
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "role_code": user["role_code"],
                    "role_name": user["role_name"],
                    "organisation_id": user["organisation_id"],
                    "organisation_name": user["organisation_name"],
                    "branch_id": user["branch_id"],
                    "location_id": user["location_id"],
                    "access_scope": user["access_scope"],
                    "password_reset_required": bool(user["password_reset_required"])
                },
                "permissions": sorted(permission_set(user["user_id"])),
                "modules": enabled_modules(user["organisation_id"]),
                "menu": menu_for_user(user["user_id"])
            })
            return

        if path == "/api/company/modules":
            user = require_user(self)
            if not user:
                return

            try:
                send_json(
                    self,
                    company_module_status(user)
                )
            except PermissionError as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    403
                )
            except Exception as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    400
                )

            return

        if path == "/api/modules/licensing":
            user=require_user(self)
            if not user: return
            try: send_json(self,list_module_licences(user))
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/organisation/structure":
            user=require_user(self)
            if not user: return
            try: send_json(self,get_org_structure(user))
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/module-catalog":
            user = require_user(self)
            if not user:
                return
            send_json(self, module_catalog())
            return

        if path == "/api/workflows":
            user = require_user(self)
            if not user:
                return
            con = connect()
            rows = con.execute(
                "SELECT workflow_id,workflow_code,workflow_name,entity_type,active FROM workflows WHERE organisation_id=? ORDER BY workflow_name",
                (user["organisation_id"],)
            ).fetchall()
            con.close()
            send_json(self, [dict(r) for r in rows])
            return

        if path == "/api/notifications/dashboard":
            user = require_user(self)
            if not user: return
            try: send_json(self, notifications_dashboard(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try:
                unread = self.headers.get("X-Unread-Only","0") == "1"
                send_json(self, list_notifications(user, unread))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_templates(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_preferences(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/deliveries":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_deliveries(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/dashboard":
            user = require_user(self)
            if not user: return
            try: send_json(self, admin_dashboard(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/permissions":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_permissions(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_roles(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path.startswith("/api/admin/roles/"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                send_json(self, get_role(user, role_id))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/admin/users":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_users(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_branches(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_module_settings(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_feature_flags(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_sequences(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_custom_fields(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/admin/security-events":
            user = require_user(self)
            if not user: return
            try: send_json(self, list_security_events(user))
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            return

        if path == "/api/integrations/dashboard":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "integrations.view"):
                send_json(self, {"error":"Integration permission denied"}, 403); return
            send_json(self, integrations_dashboard(user)); return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "integrations.view"):
                send_json(self, {"error":"Integration permission denied"}, 403); return
            send_json(self, list_integrations(user)); return

        if path.startswith("/api/integrations/") and "/jobs" not in path and "/events" not in path:
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "integrations.view"):
                send_json(self, {"error":"Integration permission denied"}, 403); return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, get_integration(user, integration_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "integrations.view"):
                send_json(self, {"error":"Integration permission denied"}, 403); return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_jobs(user, params.get("status",[None])[0])); return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "integrations.view"):
                send_json(self, {"error":"Integration permission denied"}, 403); return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_events(user, params.get("status",[None])[0])); return

        if path == "/api/reporting/dashboard":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "reporting.view"):
                send_json(self, {"error":"Reporting permission denied"}, 403); return
            send_json(self, reporting_dashboard(user)); return

        if path == "/api/reporting/snapshot":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "reporting.view"):
                send_json(self, {"error":"Reporting permission denied"}, 403); return
            send_json(self, module_snapshot(user)); return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "reporting.view"):
                send_json(self, {"error":"Reporting permission denied"}, 403); return
            send_json(self, list_report_definitions(user)); return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "reporting.view"):
                send_json(self, {"error":"Reporting permission denied"}, 403); return
            send_json(self, list_dashboards(user)); return

        if path.startswith("/api/reporting/dashboards/"):
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "reporting.view"):
                send_json(self, {"error":"Reporting permission denied"}, 403); return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, dashboard_data(user, dashboard_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/workflow/dashboard":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            send_json(self, workflow_dashboard(user)); return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            send_json(self, list_definitions(user)); return

        if path.startswith("/api/workflow/definitions/"):
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, get_definition(user, definition_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_instances(user, params.get("status",[None])[0])); return

        if path.startswith("/api/workflow/instances/"):
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            try:
                instance_id = int(path.split("/")[4])
                send_json(self, get_instance(user, instance_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/workflow/tasks":
            user = require_user(self)
            if not user: return
            if not has_permission(user["user_id"], "workflow.view"):
                send_json(self, {"error":"Workflow permission denied"}, 403); return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_tasks(user, params.get("status",["Open"])[0])); return

        if path == "/api/accounts/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "accounts.view"):
                send_json(self, {"error":"Accounts permission denied"}, 403)
                return
            send_json(self, accounts_dashboard(user))
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "accounts.view"):
                send_json(self, {"error":"Accounts permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_accounts(user, params.get("q", [""])[0]))
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "accounts.view"):
                send_json(self, {"error":"Accounts permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_financial_documents(user, params.get("q", [""])[0]))
            return

        if path.startswith("/api/accounts/documents/"):
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "accounts.view"):
                send_json(self, {"error":"Accounts permission denied"}, 403)
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, get_financial_document(user, document_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "accounts.view"):
                send_json(self, {"error":"Accounts permission denied"}, 403)
                return
            send_json(self, list_landed_costs(user))
            return

        if path == "/api/procurement/dashboard":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"procurement.view"):
                send_json(self,{"error":"Procurement permission denied"},403);return
            send_json(self,procurement_dashboard(user));return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"procurement.view"):
                send_json(self,{"error":"Procurement permission denied"},403);return
            from urllib.parse import parse_qs
            params=parse_qs(urlparse(self.path).query)
            send_json(self,list_suppliers(user,params.get("q",[""])[0]));return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"procurement.view"):
                send_json(self,{"error":"Procurement permission denied"},403);return
            from urllib.parse import parse_qs
            params=parse_qs(urlparse(self.path).query)
            send_json(self,list_purchase_orders(user,params.get("q",[""])[0]));return

        if path.startswith("/api/procurement/purchase-orders/"):
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"procurement.view"):
                send_json(self,{"error":"Procurement permission denied"},403);return
            try:
                po_id=int(path.split("/")[4]);send_json(self,get_purchase_order(user,po_id))
            except Exception as exc: send_json(self,{"error":str(exc)},404)
            return

        if path == "/api/inventory/dashboard":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"inventory.view"):
                send_json(self,{"error":"Inventory permission denied"},403);return
            send_json(self,inventory_dashboard(user));return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"inventory.view"):
                send_json(self,{"error":"Inventory permission denied"},403);return
            from urllib.parse import parse_qs
            params=parse_qs(urlparse(self.path).query)
            send_json(self,list_items(user,params.get("q",[""])[0]));return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"inventory.view"):
                send_json(self,{"error":"Inventory permission denied"},403);return
            send_json(self,list_locations(user));return

        if path == "/api/inventory/balances":
            user=require_user(self)
            if not user:return
            if not has_permission(user["user_id"],"inventory.view"):
                send_json(self,{"error":"Inventory permission denied"},403);return
            from urllib.parse import parse_qs
            params=parse_qs(urlparse(self.path).query)
            send_json(self,list_balances(user,params.get("item_id",[None])[0]));return

        if path == "/api/production/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "production.view"):
                send_json(self, {"error":"Production permission denied"}, 403)
                return
            send_json(self, production_dashboard(user))
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            try:
                item_id=create_item(user,data)
                send_json(self,{"ok":True,"inventory_item_id":item_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            try:
                location_id=create_location(user,data)
                send_json(self,{"ok":True,"location_id":location_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/transactions":
            user=require_user(self)
            if not user:return
            try:
                send_json(self,{"ok":True,**transact(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/reservations":
            user=require_user(self)
            if not user:return
            try:
                reservation_id=reserve(user,data)
                send_json(self,{"ok":True,"reservation_id":reservation_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/inventory/reservations/") and path.endswith("/release"):
            user=require_user(self)
            if not user:return
            try:
                reservation_id=int(path.split("/")[4])
                release_reservation(user,reservation_id)
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/production/orders":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "production.view"):
                send_json(self, {"error":"Production permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_orders(user, params.get("q", [""])[0]))
            return

        # ------------------------------------------------------------
        # Production ETA operational snapshot
        #
        # ETA business logic remains owned by the Production Module.
        # Phoenix Core provides authentication, permission checking,
        # database access and API exposure only.
        # ------------------------------------------------------------

        if path.startswith("/api/production/orders/") and path.endswith("/eta"):
            user = require_user(self)
            if not user:
                return

            if not has_permission(user["user_id"], "production.view"):
                send_json(
                    self,
                    {"error": "Production permission denied"},
                    403
                )
                return

            con = connect()

            try:
                order_id = int(path.split("/")[4])

                result = get_eta_operational_snapshot(
                    con,
                    organisation_id=user["organisation_id"],
                    production_order_id=order_id,
                )

                send_json(self, result)

            except PermissionError as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    403
                )

            except Exception as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    400
                )

            finally:
                con.close()

            return

        if path.startswith("/api/production/orders/"):
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "production.view"):
                send_json(self, {"error":"Production permission denied"}, 403)
                return
            try:
                order_id = int(path.split("/")[4])
                send_json(self, get_order(user,order_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)},404)
            return

        if path == "/api/sales/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "sales.view"):
                send_json(self, {"error":"Sales permission denied"}, 403)
                return
            send_json(self, sales_dashboard(user))
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            try:
                item_id=create_item(user,data)
                send_json(self,{"ok":True,"inventory_item_id":item_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            try:
                location_id=create_location(user,data)
                send_json(self,{"ok":True,"location_id":location_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/transactions":
            user=require_user(self)
            if not user:return
            try:
                send_json(self,{"ok":True,**transact(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/reservations":
            user=require_user(self)
            if not user:return
            try:
                reservation_id=reserve(user,data)
                send_json(self,{"ok":True,"reservation_id":reservation_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/inventory/reservations/") and path.endswith("/release"):
            user=require_user(self)
            if not user:return
            try:
                reservation_id=int(path.split("/")[4])
                release_reservation(user,reservation_id)
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/sales/quotes":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "sales.view"):
                send_json(self, {"error":"Sales permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_quotes(user, params.get("q", [""])[0]))
            return

        if path.startswith("/api/sales/quotes/"):
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "sales.view"):
                send_json(self, {"error":"Sales permission denied"}, 403)
                return
            try:
                quote_id = int(path.split("/")[4])
                send_json(self, get_quote(user, quote_id))
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path == "/api/projects/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "projects.view"):
                send_json(self, {"error":"Projects permission denied"}, 403)
                return
            send_json(self, projects_dashboard(user))
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            try:
                item_id=create_item(user,data)
                send_json(self,{"ok":True,"inventory_item_id":item_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            try:
                location_id=create_location(user,data)
                send_json(self,{"ok":True,"location_id":location_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/transactions":
            user=require_user(self)
            if not user:return
            try:
                send_json(self,{"ok":True,**transact(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/reservations":
            user=require_user(self)
            if not user:return
            try:
                reservation_id=reserve(user,data)
                send_json(self,{"ok":True,"reservation_id":reservation_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/inventory/reservations/") and path.endswith("/release"):
            user=require_user(self)
            if not user:return
            try:
                reservation_id=int(path.split("/")[4])
                release_reservation(user,reservation_id)
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/sales/quotes":
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = create_quote(user, data)
                send_json(self, {"ok":True,"quote_id":quote_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                result = add_line(user, quote_id, data)
                send_json(self, {"ok":True,**result}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/status"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                change_status(user, quote_id, str(data.get("status")), data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "projects.view"):
                send_json(self, {"error":"Projects permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_projects(user, params.get("q", [""])[0]))
            return

        if path == "/api/projects/tasks":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "projects.view"):
                send_json(self, {"error":"Projects permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            pid = params.get("project_id", [None])[0]
            pid = int(pid) if pid not in (None, "", "0") else None
            send_json(self, list_tasks(user, pid))
            return

        if path == "/api/projects/milestones":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "projects.view"):
                send_json(self, {"error":"Projects permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            pid = params.get("project_id", [None])[0]
            pid = int(pid) if pid not in (None, "", "0") else None
            send_json(self, list_milestones(user, pid))
            return

        if path == "/api/crm/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "crm.view"):
                send_json(self, {"error":"CRM permission denied"}, 403)
                return
            send_json(self, crm_dashboard(user))
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            try:
                item_id=create_item(user,data)
                send_json(self,{"ok":True,"inventory_item_id":item_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            try:
                location_id=create_location(user,data)
                send_json(self,{"ok":True,"location_id":location_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/transactions":
            user=require_user(self)
            if not user:return
            try:
                send_json(self,{"ok":True,**transact(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/reservations":
            user=require_user(self)
            if not user:return
            try:
                reservation_id=reserve(user,data)
                send_json(self,{"ok":True,"reservation_id":reservation_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/inventory/reservations/") and path.endswith("/release"):
            user=require_user(self)
            if not user:return
            try:
                reservation_id=int(path.split("/")[4])
                release_reservation(user,reservation_id)
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/sales/quotes":
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = create_quote(user, data)
                send_json(self, {"ok":True,"quote_id":quote_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                result = add_line(user, quote_id, data)
                send_json(self, {"ok":True,**result}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/status"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                change_status(user, quote_id, str(data.get("status")), data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects":
            user = require_user(self)
            if not user:
                return
            try:
                project_id = create_project(user, data)
                send_json(self, {"ok":True,"project_id":project_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects/tasks":
            user = require_user(self)
            if not user:
                return
            try:
                task_id = create_task(user, data)
                send_json(self, {"ok":True,"task_id":task_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/projects/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user:
                return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user, task_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects/milestones":
            user = require_user(self)
            if not user:
                return
            try:
                milestone_id = create_milestone(user, data)
                send_json(self, {"ok":True,"milestone_id":milestone_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/projects/milestones/") and path.endswith("/complete"):
            user = require_user(self)
            if not user:
                return
            try:
                milestone_id = int(path.split("/")[4])
                complete_milestone(user, milestone_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/crm/accounts":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "crm.view"):
                send_json(self, {"error":"CRM permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_accounts(user, params.get("q", [""])[0]))
            return

        if path == "/api/crm/contacts":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "crm.view"):
                send_json(self, {"error":"CRM permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            aid = params.get("account_id", [None])[0]
            aid = int(aid) if aid not in (None, "", "0") else None
            send_json(self, list_contacts(user, aid, params.get("q", [""])[0]))
            return

        if path == "/api/crm/activities":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "crm.view"):
                send_json(self, {"error":"CRM permission denied"}, 403)
                return
            from urllib.parse import parse_qs
            params = parse_qs(urlparse(self.path).query)
            send_json(self, list_activities(user, params.get("status", [None])[0]))
            return

        if path == "/api/dashboard":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "dashboard.view"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            con = connect()
            counts = {
                "users": con.execute(
                    "SELECT COUNT(*) c FROM users WHERE organisation_id=? AND active=1",
                    (user["organisation_id"],)
                ).fetchone()["c"],
                "branches": con.execute(
                    "SELECT COUNT(*) c FROM branches WHERE organisation_id=? AND active=1",
                    (user["organisation_id"],)
                ).fetchone()["c"],
                "locations": con.execute(
                    "SELECT COUNT(*) c FROM locations WHERE organisation_id=? AND active=1",
                    (user["organisation_id"],)
                ).fetchone()["c"],
                "audit_events": con.execute(
                    "SELECT COUNT(*) c FROM audit_events WHERE organisation_id=?",
                    (user["organisation_id"],)
                ).fetchone()["c"],
                "pending_approvals": con.execute(
                    "SELECT COUNT(*) c FROM approval_requests WHERE organisation_id=? AND status='Pending'",
                    (user["organisation_id"],)
                ).fetchone()["c"]
            }
            con.close()
            send_json(self, counts)
            return

        if path == "/api/settings":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "organisation.manage"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            send_json(self, get_settings(user["organisation_id"]))
            return

        if path == "/api/users":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "users.view"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            con = connect()
            rows = con.execute(
                """SELECT u.user_id,u.username,u.display_name,r.role_name,
                          u.access_scope,u.active,u.branch_id,u.location_id
                   FROM users u JOIN roles r ON r.role_id=u.role_id
                   WHERE u.organisation_id=? ORDER BY u.display_name""",
                (user["organisation_id"],)
            ).fetchall()
            con.close()
            send_json(self, [dict(r) for r in rows])
            return

        if path == "/api/branches":
            user = require_user(self)
            if not user:
                return
            con = connect()
            rows = con.execute(
                "SELECT * FROM branches WHERE organisation_id=? ORDER BY branch_name",
                (user["organisation_id"],)
            ).fetchall()
            con.close()
            send_json(self, [dict(r) for r in rows])
            return

        if path == "/api/locations":
            user = require_user(self)
            if not user:
                return
            con = connect()
            rows = con.execute(
                "SELECT * FROM locations WHERE organisation_id=? ORDER BY location_name",
                (user["organisation_id"],)
            ).fetchall()
            con.close()
            send_json(self, [dict(r) for r in rows])
            return

        if path == "/api/audit":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "audit.view"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            con = connect()
            rows = con.execute(
                """SELECT a.*,u.display_name
                   FROM audit_events a
                   LEFT JOIN users u ON u.user_id=a.user_id
                   WHERE a.organisation_id=?
                   ORDER BY a.audit_id DESC LIMIT 100""",
                (user["organisation_id"],)
            ).fetchall()
            con.close()
            send_json(self, [dict(r) for r in rows])
            return

        send_json(self, {"error":"Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        data = read_json(self)

        # ------------------------------------------------------------
        # Production POST routes
        # These routes MUST live inside do_POST().
        # ------------------------------------------------------------

        if path.startswith("/api/production/orders/") and path.endswith("/release"):
            user = require_user(self)
            if not user:
                return
            try:
                order_id = int(path.split("/")[4])
                result = release_order(user, order_id)
                send_json(self, {"ok": True, **result})
            except PermissionError as exc:
                send_json(self, {"error": str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 400)
            return

        if path == "/api/production/orders":
            user = require_user(self)
            if not user:
                return
            try:
                order_id = create_order(user, data)
                send_json(
                    self,
                    {
                        "ok": True,
                        "production_order_id": order_id
                    },
                    201
                )
            except PermissionError as exc:
                send_json(self, {"error": str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error": str(exc)}, 400)
            return

        # ------------------------------------------------------------

        # Production Order START

        #

        # Starts the overall Production Order.

        #

        # This is intentionally separate from start_stage().

        #

        # Lifecycle:

        #

        #     RELEASED

        #         ↓

        #     STARTED / IN PRODUCTION

        #         ↓

        #     start individual stage

        #

        # The Production Module remains the owner of the

        # lifecycle transition and ETA production-start logic.

        # Core only provides authentication, permissions and

        # HTTP API exposure.

        # ------------------------------------------------------------


        if (
            path.startswith("/api/production/orders/")
            and path.count("/") == 5
            and path.endswith("/start")
        ):

            user = require_user(self)

            if not user:

                return


            try:

                parts = path.split("/")

                order_id = int(parts[4])


                result = start_order(

                    user,

                    order_id,

                )


                payload = {"ok": True}


                if isinstance(result, dict):

                    payload.update(result)


                send_json(

                    self,

                    payload

                )


            except PermissionError as exc:

                send_json(

                    self,

                    {"error": str(exc)},

                    403

                )


            except Exception as exc:

                send_json(

                    self,

                    {"error": str(exc)},

                    400

                )


            return


        if path.startswith("/api/production/orders/") and "/stages/" in path:
            user = require_user(self)
            if not user:
                return

            parts = path.split("/")

            try:
                order_id = int(parts[4])
                stage_id = int(parts[6])
                action_name = parts[7]

                if action_name == "start":
                    start_stage(
                        user,
                        order_id,
                        stage_id
                    )

                    send_json(
                        self,
                        {
                            "ok": True,
                            "message": "Production stage started"
                        }
                    )

                elif action_name == "finish":
                    finish = data

                    result = finish_stage(
                        user,
                        order_id,
                        stage_id,
                        finish.get("completed_qty", 0),
                        finish.get("rejected_qty", 0),
                        finish.get("notes", "")
                    )

                    send_json(
                        self,
                        {
                            "ok": True,
                            **result
                        }
                    )

                elif action_name == "hold":
                    hold_stage(
                        user,
                        order_id,
                        stage_id,
                        data.get(
                            "problem_type",
                            "Production Problem"
                        ),
                        data.get(
                            "description",
                            ""
                        ),
                        data.get(
                            "affected_quantity",
                            0
                        )
                    )

                    send_json(
                        self,
                        {
                            "ok": True,
                            "message":
                                "Production stage placed on hold"
                        }
                    )

                elif action_name == "resume":
                    resume_stage(
                        user,
                        order_id,
                        stage_id,
                        data.get(
                            "resolution",
                            "Production resumed"
                        )
                    )

                    send_json(
                        self,
                        {
                            "ok": True,
                            "message":
                                "Production stage resumed"
                        }
                    )

                else:
                    send_json(
                        self,
                        {
                            "error":
                                "Unknown production action"
                        },
                        400
                    )

            except PermissionError as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    403
                )

            except Exception as exc:
                send_json(
                    self,
                    {"error": str(exc)},
                    400
                )

            return


        if path == "/api/modules/licensing":
            user=require_user(self)
            if not user: return
            try: send_json(self,list_module_licences(user))
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/modules/licensing/set":
            user=require_user(self)
            if not user: return
            try:
                licence_id=set_module_licence(user,int(data.get("module_id")),data.get("licence_status","ACTIVE"),
                                               data.get("licence_type","COMMERCIAL"),data.get("start_date"),
                                               data.get("expiry_date"),data.get("seats"),bool(data.get("auto_enable")),
                                               data.get("notes"))
                send_json(self,{"ok":True,"licence_id":licence_id})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/modules/licensing/enable":
            user=require_user(self)
            if not user: return
            try:
                license_enable_module(user,int(data.get("module_id")))
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/modules/licensing/disable":
            user=require_user(self)
            if not user: return
            try:
                license_disable_module(user,int(data.get("module_id")))
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/organisation/structure":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, get_org_structure(user))
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/organisation/branches":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True,"branch_id":create_org_branch(user, data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/organisation/warehouses":
            user = require_user(self)
            if not user:
                return

        # ------------------------------------------------------------
        # Company / Tenant Administration
        # ------------------------------------------------------------

        if path == "/api/admin/companies":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, list_org_companies(user))
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/companies/") and path.endswith("/detail"):
            user = require_user(self)
            if not user:
                return
            try:
                company_id = int(path.split("/")[4])
                send_json(
                    self,
                    get_org_company(user, company_id)
                )
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 404)
            return

        if path.startswith("/api/admin/companies/") and path.endswith("/status"):
            user = require_user(self)
            if not user:
                return
            try:
                company_id = int(path.split("/")[4])
                set_org_company_status(
                    user,
                    company_id,
                    bool(data.get("active"))
                )
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/companies/"):
            user = require_user(self)
            if not user:
                return
            try:
                company_id = int(path.split("/")[4])
                update_org_company(
                    user,
                    company_id,
                    data
                )
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/companies/create":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(
                    self,
                    {
                        "ok":True,
                        "organisation_id":create_org_company(user, data)
                    },
                    201
                )
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return
            try:
                send_json(self, {"ok":True,"warehouse_id":create_org_warehouse(user, data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/auth/change-password":
            user=require_user(self)
            if not user: return
            try:
                change_own_password(user,data.get("current_password",""),data.get("new_password",""))
                send_json(self,{"ok":True,"password_reset_required":False})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/admin/users":
            user=require_user(self)
            if not user: return
            try: send_json(self,auth_list_users(user))
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/admin/users/create":
            user=require_user(self)
            if not user: return
            try: send_json(self,{"ok":True,"user_id":auth_create_user(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/reset-password"):
            user=require_user(self)
            if not user: return
            try:
                target_id=int(path.split("/")[4])
                reset_user_password(user,target_id,data.get("new_password",""))
                send_json(self,{"ok":True,"password_reset_required":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/login":
            username = str(data.get("username","")).strip()
            password = data.get("password","")
            remember_me = bool(data.get("remember_me", False))
            con = connect()
            user = con.execute(
                """SELECT u.*,r.role_code,r.role_name
                   FROM users u JOIN roles r ON r.role_id=u.role_id
                   WHERE u.username=? AND u.active=1
                   ORDER BY u.organisation_id LIMIT 1""",
                (username,)
            ).fetchone()
            con.close()

            if not user or not verify_password(password, user["password_hash"]):
                send_json(self, {"error":"Invalid username or password"}, 401)
                return

            token = create_session(user["user_id"], remember_me=remember_me)
            con = connect()
            audit(
                con, user["organisation_id"], user["user_id"],
                "session", token, "LOGIN"
            )
            con.commit()
            con.close()

            send_json(
                self,
                {"ok":True},
                200,
                {"Set-Cookie":f"phoenix_session={token}; HttpOnly; SameSite=Lax; Path=/" + (f"; Max-Age={30*24*60*60}" if remember_me else "")}
            )
            return

        if path == "/api/settings":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "organisation.manage"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            key = str(data.get("key","")).strip()
            value = data.get("value","")
            if not key:
                send_json(self, {"error":"Setting key is required"}, 400)
                return
            set_setting(user["organisation_id"], key, value)
            emit_event(user["organisation_id"], user["user_id"], "settings.updated", {"key": key})
            send_json(self, {"ok": True})
            return

        if path.startswith("/api/modules/") and path.endswith("/enable"):
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "modules.manage"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            code = path.split("/")[3]
            con = connect()
            module = con.execute(
                "SELECT module_id,module_code,module_name,core FROM modules WHERE module_code=? AND active=1",
                (code,)
            ).fetchone()
            if not module:
                con.close()
                send_json(self, {"error":"Module not found"}, 404)
                return
            con.execute(
                """INSERT INTO organisation_modules(organisation_id,module_id,enabled)
                   VALUES(?,?,1)
                   ON CONFLICT(organisation_id,module_id)
                   DO UPDATE SET enabled=1""",
                (user["organisation_id"], module["module_id"])
            )
            audit(con, user["organisation_id"], user["user_id"], "module", code, "ENABLE")
            con.commit()
            con.close()
            send_json(self, {"ok": True, "module": code})
            return

        if path == "/api/workflows/start":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "workflow.manage"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            try:
                instance_id = start_workflow(
                    user["user_id"],
                    int(data["workflow_id"]),
                    str(data["entity_type"]),
                    str(data["entity_id"])
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id})
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflows/advance":
            user = require_user(self)
            if not user:
                return
            if not has_permission(user["user_id"], "workflow.manage"):
                send_json(self, {"error":"Permission denied"}, 403)
                return
            try:
                result = advance_workflow(
                    user["user_id"],
                    int(data["workflow_instance_id"]),
                    data.get("notes")
                )
                send_json(self, {"ok":True,**result})
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/templates":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_template_id":create_template(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications/preferences":
            user = require_user(self)
            if not user: return
            try: set_preference(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/notifications":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"notification_id":create_notification(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/") and path.endswith("/read"):
            user = require_user(self)
            if not user: return
            try:
                nid = int(path.split("/")[3])
                mark_read(user,nid); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/notifications/deliveries/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                did = int(path.split("/")[3])
                update_delivery_status(
                    user,did,data.get("status"),
                    data.get("error"),data.get("provider_message_id")
                )
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/roles":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"role_id":create_role(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/roles/") and path.endswith("/permissions"):
            user = require_user(self)
            if not user: return
            try:
                role_id = int(path.split("/")[4])
                set_role_permissions(user,role_id,data.get("permission_ids") or [])
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/roles"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id = int(path.split("/")[4])
                if data.get("action","assign")=="remove":
                    remove_user_role(user,target_user_id,int(data.get("role_id")))
                else:
                    assign_user_role(user,target_user_id,int(data.get("role_id")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/branches":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"branch_id":create_branch(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/users/") and path.endswith("/branches"):
            user = require_user(self)
            if not user: return
            try:
                target_user_id=int(path.split("/")[4])
                assign_user_branch(user,target_user_id,int(data.get("branch_id")),bool(data.get("is_primary")))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/settings":
            user = require_user(self)
            if not user: return
            try: set_module_setting(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/feature-flags":
            user = require_user(self)
            if not user: return
            try: set_feature_flag(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/sequences":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"number_sequence_id":create_sequence(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/admin/sequences/") and path.endswith("/next"):
            user = require_user(self)
            if not user: return
            try:
                code=path.split("/")[4]
                send_json(self, {"number":next_sequence_number(user,code)})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-fields":
            user = require_user(self)
            if not user: return
            try: send_json(self, {"ok":True,"custom_field_definition_id":create_custom_field(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/admin/custom-field-values":
            user = require_user(self)
            if not user: return
            try: set_custom_field_value(user,data); send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_definition_id":create_integration(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/endpoints"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_endpoint_id":add_endpoint(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/credentials"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_credential_id":add_credential(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/") and path.endswith("/mappings"):
            user = require_user(self)
            if not user: return
            try:
                integration_id = int(path.split("/")[3])
                send_json(self, {"ok":True, "integration_mapping_id":add_mapping(user,integration_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/jobs":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_job_id":queue_job(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/integrations/jobs/") and path.endswith("/status"):
            user = require_user(self)
            if not user: return
            try:
                job_id = int(path.split("/")[4])
                update_job_status(user,job_id,str(data.get("status")),data.get("error_message"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/events":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "integration_event_id":receive_event(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/integrations/sync-state":
            user = require_user(self)
            if not user: return
            try:
                update_sync_state(user,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/reports":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "report_definition_id":create_report_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/reporting/dashboards":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "dashboard_definition_id":create_dashboard(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/dashboards/") and path.endswith("/widgets"):
            user = require_user(self)
            if not user: return
            try:
                dashboard_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "dashboard_widget_id":add_widget(user,dashboard_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/reporting/reports/") and path.endswith("/filters"):
            user = require_user(self)
            if not user: return
            try:
                report_id = int(path.split("/")[4])
                save_filter(user,report_id,data)
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/definitions":
            user = require_user(self)
            if not user: return
            try:
                send_json(self, {"ok":True, "workflow_definition_id":create_definition(user,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/definitions/") and path.endswith("/steps"):
            user = require_user(self)
            if not user: return
            try:
                definition_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "workflow_step_id":add_step(user,definition_id,data)}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/workflow/instances":
            user = require_user(self)
            if not user: return
            try:
                instance_id = start_workflow(
                    user, int(data.get("workflow_definition_id")),
                    str(data.get("entity_type")), int(data.get("entity_id"))
                )
                send_json(self, {"ok":True,"workflow_instance_id":instance_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/advance"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                status = advance_workflow(user,instance_id,data.get("reason"))
                send_json(self, {"ok":True,"status":status})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/state"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                set_instance_state(user,instance_id,str(data.get("status")),data.get("reason"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/instances/") and path.endswith("/tasks"):
            user = require_user(self)
            if not user: return
            try:
                instance_id = int(path.split("/")[4])
                task_id = create_task(user,instance_id,data)
                send_json(self, {"ok":True,"workflow_task_id":task_id}, 201)
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/workflow/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user: return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user,task_id,data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc: send_json(self, {"error":str(exc)}, 403)
            except Exception as exc: send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "account_id":create_account(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/documents":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "financial_document_id":create_financial_document(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                send_json(self, {"ok":True, "financial_document_line_id":add_document_line(user,document_id,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/documents/") and path.endswith("/post"):
            user = require_user(self)
            if not user:
                return
            try:
                document_id = int(path.split("/")[4])
                post_document(user,document_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/accounts/landed-costs":
            user = require_user(self)
            if not user:
                return
            try:
                send_json(self, {"ok":True, "landed_cost_id":create_landed_cost(user,data)}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/accounts/landed-costs/") and path.endswith("/allocate"):
            user = require_user(self)
            if not user:
                return
            try:
                landed_cost_id = int(path.split("/")[4])
                allocate_landed_cost(user,landed_cost_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/procurement/suppliers":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"supplier_id":create_supplier(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/procurement/purchase-orders":
            user=require_user(self)
            if not user:return
            try: send_json(self,{"ok":True,"purchase_order_id":create_purchase_order(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/lines"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);send_json(self,{"ok":True,**add_line(user,po_id,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/status"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4]);change_status(user,po_id,str(data.get("status")));send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/procurement/purchase-orders/") and path.endswith("/receive"):
            user=require_user(self)
            if not user:return
            try:
                po_id=int(path.split("/")[4])
                result=receive_line(user,po_id,int(data.get("purchase_order_line_id")),int(data.get("location_id")),data.get("quantity"),data.get("notes",""))
                send_json(self,{"ok":True,**result})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/items":
            user=require_user(self)
            if not user:return
            try:
                item_id=create_item(user,data)
                send_json(self,{"ok":True,"inventory_item_id":item_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/locations":
            user=require_user(self)
            if not user:return
            try:
                location_id=create_location(user,data)
                send_json(self,{"ok":True,"location_id":location_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/transactions":
            user=require_user(self)
            if not user:return
            try:
                send_json(self,{"ok":True,**transact(user,data)},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/inventory/reservations":
            user=require_user(self)
            if not user:return
            try:
                reservation_id=reserve(user,data)
                send_json(self,{"ok":True,"reservation_id":reservation_id},201)
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path.startswith("/api/inventory/reservations/") and path.endswith("/release"):
            user=require_user(self)
            if not user:return
            try:
                reservation_id=int(path.split("/")[4])
                release_reservation(user,reservation_id)
                send_json(self,{"ok":True})
            except PermissionError as exc: send_json(self,{"error":str(exc)},403)
            except Exception as exc: send_json(self,{"error":str(exc)},400)
            return

        if path == "/api/sales/quotes":
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = create_quote(user, data)
                send_json(self, {"ok":True,"quote_id":quote_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/lines"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                result = add_line(user, quote_id, data)
                send_json(self, {"ok":True,**result}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/sales/quotes/") and path.endswith("/status"):
            user = require_user(self)
            if not user:
                return
            try:
                quote_id = int(path.split("/")[4])
                change_status(user, quote_id, str(data.get("status")), data.get("notes"))
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects":
            user = require_user(self)
            if not user:
                return
            try:
                project_id = create_project(user, data)
                send_json(self, {"ok":True,"project_id":project_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects/tasks":
            user = require_user(self)
            if not user:
                return
            try:
                task_id = create_task(user, data)
                send_json(self, {"ok":True,"task_id":task_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/projects/tasks/") and path.endswith("/complete"):
            user = require_user(self)
            if not user:
                return
            try:
                task_id = int(path.split("/")[4])
                complete_task(user, task_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/projects/milestones":
            user = require_user(self)
            if not user:
                return
            try:
                milestone_id = create_milestone(user, data)
                send_json(self, {"ok":True,"milestone_id":milestone_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/projects/milestones/") and path.endswith("/complete"):
            user = require_user(self)
            if not user:
                return
            try:
                milestone_id = int(path.split("/")[4])
                complete_milestone(user, milestone_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/crm/accounts":
            user = require_user(self)
            if not user:
                return
            try:
                account_id = create_account(user, data)
                send_json(self, {"ok":True,"account_id":account_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/crm/contacts":
            user = require_user(self)
            if not user:
                return
            try:
                contact_id = create_contact(user, data)
                send_json(self, {"ok":True,"contact_id":contact_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/crm/activities":
            user = require_user(self)
            if not user:
                return
            try:
                activity_id = create_activity(user, data)
                send_json(self, {"ok":True,"activity_id":activity_id}, 201)
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path.startswith("/api/crm/activities/") and path.endswith("/complete"):
            user = require_user(self)
            if not user:
                return
            try:
                activity_id = int(path.split("/")[4])
                complete_activity(user, activity_id)
                send_json(self, {"ok":True})
            except PermissionError as exc:
                send_json(self, {"error":str(exc)}, 403)
            except Exception as exc:
                send_json(self, {"error":str(exc)}, 400)
            return

        if path == "/api/logout":
            token = cookie_token(self)
            if token:
                con = connect()
                row = con.execute(
                    "SELECT user_id FROM sessions WHERE session_id=?",
                    (token,)
                ).fetchone()
                con.execute(
                    "UPDATE sessions SET active=0 WHERE session_id=?",
                    (token,)
                )
                if row:
                    user = con.execute(
                        "SELECT organisation_id FROM users WHERE user_id=?",
                        (row["user_id"],)
                    ).fetchone()
                    if user:
                        audit(con,user["organisation_id"],row["user_id"],"session",token,"LOGOUT")
                con.commit()
                con.close()
            send_json(
                self, {"ok":True}, 200,
                {"Set-Cookie":"phoenix_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"}
            )
            return

        send_json(self, {"error":"Not found"}, 404)

if __name__ == "__main__":
    init_db()

    configure_production_module(
        r"C:\Users\Disa Lombard\OneDrive - Upat\Upat\Phoenix App\Phoenix_App_Production_Module1_V1.0\Phoenix_Production_Module1_V1"
    )

    print(f"Phoenix Core v1.0 running at http://localhost:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
