/* Phoenix User UI V0.1 — browser shell foundation.
 * This adapter is intentionally UI-only. Live Core/API integration is a later build step.
 */

const phoenixContext = {
  tenant: { id: null, name: "Current Tenant" },
  user: { id: null, displayName: "User" },
  authorizedModules: []
};

const views = {
  home: {
    eyebrow: "Phoenix Core",
    title: "Home",
    subtitle: "Your Phoenix workspace at a glance.",
    body: `
      <div class="card-grid">
        <article class="card kpi"><div class="kpi-label">Open Work</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article>
        <article class="card kpi"><div class="kpi-label">Attention</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article>
        <article class="card kpi"><div class="kpi-label">Notifications</div><div class="kpi-value">—</div><div class="kpi-note">Awaiting Core data</div></article>
        <article class="card kpi"><div class="kpi-label">Modules</div><div class="kpi-value" id="module-count">0</div><div class="kpi-note">Authorized modules</div></article>
      </div>
      <div class="content-grid">
        <section class="card panel"><h2 class="panel-title">My Workspace</h2><p class="panel-subtitle">Personal work and context will appear here.</p><div class="empty-state"><div><strong>No live workspace data yet</strong>The shell is ready for the Core service integration.</div></div></section>
        <section class="card panel"><h2 class="panel-title">Attention</h2><p class="panel-subtitle">Items requiring your attention.</p><div class="empty-state"><div><strong>No attention items</strong>Attention data will be supplied by Core.</div></div></section>
      </div>`
  },
  "my-work": {
    eyebrow: "User Workspace",
    title: "My Work",
    subtitle: "A single place for work, attention items and actionable context.",
    body: `<section class="card panel"><div class="empty-state"><div><strong>My Work is ready</strong>Core-backed tasks, attention items and related records will appear here.</div></div></section>`
  },
  documents: {
    eyebrow: "Core Service",
    title: "Documents",
    subtitle: "Access documents available to you within the current tenant context.",
    body: `<section class="card panel"><div class="empty-state"><div><strong>No documents loaded</strong>Document discovery will use the Core/API service boundary.</div></div></section>`
  },
  profile: {
    eyebrow: "User",
    title: "Profile",
    subtitle: "Manage your personal Phoenix workspace and security context.",
    body: `<div class="content-grid"><section class="card panel"><h2 class="panel-title">My Profile</h2><p class="panel-subtitle">Identity information supplied by Core.</p><div class="empty-state"><div><strong>Profile service not connected</strong>Live profile data will be integrated through Core.</div></div></section><section class="card panel"><h2 class="panel-title">My Security</h2><p class="panel-subtitle">Security and session controls.</p><div class="empty-state"><div><strong>Security service not connected</strong>Authentication and session controls remain Core-owned.</div></div></section></div>`
  }
};

const workspaceView = document.getElementById("workspace-view");
const moduleNavigation = document.getElementById("module-navigation");
const moduleEmpty = document.getElementById("module-empty");
const tenantName = document.getElementById("tenant-name");
const userName = document.getElementById("user-name");

function renderView(route) {
  const view = views[route];
  if (!view) {
    workspaceView.innerHTML = `<div class="status error"><strong>Workspace unavailable.</strong> The requested workspace is not registered.</div>`;
    return;
  }
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div><p class="eyebrow">${view.eyebrow}</p><h1 class="workspace-title">${view.title}</h1><p class="workspace-subtitle">${view.subtitle}</p></div>
    </header>
    ${view.body}`;
  const count = document.getElementById("module-count");
  if (count) count.textContent = String(phoenixContext.authorizedModules.length);
}

function setActive(route) {
  document.querySelectorAll("[data-route]").forEach((item) => item.classList.toggle("active", item.dataset.route === route));
}

function navigate(route) {
  if (route === "production") {
    renderModuleUnavailable("production");
    setActive(route);
    return;
  }
  renderView(route);
  setActive(route);
  history.replaceState({ route }, "", `#/${route}`);
  document.getElementById("workspace").focus({ preventScroll: true });
}

function renderModuleUnavailable(code) {
  const module = phoenixContext.authorizedModules.find((item) => item.code === code);
  workspaceView.innerHTML = `
    <header class="workspace-header"><div><p class="eyebrow">Module Workspace</p><h1 class="workspace-title">${module ? module.name : code}</h1><p class="workspace-subtitle">Module workspace integration is the next build stage.</p></div></header>
    <section class="card panel"><div class="empty-state"><div><strong>Module workspace not loaded</strong>The shell will load this module through the Phoenix module contract and Core authorization boundary.</div></div></section>`;
}

function renderAuthorizedModules() {
  moduleNavigation.innerHTML = "";
  const modules = phoenixContext.authorizedModules;
  moduleEmpty.hidden = modules.length > 0;
  modules.forEach((module) => {
    const button = document.createElement("button");
    button.className = "nav-item";
    button.type = "button";
    button.dataset.route = module.code;
    button.innerHTML = `<span class="nav-icon">▦</span><span>${module.name}</span>`;
    button.addEventListener("click", () => navigate(module.code));
    moduleNavigation.appendChild(button);
  });
}

function handleHeaderAction(action) {
  const titles = { search: "Global Search", ai: "AI", communication: "Communication", notifications: "Notifications", profile: "Profile" };
  if (action === "profile") return navigate("profile");
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">${titles[action]}</h1><p class="workspace-subtitle">This Core workspace is reserved for its service integration.</p></div></header><section class="card panel"><div class="empty-state"><div><strong>Service workspace ready</strong>The live Core service will be connected in the next build stages.</div></div></section>`;
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
