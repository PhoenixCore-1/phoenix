import { renderProfileNavigation } from "./profile-navigation.js";

/* Phoenix User UI V0.1 — User activity workspace.
 * Audit/activity records are Core-owned; the browser never queries storage directly.
 */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export async function renderActivityWorkspace({ workspaceView, coreServiceAdapter, navigate }) {
  workspaceView.innerHTML = `
    <header class="workspace-header"><div><p class="eyebrow">User Profile</p><h1 class="workspace-title">Activity</h1><p class="workspace-subtitle">Review activity made available to you by Phoenix Core.</p></div><button class="button secondary" type="button" data-refresh>Refresh</button></header>
    <div data-profile-navigation></div>
    <section class="card panel"><div class="status" data-activity-status role="status" aria-live="polite">Loading activity…</div><div class="activity-list" data-activity-list></div></section>
    <section class="card panel"><h2 class="panel-title">Audit authority</h2><p class="panel-subtitle">Security and audit records remain authoritative in Phoenix Core. This workspace is read-only.</p></section>`;

  renderProfileNavigation(workspaceView.querySelector("[data-profile-navigation]"), navigate, "activity");
  const status = workspaceView.querySelector("[data-activity-status]");
  const list = workspaceView.querySelector("[data-activity-list]");
  const load = async () => {
    status.className = "status"; status.textContent = "Loading activity…"; list.replaceChildren();
    try {
      if (typeof coreServiceAdapter.getActivity !== "function") throw new Error("Core activity service is not connected yet.");
      const result = await coreServiceAdapter.getActivity();
      const items = Array.isArray(result) ? result : (result?.activity || result?.items || result?.events || []);
      if (!items.length) { status.textContent = "No activity records were returned by Core."; list.innerHTML = '<div class="empty-state"><div><strong>No activity</strong>Core returned no activity records for this user.</div></div>'; return; }
      status.textContent = `${items.length} activity record${items.length === 1 ? "" : "s"} returned by Core.`;
      list.innerHTML = items.map((item) => `<article class="activity-item"><div><strong>${escapeHtml(item.action || item.event || item.type || "Activity")}</strong><span>${escapeHtml(item.description || item.message || item.entity || "Core activity record")}</span></div><time>${escapeHtml(item.created_at || item.timestamp || item.occurred_at || "Time not supplied")}</time></article>`).join("");
    } catch (error) { status.className = "status error"; status.textContent = error?.message || "Core activity is unavailable."; list.innerHTML = '<div class="empty-state"><div><strong>Activity service unavailable</strong>No activity has been fabricated or inferred.</div></div>'; }
  };
  workspaceView.querySelector("[data-refresh]").addEventListener("click", load); await load();
}
