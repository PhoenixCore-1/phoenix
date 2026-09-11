import { runCoreIntegrationChecks } from "./integration-test-runner.js";
import { getHostModuleCatalog } from "./module-registry-adapter.js";

/* Phoenix User UI V0.1 — runtime integration verification workspace. */

function esc(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
}

export async function renderIntegrationTestWorkspace({ workspaceView, coreServiceAdapter }) {
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">Integration Tests</h1><p class="workspace-subtitle">Runtime checks for the User UI/Core boundary.</p></div></header><section class="card panel"><div class="table-state">Running Core integration checks…</div></section>`;

  const results = await runCoreIntegrationChecks({
    coreServiceAdapter,
    moduleCatalogAdapter: () => getHostModuleCatalog()
  });
  const passed = results.filter((result) => result.passed).length;

  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">Integration Tests</h1><p class="workspace-subtitle">Runtime checks for the User UI/Core boundary.</p></div><div class="workspace-meta"><span class="status-pill">${passed}/${results.length} passed</span></div></header><section class="card panel"><h2 class="panel-title">Core boundary results</h2><p class="panel-subtitle">These results are evidence from the current runtime; they do not replace security testing or server-side controls.</p><div class="security-check-list">${results.map((result) => `<article class="security-check ${result.passed ? "passed" : "failed"}"><div class="security-check-mark" aria-hidden="true">${result.passed ? "✓" : "!"}</div><div><strong>${esc(result.id)} — ${esc(result.label)}</strong><span>${esc(result.detail)}</span></div><span class="status-pill">${result.passed ? "PASS" : "CHECK"}</span></article>`).join("")}</div></section>`;
}
