import { runUserUiSecurityChecks } from "./user-ui-security-checks.js";

/* Phoenix User UI V0.1 — security/integration verification workspace. */

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
}

export function renderSecurityWorkspace({ workspaceView, session, authorizedModules }) {
  const checks = runUserUiSecurityChecks({ session, authorizedModules });
  const passed = checks.filter((check) => check.passed).length;

  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">Security &amp; Integration</h1>
        <p class="workspace-subtitle">User UI boundary verification. Server-side security remains authoritative.</p>
      </div>
      <div class="workspace-meta"><span class="status-pill">${passed}/${checks.length} UI checks passed</span></div>
    </header>
    <section class="card panel">
      <h2 class="panel-title">Boundary checks</h2>
      <p class="panel-subtitle">These checks provide integration evidence; they do not grant access or replace Core controls.</p>
      <div class="security-check-list">
        ${checks.map((check) => `
          <article class="security-check ${check.passed ? "passed" : "failed"}">
            <div class="security-check-mark" aria-hidden="true">${check.passed ? "✓" : "!"}</div>
            <div><strong>${escapeHtml(check.label)}</strong><span>${escapeHtml(check.detail)}</span></div>
            <span class="status-pill">${check.passed ? "PASS" : "CHECK"}</span>
          </article>
        `).join("")}
      </div>
    </section>
    <section class="content-grid security-principles">
      <article class="card panel"><h2 class="panel-title">Authoritative controls</h2><p class="panel-subtitle">Owned outside the browser</p><ul class="security-list"><li>Authentication and session validity</li><li>Tenant isolation</li><li>Server-side authorization and permissions</li><li>Module registration and access</li><li>Business transaction validation</li></ul></article>
      <article class="card panel"><h2 class="panel-title">UI integration rules</h2><p class="panel-subtitle">Required for User UI V0.1</p><ul class="security-list"><li>No direct database connections</li><li>No client-side authorization decisions</li><li>No false transaction success</li><li>Explicit loading, empty and error states</li><li>Server-authoritative action results</li></ul></article>
    </section>`;
}
