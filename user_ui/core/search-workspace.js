import { coreServiceAdapter } from "./core-service-adapter.js";

/* Phoenix User UI V0.1 — Global Search workspace.
 * Search is permission-aware and Core-authoritative. The UI never queries storage.
 */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export async function renderSearchWorkspace({ workspaceView }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">Global Search</h1>
        <p class="workspace-subtitle">Search content you are authorized to access in the current tenant.</p>
      </div>
      <div class="workspace-meta"><span class="status-pill">Core-backed</span></div>
    </header>
    <section class="card panel search-panel">
      <form id="global-search-form" class="search-toolbar">
        <label class="search-input-wrap">
          <span class="sr-only">Search Phoenix</span>
          <input id="global-search-input" type="search" placeholder="Search orders, documents, customers or other authorized content…" autocomplete="off" required>
        </label>
        <button class="button-primary" type="submit">Search</button>
      </form>
      <div id="global-search-status" class="status info" role="status" aria-live="polite">Enter a search term to begin.</div>
    </section>
    <section class="card panel">
      <div class="panel-heading-row"><div><h2 class="panel-title">Results</h2><p class="panel-subtitle">Results are supplied and permission-filtered by Phoenix Core.</p></div></div>
      <div id="global-search-results"><div class="table-state">No search performed.</div></div>
    </section>
  `;

  const form = workspaceView.querySelector("#global-search-form");
  const input = workspaceView.querySelector("#global-search-input");
  const status = workspaceView.querySelector("#global-search-status");
  const results = workspaceView.querySelector("#global-search-results");

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const query = input.value.trim();
    if (!query) return;
    status.className = "status info";
    status.textContent = "Searching Phoenix Core…";
    results.innerHTML = `<div class="table-state">Searching authorized content…</div>`;

    try {
      const response = await coreServiceAdapter.search({ query });
      const items = normalizeResults(response);
      status.className = "status success";
      status.textContent = `${items.length} result${items.length === 1 ? "" : "s"} returned.`;
      results.innerHTML = items.length ? items.map(resultMarkup).join("") : `<div class="table-state"><strong>No results found</strong>Try a different search term.</div>`;
    } catch (error) {
      status.className = "status error";
      status.textContent = "Search is not currently available through Phoenix Core.";
      results.innerHTML = `<div class="table-state"><strong>No false success</strong>${escapeHtml(error?.message || "The Search service endpoint is not connected yet.")}</div>`;
    }
  });
}

function normalizeResults(response) {
  const source = Array.isArray(response) ? response : response?.results ?? response?.items;
  if (!Array.isArray(source)) return [];
  return source.filter(Boolean).map((item) => ({
    title: item.title ?? item.name ?? item.label ?? item.id ?? "Result",
    type: item.type ?? item.entity_type ?? item.kind ?? "Content",
    description: item.description ?? item.summary ?? item.snippet ?? "",
    id: item.id ?? item.entity_id ?? ""
  }));
}

function resultMarkup(item) {
  return `<article class="work-item search-result-item"><div class="work-item-main"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.description)}</span></div><div class="work-item-meta"><span>${escapeHtml(item.type)}</span>${item.id ? `<span>${escapeHtml(item.id)}</span>` : ""}</div></article>`;
}
