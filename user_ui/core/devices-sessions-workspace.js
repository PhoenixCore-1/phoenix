/* Phoenix User UI V0.1 — Devices & Sessions workspace.
 * Session authority remains in Phoenix Core. No client-side session store is used.
 */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export async function renderDevicesSessionsWorkspace({ workspaceView, coreServiceAdapter }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div><p class="eyebrow">Security</p><h1 class="workspace-title">Devices &amp; Sessions</h1><p class="workspace-subtitle">Review active access to your Phoenix account. Session validity is determined by Phoenix Core.</p></div>
    </header>
    <section class="card panel">
      <div class="panel-heading-row"><div><h2 class="panel-title">Active Sessions</h2><p class="panel-subtitle">Only Core-authoritative session data may be displayed here.</p></div><button class="button secondary" type="button" data-refresh>Refresh</button></div>
      <div class="status" data-session-status role="status" aria-live="polite">Loading session information…</div>
      <div class="session-list" data-session-list></div>
    </section>
    <section class="card panel">
      <h2 class="panel-title">Security boundary</h2>
      <p class="panel-subtitle">The User UI cannot extend, revoke, validate or manufacture session authority.</p>
      <ul class="security-list"><li>Authentication and expiry are enforced by Phoenix Core.</li><li>Session revocation must be performed by the authoritative Core service.</li><li>No passwords, tokens or session records are stored in this workspace.</li></ul>
    </section>`;

  const status = workspaceView.querySelector("[data-session-status]");
  const list = workspaceView.querySelector("[data-session-list]");
  const load = async () => {
    status.textContent = "Loading session information…";
    status.className = "status";
    list.replaceChildren();
    try {
      if (typeof coreServiceAdapter.getSessions !== "function") throw new Error("Core session listing service is not connected yet.");
      const result = await coreServiceAdapter.getSessions();
      const sessions = Array.isArray(result) ? result : (result?.sessions || result?.items || []);
      if (!sessions.length) {
        status.textContent = "No session records were returned by Core.";
        list.innerHTML = '<div class="empty-state"><div><strong>No session data</strong>Core did not return any active session records.</div></div>';
        return;
      }
      status.textContent = `${sessions.length} session record${sessions.length === 1 ? "" : "s"} returned by Core.`;
      list.innerHTML = sessions.map((session) => `<article class="session-item"><div><strong>${escapeHtml(session.device || session.device_name || "Phoenix session")}</strong><span>${escapeHtml(session.location || session.ip_address || "Location not supplied")}</span></div><div><span>${escapeHtml(session.status || "Active")}</span><small>${escapeHtml(session.last_seen || session.last_activity || "Last activity not supplied")}</small></div></article>`).join("");
    } catch (error) {
      status.className = "status error";
      status.textContent = error?.message || "Core session information is unavailable.";
      list.innerHTML = '<div class="empty-state"><div><strong>Session service unavailable</strong>No session information has been fabricated or inferred.</div></div>';
    }
  };
  workspaceView.querySelector("[data-refresh]").addEventListener("click", load);
  await load();
}
