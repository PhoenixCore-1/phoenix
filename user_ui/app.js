import { getHostModuleCatalog, moduleFromMenuRoute } from "./core/module-registry-adapter.js";
import { coreServiceAdapter } from "./core/core-service-adapter.js";
import { renderMyWorkWorkspace } from "./core/my-work-workspace.js";
import { renderNotificationsWorkspace } from "./core/notifications-workspace.js";
import { renderProfileWorkspace } from "./core/profile-workspace.js";
import { renderSecurityWorkspace } from "./core/security-workspace.js";
import { renderIntegrationTestWorkspace } from "./core/integration-test-workspace.js";
import { renderProductionWorkspace } from "./modules/production/production-workspace.js";

/* Phoenix User UI V0.1 — Core service and module workspace controller. */

const phoenixContext = { tenant: { id: null, name: "Current Tenant" }, user: { id: null, displayName: "User" }, authorizedModules: [], session: null };

const views = {
  home: { eyebrow: "Phoenix Core", title: "Home", subtitle: "Your Phoenix workspace at a glance.", body: `<div class="card-grid"><article class="card kpi"><div class="kpi-label">Open Work</div><div class="kpi-value">—</div><div class="kpi-note">Open My Work to load Core data</div></article><article class="card kpi"><div class="kpi-label">Attention</div><div class="kpi-value">—</div><div class="kpi-note">Open My Work to load Core data</div></article><article class="card kpi"><div class="kpi-label">Notifications</div><div class="kpi-value">—</div><div class="kpi-note">Supplied by Core</div></article><article class="card kpi"><div class="kpi-label">Modules</div><div class="kpi-value" id="module-count">0</div><div class="kpi-note">Authorized modules</div></article></div><div class="content-grid"><section class="card panel"><h2 class="panel-title">My Workspace</h2><p class="panel-subtitle">Personal work and context.</p><div class="empty-state"><div><strong>Open My Work</strong>Your Core-backed tasks and attention items are available there.</div></div></section><section class="card panel"><h2 class="panel-title">Attention</h2><p class="panel-subtitle">Items requiring your attention.</p><div class="empty-state"><div><strong>Open My Work</strong>Actionable workflow items are presented in one place.</div></div></section></div>` },
  documents: { eyebrow: "Core Service", title: "Documents", subtitle: "Access documents available to you within the current tenant context.", body: `<section class="card panel"><div class="empty-state"><div><strong>No documents loaded</strong>Document discovery will use the Core/API service boundary.</div></div></section>` }
};

const coreServices = {
  search: { title: "Global Search", description: "Search across authorized Phoenix content and return permission-aware results." },
  ai: { title: "AI", description: "Open the Phoenix AI workspace using the Core AI service boundary." },
  communication: { title: "Communication", description: "Open communication using the Core communication service boundary." }
};

const workspaceView = document.getElementById("workspace-view");
const moduleNavigation = document.getElementById("module-navigation");
const moduleEmpty = document.getElementById("module-empty");
const tenantName = document.getElementById("tenant-name");
const userName = document.getElementById("user-name");

function renderView(route) {
  const view = views[route];
  if (!view) return renderError("Workspace unavailable", "The requested workspace is not registered.");
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">${view.eyebrow}</p><h1 class="workspace-title">${view.title}</h1><p class="workspace-subtitle">${view.subtitle}</p></div></header>${view.body}`;
  const count = document.getElementById("module-count");
  if (count) count.textContent = String(phoenixContext.authorizedModules.length);
}

function renderError(title, message) { workspaceView.innerHTML = `<div class="status error"><strong>${title}.</strong> ${message}</div>`; }
function setActive(route) { document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route)); }

function navigate(route) {
  const module = moduleFromMenuRoute(phoenixContext.authorizedModules, route);
  if (module) return openModule(module, route);
  if (route === "my-work") {
    renderMyWorkWorkspace({ workspaceView, userId: phoenixContext.user.id }); setActive(route); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true }); return;
  }
  if (route === "notifications") {
    renderNotificationsWorkspace({ workspaceView, coreServiceAdapter }); setActive(""); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true }); return;
  }
  if (route === "profile") {
    renderProfileWorkspace({ workspaceView, context: phoenixContext }); setActive(route); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true }); return;
  }
  if (route === "security") {
    renderSecurityWorkspace({ workspaceView, session: phoenixContext.session, authorizedModules: phoenixContext.authorizedModules }); setActive(""); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true }); return;
  }
  if (route === "integration-tests") {
    renderIntegrationTestWorkspace({ workspaceView, coreServiceAdapter }); setActive(""); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true }); return;
  }
  if (!views[route]) return renderError("Workspace unavailable", "The requested workspace is not registered.");
  renderView(route); setActive(route); history.replaceState({ route }, "", `#/${route}`); document.getElementById("workspace").focus({ preventScroll: true });
}

function openModule(module, route) {
  if (module.code === "production") renderProductionWorkspace({ workspaceView, module });
  else {
    const menuItem = module.menu.find((item) => item.route === route) || module.menu[0];
    workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Module</p><h1 class="workspace-title">${module.name}</h1><p class="workspace-subtitle">${module.description || "Authorized module workspace."}</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Module workspace ready</strong><div>${menuItem?.label || module.name} is registered for this User UI session.</div><div style="margin-top:8px;font-size:11px">Version ${module.version || "—"} · Business UI integration follows the module contract.</div></div></div></section>`;
  }
  setActive(module.code); history.replaceState({ route: module.code }, "", `#/${module.code}`); document.getElementById("workspace").focus({ preventScroll: true });
}

function renderAuthorizedModules() {
  moduleNavigation.replaceChildren(); const modules = phoenixContext.authorizedModules; moduleEmpty.hidden = modules.length > 0;
  modules.forEach((module) => {
    const menuItem = module.menu[0]; if (!menuItem) return;
    const button = document.createElement("button"); button.className = "nav-item"; button.type = "button"; button.dataset.route = module.code;
    const icon = document.createElement("span"); icon.className = "nav-icon"; icon.setAttribute("aria-hidden", "true"); icon.textContent = "▦";
    const label = document.createElement("span"); label.textContent = menuItem.label || module.name;
    button.append(icon, label); button.addEventListener("click", () => navigate(module.code)); moduleNavigation.appendChild(button);
  });
}

function openCoreService(serviceCode) {
  if (serviceCode === "notifications") return navigate("notifications");
  const service = coreServices[serviceCode];
  if (!service) return renderError("Service unavailable", "The requested Core service is not registered.");
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">${service.title}</h1><p class="workspace-subtitle">${service.description}</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Core service entry ready</strong>This is the User UI boundary. The live service implementation will be connected through the Core/API layer without direct database access.</div></div></section>`;
  document.querySelectorAll("[data-route]").forEach((item) => item.classList.remove("active"));
}
function handleHeaderAction(action) { if (action === "profile") return navigate("profile"); openCoreService(action); }

window.addEventListener("phoenix:my-work-open", (event) => {
  const detail = event.detail || {};
  if (detail.entityType === "production" && detail.entityId) {
    const module = phoenixContext.authorizedModules.find((item) => item.code === "production");
    if (module) { openModule(module, module.menu[0]?.route || "/production"); window.dispatchEvent(new CustomEvent("phoenix:production-order-open", { detail: { orderId: detail.entityId } })); return; }
  }
  renderError("Related workspace unavailable", "The related record is not currently registered for this User UI session.");
});

document.querySelectorAll("[data-route]").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.route)));
document.querySelectorAll("[data-action]").forEach((item) => item.addEventListener("click", () => handleHeaderAction(item.dataset.action)));
window.addEventListener("popstate", () => navigate(location.hash.replace(/^#\//, "") || "home"));

async function boot() {
  try {
    const session = await coreServiceAdapter.getUserContext(); phoenixContext.session = session;
    const user = session?.user || {};
    phoenixContext.tenant = { id: user.organisation_id ?? null, name: user.organisation_name || "Current Tenant" };
    phoenixContext.user = { id: user.user_id ?? null, username: user.username ?? null, displayName: user.display_name || user.username || "User", display_name: user.display_name, user_id: user.user_id, organisation_id: user.organisation_id, organisation_name: user.organisation_name };
    const catalog = await coreServiceAdapter.getAuthorizedModuleCatalog(); window.PhoenixCoreModuleCatalog = catalog; phoenixContext.authorizedModules = getHostModuleCatalog();
  } catch (error) {
    phoenixContext.authorizedModules = getHostModuleCatalog(); renderError("Phoenix session unavailable", error?.message || "The authenticated Core service could not be reached.");
  }
  tenantName.textContent = phoenixContext.tenant.name; userName.textContent = phoenixContext.user.displayName; renderAuthorizedModules();
  navigate(location.hash.replace(/^#\//, "") || "home");
}
boot();
