/* Phoenix User UI V0.1 — Profile workspace.
 * Identity/session data is supplied by Phoenix Core; no direct storage access.
 */

function escapeHtml(value) {
  return String(value ?? "—").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function identityRows(context) {
  const user = context.user || {}, tenant = context.tenant || {};
  return [["Display name", user.displayName || user.display_name || user.username], ["Username", user.username], ["User ID", user.id || user.user_id], ["Company", tenant.name || tenant.organisation_name], ["Organisation ID", tenant.id || tenant.organisation_id]];
}

export function renderProfileWorkspace({ workspaceView, context, navigate }) {
  const profileLinks = [
    ["Preferences", "profile-preferences", "Language, display and workspace preferences."],
    ["Security", "security", "Authentication and Core security controls."],
    ["Notifications", "notifications", "Notification centre and attention items."],
    ["Devices & Sessions", "devices-sessions", "Review access sessions supplied by Core."],
    ["Activity", "activity", "Review Core-authoritative user activity."],
    ["Help & Support", "help-support", "Guidance and support entry point."],
    ["About Phoenix", "about-phoenix", "Phoenix User UI and architecture information."],
    ["Sign Out", "sign-out", "Securely terminate the current Core session."]
  ];
  workspaceView.innerHTML = `
    <header class="workspace-header"><div><p class="eyebrow">User</p><h1 class="workspace-title">Profile</h1><p class="workspace-subtitle">Your Phoenix identity, preferences and security entry points.</p></div></header>
    <div class="content-grid">
      <section class="card panel"><h2 class="panel-title">My Profile</h2><p class="panel-subtitle">Identity information supplied by Phoenix Core.</p><dl class="profile-details">${identityRows(context).map(([label, value]) => `<div class="profile-detail"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl></section>
      <section class="card panel"><h2 class="panel-title">Profile &amp; Security</h2><div class="profile-option-list">${profileLinks.map(([label, route, description]) => `<button class="profile-option" type="button" data-profile-route="${route}"><span><strong>${escapeHtml(label)}</strong><small>${escapeHtml(description)}</small></span><span aria-hidden="true">›</span></button>`).join("")}</div></section>
      <section class="card panel"><h2 class="panel-title">Authorized Modules</h2><p class="panel-subtitle">Modules currently supplied by Core authorization.</p><div class="profile-module-list">${(context.authorizedModules || []).length ? context.authorizedModules.map((module) => `<span class="profile-module-chip">${escapeHtml(module.name || module.code)}</span>`).join("") : '<div class="empty-state"><div><strong>No authorized modules</strong>No business modules are currently available to this session.</div></div>'}</div></section>
    </div>`;
  workspaceView.querySelectorAll("[data-profile-route]").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.profileRoute)));
}
