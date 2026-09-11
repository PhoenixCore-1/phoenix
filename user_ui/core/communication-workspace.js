/* Phoenix User UI V0.1 — Core communication workspace. */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeMessages(response) {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.messages)) return response.messages;
  if (Array.isArray(response?.items)) return response.items;
  return [];
}

export function renderCommunicationWorkspace({ workspaceView, coreServiceAdapter }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">Communication</h1>
        <p class="workspace-subtitle">Access authorised communication through the Core service boundary.</p>
      </div>
    </header>
    <section class="card panel communication-workspace">
      <div class="communication-toolbar">
        <div>
          <strong>Communication context</strong>
          <p class="muted">Messages and related communication are supplied by Phoenix Core. This workspace does not access business databases directly.</p>
        </div>
        <button class="button secondary" type="button" data-communication-refresh>Refresh</button>
      </div>
      <div class="status" data-communication-status role="status" aria-live="polite">Loading communication...</div>
      <section class="communication-list" data-communication-list aria-live="polite"></section>
    </section>
  `;

  const status = workspaceView.querySelector("[data-communication-status]");
  const list = workspaceView.querySelector("[data-communication-list]");
  const refresh = workspaceView.querySelector("[data-communication-refresh]");

  async function load() {
    refresh.disabled = true;
    status.className = "status loading";
    status.textContent = "Loading communication...";
    list.replaceChildren();

    try {
      const response = await coreServiceAdapter.getCommunicationContext();
      const messages = normalizeMessages(response);
      if (messages.length === 0) {
        status.className = "status";
        status.textContent = "No communication is available for this User UI session.";
        list.innerHTML = `<div class="empty-state"><div><strong>No communication</strong><div class="muted">There are no authorised communication items to display.</div></div></div>`;
        return;
      }

      status.className = "status success";
      status.textContent = `${messages.length} communication item${messages.length === 1 ? "" : "s"} loaded.`;
      list.innerHTML = messages.map((item) => `
        <article class="communication-item">
          <div class="communication-main">
            <strong>${escapeHtml(item.subject || item.title || "Communication")}</strong>
            <div>${escapeHtml(item.body || item.message || item.preview || "")}</div>
          </div>
          <div class="communication-meta">
            <span>${escapeHtml(item.sender || item.from || "")}</span>
            <span>${escapeHtml(item.created_at || item.timestamp || "")}</span>
          </div>
        </article>
      `).join("");
    } catch (error) {
      status.className = "status error";
      status.textContent = error?.message || "Communication is currently unavailable.";
      list.innerHTML = `<div class="empty-state"><div><strong>Communication unavailable</strong><div class="muted">No fallback or fabricated communication data is shown.</div></div></div>`;
    } finally {
      refresh.disabled = false;
    }
  }

  refresh.addEventListener("click", load);
  load();
}
