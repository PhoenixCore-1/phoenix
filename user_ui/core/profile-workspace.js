/* Phoenix User UI V0.1 — Profile workspace.
 * Identity/session data is supplied by Phoenix Core; no direct storage access.
 */

function escapeHtml(value) {
  return String(value ?? "—")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function identityRows(context) {
  const user = context.user || {};
  const tenant = context.tenant || {};
  return [
    ["Display name", user.displayName || user.display_name || user.username],
    ["Username", user.username],
    ["User ID", user.id || user.user_id],
    ["Company", tenant.name || tenant.organisation_name],
    ["Organisation ID", tenant.id || tenant.organisation_id]
  ];
}

export function renderProfileWorkspace({ workspaceView, context }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">User</p>
        <h1 class="workspace-title">Profile</h1>
        <p class="workspace-subtitle">Your Phoenix identity, preferences and security entry points.</p>
      </div>
    </header>
    <div class="content-grid">
      <section class="card panel">
        <h2 class="panel-title">My Profile</h2>
        <p class="panel-subtitle">Identity information supplied by Phoenix Core.</p>
        <dl class="profile-details">
          ${identityRows(context).map(([label, value]) => `<div class="profile-detail"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}
        </dl>
      </section>
      <section class="card panel">
        <h2 class="panel-title">My Workspace</h2>
        <p class="panel-subtitle">Personal User UI configuration.</p>
        <div class="profile-option-list">
          <div><strong>Preferences</strong><span>Language, display and workspace preferences remain user-scoped.</span></div>
          <div><strong>Notifications</strong><span>Notification delivery and attention settings are Core-owned.</span></div>
        </div>
      </section>
      <section class="card panel">
        <h2 class="panel-title">Security</h2>
        <p class="panel-subtitle">Authentication and session controls remain authoritative in Core.</p>
        <div class="profile-option-list">
          <div><strong>Authentication</strong><span>Managed by Phoenix Core. The User UI does not handle credentials directly.</span></div>
          <div><strong>Devices &amp; Sessions</strong><span>Session/device management will be exposed through the Core security service.</span></div>
          <div><strong>Activity</strong><span>Security-relevant activity is recorded by Core audit services.</span></div>
        </div>
      </section>
      <section class="card panel">
        <h2 class="panel-title">Authorized Modules</h2>
        <p class="panel-subtitle">Modules currently supplied by Core authorization.</p>
        <div class="profile-module-list">
          ${(context.authorizedModules || []).length
            ? context.authorizedModules.map((module) => `<span class="profile-module-chip">${escapeHtml(module.name || module.code)}</span>`).join("")
            : '<div class="empty-state"><div><strong>No authorized modules</strong>No business modules are currently available to this session.</div></div>'}
        </div>
      </section>
    </div>`;
}
