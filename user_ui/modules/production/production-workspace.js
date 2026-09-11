import {
  getProductionContract,
  productionServiceState
} from "./production-module-adapter.js";
import { renderProductionOrdersWorkspace } from "./production-orders-workspace.js";

/* Production module workspace renderer.
 * Business rules remain in the Production Module. This file owns only
 * User UI presentation and navigation within the Production workspace.
 */

export function renderProductionWorkspace({ workspaceView, module }) {
  const contract = getProductionContract(module);
  const serviceState = productionServiceState();

  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Module</p>
        <h1 class="workspace-title">${escapeHtml(contract.name)}</h1>
        <p class="workspace-subtitle">Manufacturing and production operations for your authorized workspace.</p>
      </div>
      <div class="workspace-meta" aria-label="Module status">
        <span class="status-pill">Version ${escapeHtml(contract.version)}</span>
        <span class="status-pill">${serviceState === "connected" ? "Service connected" : "Service pending"}</span>
      </div>
    </header>

    <nav class="workspace-tabs" aria-label="Production workspace">
      <button class="workspace-tab active" type="button" data-production-route="home">Overview</button>
      <button class="workspace-tab" type="button" data-production-route="orders">Production Orders</button>
    </nav>

    <section class="card panel" id="production-workspace-panel">
      ${productionOverviewMarkup(serviceState)}
    </section>
  `;

  workspaceView.querySelectorAll("[data-production-route]").forEach((button) => {
    button.addEventListener("click", async () => {
      workspaceView.querySelectorAll("[data-production-route]").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const panel = workspaceView.querySelector("#production-workspace-panel");

      if (button.dataset.productionRoute === "orders") {
        await renderProductionOrdersWorkspace({ workspaceView: panel, module });
        return;
      }

      panel.innerHTML = productionOverviewMarkup(productionServiceState());
    });
  });
}

function productionOverviewMarkup(serviceState) {
  if (serviceState !== "connected") {
    return `
      <div class="module-summary-grid">
        <div><span class="kpi-label">Production Orders</span><strong class="kpi-value">—</strong><span class="kpi-note">Awaiting Core/API data</span></div>
        <div><span class="kpi-label">In Production</span><strong class="kpi-value">—</strong><span class="kpi-note">Awaiting Core/API data</span></div>
        <div><span class="kpi-label">On Hold</span><strong class="kpi-value">—</strong><span class="kpi-note">Awaiting Core/API data</span></div>
        <div><span class="kpi-label">Attention</span><strong class="kpi-value">—</strong><span class="kpi-note">Awaiting Core/API data</span></div>
      </div>
      <div class="empty-state">
        <div><strong>Production service not connected</strong>Live Production data will be retrieved through the Phoenix Core/API module boundary.</div>
      </div>
    `;
  }

  return `
    <div class="empty-state">
      <div><strong>Production workspace connected</strong>Production data is available through the module service boundary.</div>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
