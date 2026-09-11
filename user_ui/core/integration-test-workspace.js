import { runCoreIntegrationChecks } from "./integration-test-runner.js";
import { getHostModuleCatalog } from "./module-registry-adapter.js";

/* Phoenix User UI V0.1 — runtime integration verification workspace. */

function esc(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
}

export async function renderIntegrationTestWorkspace({ workspaceView, coreServiceAdapter }) {
  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">Integration Tests</h1><p class="workspace-subtitle">Runtime checks for the User UI/Core boundary.</p></div></header><section class="card panel"><div class="table-state">Running Core integration checks…</div></section>`;

  let results;
  try {
    results = await runCoreIntegrationChecks({
      coreServiceAdapter,
      moduleCatalogAdapter: () => getHostModuleCatalog()
    });
  } catch (error) {
    results = [{ id: "HARNESS", label: "Integration harness", state: "BLOCKED", passed: false, detail: error?.message || "The integration harness could not complete." }];
  }

  const passed = results.filter((item) => item.state === "PASS").length;
  const failed = results.filter((item) => item.state === "FAIL").length;
  const blocked = results.filter((item) => item.state === "BLOCKED").length;
  const statusClass = failed ? "error" : blocked ? "info" : "";
  const gateLabel = failed ? "FAIL" : blocked ? "BLOCKED" : "PASS";

  workspaceView.innerHTML = `<header class="workspace-header"><div><p class="eyebrow">Phoenix Core</p><h1 class="workspace-title">Integration Tests</h1><p class="workspace-subtitle">Runtime checks for the User UI/Core boundary.</p></div><div class="workspace-meta"><span class="status-pill">Gate: ${gateLabel}</span><span class="status-pill">${passed} pass · ${failed} fail · ${blocked} blocked</span></div></header><section class="card panel"><div class="status ${statusClass}"><strong>Release gate: ${gateLabel}.</strong> PASS means verified; FAIL means executed and failed; BLOCKED means the required runtime capability was unavailable.</div><h2 class="panel-title">Core boundary results</h2><p class="panel-subtitle">These results are evidence from the current runtime; they do not replace security testing or server-side controls.</p><div class="security-check-list">${results.map((item) => { const state = item.state || (item.passed ? "PASS" : "FAIL"); const ok = state === "PASS"; return `<article class="security-check ${state.toLowerCase()}"><div class="security-check-mark" aria-hidden="true">${ok ? "✓" : state === "BLOCKED" ? "~" : "!"}</div><div><strong>${esc(item.id)} — ${esc(item.label)}</strong><span>${esc(item.detail)}</span></div><span class="status-pill">${esc(state)}</span></article>`; }).join("")}</div></section>`;
}
