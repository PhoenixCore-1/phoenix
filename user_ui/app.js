/* Phoenix User UI V0.1 — Core header service-entry layer.
 * UI routes into service boundaries; live Core/API implementations are separate.
 */

const phoenixContext = {
  tenant: { id: null, name: "Current Tenant" },
  user: { id: null, displayName: "User" },
  authorizedModules: []
};

const views = {
  home: { eyebrow: "Phoenix Core", title: "Home", subtitle: "Your Phoenix workspace at a glance.", body: `<div class="card-grid"><article class="card kpi"><div class="kpi-label">Open Work</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article><article class="card kpi"><div class="kpi-label">Attention</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article><article class="card kpi"><div class="kpi-label">Notifications</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article><article class="card kpi"><div class="kpi-label">Modules</div><div class="kpi-value" id="module-count">0</div><div class="kpi-note">Authorized modules</div></article></div><div class="content-grid"><section class="card panel"><h2 class="panel-title">My Workspace</h2><p class="panel-subtitle">Personal work and context will appear here.</p><div class="empty-state"><div><strong>No live workspace data yet</strong>The shell is ready for the Core service integration.</div></div></section><section class="card panel"><h2 class="panel-title">Attention</h2><p class="panel-subtitle">Items requiring your attention.</p><div class="empty-state"><div><strong>No attention items</strong>Attention data will be supplied by Core.</div></div></section></div>` },
  "my-work": { eyebrow: "User Workspace", title: "My Work", subtitle: "A single place for work, attention items and actionable context.", body: `<section class="card panel"><div class="empty-state"><div><strong>My Work is ready</strong>Core-backed tasks, attention items and related records will appear here.</div></div></section>` },
  documents: { eyebrow: "Core Service", title: "Documents", subtitle: "Access documents available to you within the current tenant context.", body: `<section class="card panel"><div class="empty-state"><div><strong>No documents loaded</strong>Document discovery will use the Core/API service boundary.</div></div></section>` },
  profile: { eyebrow: "User", title: "Profile", subtitle: "Manage your personal Phoenix workspace and security context.", body: `<div class="content-grid"><section class="card panel"><h2 class="panel-title">My Profile</h2><p class="panel-subtitle">Identity information supplied by Core.</p><div class="empty-state"><div><strong>Profile service not connected</strong>Live profile data will be integrated through Core.</div></div></section><section class="card panel"><h2 class="panel-title">My Security</h2><p class="panel-subtitle">Security and session controls.</p><div class="empty-state"><div><strong>Security service not connected</strong>Authentication and session controls remain Core-owned.</div></div></section></div>` }
};

const coreServices = {
  search: { route: "search", title: "Global Search", description: "Search across authorized Phoenix content and return permission-aware results." },
  ai: { route: "ai", title: "AI", description: "Open the Phoenix AI workspace using the Core AI service boundary." },
  communication: { route: "communication", title: "Communication", description: "Open communication using the Core communication service boundary." },
  notifications: { route: "notifications", title: "Notifications", description: "Open the notification centre using the Core notification service boundary." }
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

function renderError(title, message) {
  workspaceView.innerHTML = `<div class="status error"><strong>${title}.</strong> ${message}</div>`;
}

function setActive(route) {
  document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route));
}

function navigate(route) {
  if (route === "production") return renderModuleUnavailable("production");
  renderView(route);
  setActive(route);
  history.replaceState({ route }, "", `#/${route}`);
  document.getElementById("workspace").focus({ preventScroll: true });
}

function renderModuleUnavailable(code) {
  const module = phoenixContext.authorizedModules.find((item) => item.code === code);
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Module Workspace</p><h1 class="workspace-title">${module ? module.name : code}</h1><p class="workspace-subtitle">Module workspace integration is the next build stage.</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Module workspace not loaded</strong>The shell will load this module through the Phoenix module contract and Core authorization boundary.</div></div></section>`;
  setActive(code);
}

function renderAuthorizedModules() {
  moduleNavigation.replaceChildren();
  const modules = phoenixContext.authorizedModules;
  moduleEmpty.hidden = modules.length > 0;
  modules.forEach((module) => {
    const button = document.createElement("button");
    button.className = "nav-item";
    button.type = "button";
    button.dataset.route = module.code;
    const icon = document.createElement("span"); icon.className = "nav-icon"; icon.setAttribute("aria-hidden", "true"); icon.textContent = "▦";
    const label = document.createElement("span"); label.textContent = module.name;
    button.append(icon, label);
    button.addEventListener("click", () => navigate(module.code));
    moduleNavigation.appendChild(button);
  });
}

function openCoreService(serviceCode) {
  const service = coreServices[serviceCode];
  if (!service) return renderError("Service unavailable", "The requested Core service is not registered.");
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">${service.title}</h1><p class="workspace-subtitle">${service.description}</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Core service entry ready</strong>This is the User UI boundary. The live service implementation will be connected through the Core/API layer without direct database access.</div></div></section>`;
  document.querySelectorAll("[data-route]").forEach((item) => item.classList.remove("active"));
}

function handleHeaderAction(action) {
  if (action === "profile") return navigate("profile");
  openCoreService(action);
}

document.querySelectorAll("[data-route]").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.route)));
document.querySelectorAll("[data-action]").forEach((item) => item.addEventListener("click", () => handleHeaderAction(item.dataset.action)));
window.addEventListener("popstate", () => navigate(location.hash.replace(/^#\//, "") || "home"));

function boot() {
  tenantName.textContent = phoenixContext.tenant.name;
  userName.textContent = phoenixContext.user.displayName;
  renderAuthorizedModules();
  const initialRoute = location.hash.replace(/^#\//, "") || "home";
  navigate(views[initialRoute] ? initialRoute : "home");
}

boot();
