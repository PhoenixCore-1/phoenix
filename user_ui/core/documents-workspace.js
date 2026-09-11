import { coreServiceAdapter } from "./core-service-adapter.js";

/* Phoenix User UI V0.1 — Documents workspace.
 * Presentation only. Tenant scope, permission checks and document access remain
 * authoritative in Phoenix Core/API.
 */

export async function renderDocumentsWorkspace({ workspaceView }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">Documents</h1>
        <p class="workspace-subtitle">Access documents available to you within the current tenant context.</p>
      </div>
      <div class="workspace-meta"><span class="status-pill">Core-backed</span></div>
    </header>
    <section class="card panel">
      <div class="documents-toolbar">
        <label class="documents-search">
          <span class="sr-only">Search documents</span>
          <input id="documents-search" type="search" placeholder="Search documents…" autocomplete="off">
        </label>
        <button id="documents-refresh" class="button-secondary" type="button">Refresh</button>
      </div>
      <div id="documents-status" class="status info" role="status" aria-live="polite">Document service not connected.</div>
      <div id="documents-content"></div>
    </section>
  `;

  const status = workspaceView.querySelector("#documents-status");
  const content = workspaceView.querySelector("#documents-content");
  const search = workspaceView.querySelector("#documents-search");
  const refresh = workspaceView.querySelector("#documents-refresh");

  const load = async () => {
    refresh.disabled = true;
    status.className = "status info";
    status.textContent = "Loading documents from Phoenix Core…";
    content.innerHTML = `<div class="table-state">Loading documents…</div>`;

    try {
      const result = await coreServiceAdapter.getDocuments({ query: search.value.trim() });
      const documents = normalizeDocuments(result);
      status.className = "status success";
      status.textContent = `${documents.length} document${documents.length === 1 ? "" : "s"} returned.`;
      content.innerHTML = documents.length ? documentsMarkup(documents) : emptyMarkup();
    } catch (error) {
      status.className = "status error";
      status.innerHTML = `<strong>Documents could not be loaded.</strong> ${escapeHtml(error?.message || "The Core document service is unavailable.")}`;
      content.innerHTML = `<div class="empty-state"><div><strong>No false success</strong>No document access was assumed. Retry when the Core document API is available.</div></div>`;
    } finally {
      refresh.disabled = false;
    }
  };

  refresh.addEventListener("click", load);
  search.addEventListener("keydown", (event) => { if (event.key === "Enter") load(); });
  await load();
}

function normalizeDocuments(result) {
  const source = Array.isArray(result) ? result : result?.documents;
  if (!Array.isArray(source)) return [];
  return source.filter(Boolean).map((document) => ({
    id: document.id ?? document.document_id ?? "",
    name: document.name ?? document.title ?? document.filename ?? "Untitled document",
    type: document.type ?? document.mime_type ?? document.content_type ?? "—",
    size: document.size ?? document.file_size ?? "—",
    updated: document.updated_at ?? document.modified_at ?? document.created_at ?? "—"
  }));
}

function documentsMarkup(documents) {
  return `<div class="table-scroll"><table class="data-table"><caption class="sr-only">Available Documents</caption><thead><tr><th scope="col">Document</th><th scope="col">Type</th><th scope="col">Size</th><th scope="col">Updated</th><th scope="col"><span class="sr-only">Action</span></th></tr></thead><tbody>${documents.map((document) => `<tr><td><strong>${escapeHtml(document.name)}</strong></td><td>${escapeHtml(document.type)}</td><td>${escapeHtml(document.size)}</td><td>${escapeHtml(document.updated)}</td><td><button type="button" class="table-link" disabled title="Document opening will be connected through the Core document service">Open</button></td></tr>`).join("")}</tbody></table></div>`;
}

function emptyMarkup() { return `<div class="empty-state"><div><strong>No documents available</strong>Core returned no documents for the current authorized context.</div></div>`; }
function escapeHtml(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
