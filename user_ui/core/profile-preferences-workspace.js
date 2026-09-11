import { renderProfileNavigation } from "./profile-navigation.js";

/* Phoenix User UI V0.1 — User preferences workspace. */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function renderProfilePreferencesWorkspace({ workspaceView, context, navigate }) {
  const user = context?.user || {};
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">User Profile</p>
        <h1 class="workspace-title">Preferences</h1>
        <p class="workspace-subtitle">Personalise your Phoenix User UI workspace without changing company or platform settings.</p>
      </div>
    </header>
    <div data-profile-navigation></div>
    <section class="card panel">
      <div class="panel-heading-row"><div><h2 class="panel-title">Workspace Preferences</h2><p class="panel-subtitle">These controls are user-scoped. Saved preferences will be persisted through the appropriate Core service when connected.</p></div></div>
      <form class="profile-preferences-form" data-preferences-form>
        <div class="form-field"><label for="preference-language">Language</label><select id="preference-language" name="language"><option value="en-ZA">English (South Africa)</option></select></div>
        <div class="form-field"><label for="preference-density">Workspace density</label><select id="preference-density" name="density"><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></div>
        <div class="form-field checkbox-field"><input id="preference-notifications" name="notifications" type="checkbox" checked><label for="preference-notifications">Show notification indicators in the workspace</label></div>
        <div class="form-actions"><button class="button primary" type="submit">Save Preferences</button></div>
      </form>
      <div class="status" data-preferences-status role="status" aria-live="polite">Preferences are currently local to this workspace until the Core preference service is connected.</div>
      <p class="muted">Signed in as ${escapeHtml(user.displayName || user.username || "User")}. Company administration and Phoenix platform settings are not exposed here.</p>
    </section>`;

  renderProfileNavigation(workspaceView.querySelector("[data-profile-navigation]"), navigate, "profile-preferences");
  workspaceView.querySelector("[data-preferences-form]").addEventListener("submit", (event) => {
    event.preventDefault();
    const status = workspaceView.querySelector("[data-preferences-status]");
    status.className = "status";
    status.textContent = "Preferences captured for this workspace. Core persistence is not connected yet; no false save confirmation was issued.";
  });
}
