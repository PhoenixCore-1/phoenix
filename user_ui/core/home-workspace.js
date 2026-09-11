/* Phoenix User UI V0.1 — Home workspace. */

function escapeHtml(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

export function renderHomeWorkspace({ workspaceView, context, navigate }) {
  const user = context?.user || {};
  const tenant = context?.tenant || {};
  const modules = Array.isArray(context?.authorizedModules) ? context.authorizedModules : [];

  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix User Workspace</p>
        <h1 class="workspace-title">Welcome${user.displayName ? `, ${escapeHtml(user.displayName)}` : ""}</h1>
        <p class="workspace-subtitle">Your working environment for the current company and authorised Phoenix services.</p>
      </div>
      <div class="workspace-meta"><span class="status-pill">Authenticated</span></div>
    </header>
    <div class="content-grid home-grid">
      <section class="card panel home-primary-panel">
        <h2 class="panel-title">My Workspace</h2>
        <p class="panel-subtitle">Start with the work that requires your attention.</p>
        <div class="home-action-grid">
          <button type="button" class="home-action" data-home-route="my-work"><span class="home-action-icon" aria-hidden="true">▣</span><span><strong>My Work</strong><small>Open tasks, attention items and notifications.</small></span></button>
          <button type="button" class="home-action" data-home-route="documents"><span class="home-action-icon" aria-hidden="true">□</span><span><strong>Documents</strong><small>Access documents available to you.</small></span></button>
        </div>
      </section>
      <section class="card panel">
        <h2 class="panel-title">Current Company</h2>
        <p class="panel-subtitle">Authoritative tenant context supplied by Core.</p>
        <dl class="context-list">
          <div><dt>Company</dt><dd>${escapeHtml(tenant.name || "Current Tenant")}</dd></div>
          <div><dt>Company ID</dt><dd>${escapeHtml(tenant.id || "—")}</dd></div>
          <div><dt>Authorised modules</dt><dd>${modules.length}</dd></div>
        </dl>
      </section>
    </div>
    <section class="card panel home-modules-panel">
      <div class="panel-heading-row"><div><h2 class="panel-title">Your Modules</h2><p class="panel-subtitle">Only modules authorised for this User UI session are shown.</p></div></div>
      <div class="home-module-grid">
        ${modules.length ? modules.map((module) => `<button type="button" class="home-module-card" data-home-module="${escapeHtml(module.code)}"><span class="home-module-icon" aria-hidden="true">▦</span><span><strong>${escapeHtml(module.name || module.code)}</strong><small>${escapeHtml(module.description || "Open module workspace")}</small></span></button>`).join("") : `<div class="table-state">No authorised modules are available in this session.</div>`}
      </div>
    </section>
  `;

  workspaceView.querySelectorAll("[data-home-route]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.homeRoute)));
  workspaceView.querySelectorAll("[data-home-module]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.homeModule)));
}
