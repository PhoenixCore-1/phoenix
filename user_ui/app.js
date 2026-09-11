import { getHostModuleCatalog, normalizeModuleCatalog, moduleFromMenuRoute } from "./core/module-registry-adapter.js";
import { coreServiceAdapter } from "./core/core-service-adapter.js";
import { renderHomeWorkspace } from "./core/home-workspace.js";
import { renderMyWorkWorkspace } from "./core/my-work-workspace.js";
import { renderDocumentsWorkspace } from "./core/documents-workspace.js";
import { renderNotificationsWorkspace } from "./core/notifications-workspace.js";
import { renderProfileWorkspace } from "./core/profile-workspace.js";
import { renderProfilePreferencesWorkspace } from "./core/profile-preferences-workspace.js";
import { renderSignOutWorkspace } from "./core/sign-out-workspace.js";
import { renderSecurityWorkspace } from "./core/security-workspace.js";
import { renderDevicesSessionsWorkspace } from "./core/devices-sessions-workspace.js";
import { renderActivityWorkspace } from "./core/activity-workspace.js";
import { renderHelpSupportWorkspace } from "./core/help-support-workspace.js";
import { renderAboutPhoenixWorkspace } from "./core/about-phoenix-workspace.js";
import { renderIntegrationTestWorkspace } from "./core/integration-test-workspace.js";
import { renderAIWorkspace } from "./core/ai-workspace.js";
import { renderCommunicationWorkspace } from "./core/communication-workspace.js";
import { renderSearchWorkspace } from "./core/search-workspace.js";
import { renderProductionWorkspace } from "./modules/production/production-workspace.js";

const phoenixContext = { tenant: { id: null, name: "Current Tenant" }, user: { id: null, displayName: "User" }, authorizedModules: [], session: null };
const workspaceView = document.getElementById("workspace-view");
const moduleNavigation = document.getElementById("module-navigation");
const moduleEmpty = document.getElementById("module-empty");
const tenantName = document.getElementById("tenant-name");
const userName = document.getElementById("user-name");

function renderError(title, message) { workspaceView.innerHTML = `<div class="status error"><strong>${title}.</strong> ${message}</div>`; }
function setActive(route) { document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route)); }
function setProfileActive() { setActive("profile"); }
function focusWorkspace() { document.getElementById("workspace").focus({ preventScroll: true }); }
function commitRoute(route) { history.replaceState({ route }, "", `#/${route}`); focusWorkspace(); }

function navigate(route) {
  const module = moduleFromMenuRoute(phoenixContext.authorizedModules, route);
  if (module) return openModule(module, route);
  if (route === "home") { renderHomeWorkspace({ workspaceView, context: phoenixContext, navigate }); setActive(route); commitRoute(route); return; }
  if (route === "my-work") { renderMyWorkWorkspace({ workspaceView, userId: phoenixContext.user.id }); setActive(route); commitRoute(route); return; }
  if (route === "documents") { renderDocumentsWorkspace({ workspaceView }); setActive(route); commitRoute(route); return; }
  if (route === "notifications") { renderNotificationsWorkspace({ workspaceView, coreServiceAdapter, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "profile") { renderProfileWorkspace({ workspaceView, context: phoenixContext, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "profile-preferences") { renderProfilePreferencesWorkspace({ workspaceView, context: phoenixContext, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "sign-out") { renderSignOutWorkspace({ workspaceView, coreServiceAdapter, navigate, onSignedOut: () => renderError("Session ended", "Phoenix Core confirmed logout. Please authenticate again to continue.") }); setProfileActive(); commitRoute(route); return; }
  if (route === "security") { renderSecurityWorkspace({ workspaceView, session: phoenixContext.session, authorizedModules: phoenixContext.authorizedModules, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "devices-sessions") { renderDevicesSessionsWorkspace({ workspaceView, coreServiceAdapter, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "activity") { renderActivityWorkspace({ workspaceView, coreServiceAdapter, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "help-support") { renderHelpSupportWorkspace({ workspaceView, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "about-phoenix") { renderAboutPhoenixWorkspace({ workspaceView, context: phoenixContext, navigate }); setProfileActive(); commitRoute(route); return; }
  if (route === "integration-tests") { renderIntegrationTestWorkspace({ workspaceView, coreServiceAdapter }); setActive(""); commitRoute(route); return; }
  if (route === "ai") { renderAIWorkspace({ workspaceView, coreServiceAdapter }); setActive(""); commitRoute(route); return; }
  if (route === "communication") { renderCommunicationWorkspace({ workspaceView, coreServiceAdapter }); setActive(""); commitRoute(route); return; }
  if (route === "search") { renderSearchWorkspace({ workspaceView }); setActive(""); commitRoute(route); return; }
  renderError("Workspace unavailable", "The requested workspace is not registered.");
}

function openModule(module, route) {
  if (module.code === "production") renderProductionWorkspace({ workspaceView, module });
  else { const menuItem = module.menu.find((item) => item.route === route) || module.menu[0]; workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Module</p><h1 class="workspace-title">${module.name}</h1><p class="workspace-subtitle">${module.description || "Authorized module workspace."}</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Module workspace ready</strong><div>${menuItem?.label || module.name} is registered for this User UI session.</div><div style="margin-top:8px;font-size:11px">Version ${module.version || "—"} · Business UI integration follows the module contract.</div></div></div></section>`; }
  setActive(module.code); commitRoute(route || module.code);
}

function renderAuthorizedModules() { moduleNavigation.replaceChildren(); const modules = phoenixContext.authorizedModules; moduleEmpty.hidden = modules.length > 0; modules.forEach((module) => { const menuItem = module.menu[0]; if (!menuItem) return; const button = document.createElement("button"); button.className = "nav-item"; button.type = "button"; button.dataset.route = module.code; const icon = document.createElement("span"); icon.className = "nav-icon"; icon.setAttribute("aria-hidden", "true"); icon.textContent = "▦"; const label = document.createElement("span"); label.textContent = menuItem.label || module.name; button.append(icon, label); button.addEventListener("click", () => navigate(module.code)); moduleNavigation.appendChild(button); }); }
function openCoreService(serviceCode) { if (serviceCode === "notifications") return navigate("notifications"); if (serviceCode === "ai") return navigate("ai"); if (serviceCode === "communication") return navigate("communication"); if (serviceCode === "search") return navigate("search"); return renderError("Service unavailable", "The requested Core service is not registered."); }
function handleHeaderAction(action) { if (action === "profile") return navigate("profile"); openCoreService(action); }
window.addEventListener("phoenix:my-work-open", (event) => { const detail = event.detail || {}; if (detail.entityType === "production" && detail.entityId) { const module = phoenixContext.authorizedModules.find((item) => item.code === "production"); if (module) { openModule(module, module.menu[0]?.route || "/production"); window.dispatchEvent(new CustomEvent("phoenix:production-order-open", { detail: { orderId: detail.entityId } })); return; } } renderError("Related workspace unavailable", "The related record is not currently registered for this User UI session."); });
document.querySelectorAll("[data-route]").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.route)));
document.querySelectorAll("[data-action]").forEach((item) => item.addEventListener("click", () => handleHeaderAction(item.dataset.action)));
window.addEventListener("popstate", () => navigate(location.hash.replace(/^#\//, "") || "home"));
async function boot() {
  try {
    const session = await coreServiceAdapter.getUserContext();
    if (!session || session.status === "unauthenticated" || session.authenticated === false) throw new Error("No authenticated Phoenix Core session is available.");
    phoenixContext.session = session;
    const user = session?.user || {};
    phoenixContext.tenant = { id: user.organisation_id ?? session?.organisation_id ?? null, name: user.organisation_name || session?.organisation_name || "Current Tenant" };
    phoenixContext.user = { id: user.user_id ?? user.id ?? session?.identity_id ?? null, username: user.username ?? null, displayName: user.display_name || user.username || "User", display_name: user.display_name, user_id: user.user_id ?? user.id, organisation_id: user.organisation_id ?? session?.organisation_id, organisation_name: user.organisation_name ?? session?.organisation_name };
    if (!phoenixContext.tenant.id) throw new Error("Phoenix Core did not provide an authoritative organisation context.");
    coreServiceAdapter.setContext({ sessionId: session?.session_id ?? session?.sessionId, token: session?.token, organisationId: phoenixContext.tenant.id });
    const catalog = normalizeModuleCatalog(await coreServiceAdapter.getAuthorizedModuleCatalog());
    phoenixContext.authorizedModules = catalog;
    window.PhoenixCoreModuleCatalog = catalog;
  } catch (error) {
    phoenixContext.authorizedModules = [];
    coreServiceAdapter.clearContext();
    renderError("Phoenix session unavailable", error?.message || "The authenticated Core service could not be reached.");
  }
  tenantName.textContent = phoenixContext.tenant.name;
  userName.textContent = phoenixContext.user.displayName;
  renderAuthorizedModules();
  if (phoenixContext.session) navigate(location.hash.replace(/^#\//, "") || "home");
}
boot();
