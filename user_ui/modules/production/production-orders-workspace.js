import {
  listProductionOrders,
  getProductionContract
} from "./production-module-adapter.js";

/* Production Orders workspace.
 * UI owns presentation and interaction only. Data and business rules remain
 * behind the Phoenix Core/API Production service boundary.
 */

export async function renderProductionOrdersWorkspace({ workspaceView, module }) {
  const contract = getProductionContract(module);
  workspaceView.innerHTML = ordersShellMarkup(contract);

  const tableBody = workspaceView.querySelector("#production-orders-body");
  const status = workspaceView.querySelector("#production-orders-status");
  const search = workspaceView.querySelector("#production-orders-search");
  const stateFilter = workspaceView.querySelector("#production-orders-state");

  const load = async () => {
    setStatus(status, "Loading Production Orders…", "info");
    tableBody.innerHTML = loadingRow();

    try {
      const result = await listProductionOrders({
        search: search.value.trim(),
        state: stateFilter.value || undefined
      });
      const orders = normalizeOrders(result);
      tableBody.innerHTML = orders.length ? orders.map(orderRow).join("") : emptyRow();
      setStatus(status, `${orders.length} order${orders.length === 1 ? "" : "s"} returned.`, "success");
      bindOrderSelection(workspaceView);
    } catch (error) {
      tableBody.innerHTML = errorRow();
      setStatus(status, error?.message || "Production Orders could not be loaded.", "error");
    }
  };

  workspaceView.querySelector("#production-orders-refresh").addEventListener("click", load);
  search.addEventListener("keydown", (event) => {
    if (event.key === "Enter") load();
  });
  stateFilter.addEventListener("change", load);

  await load();
}

function ordersShellMarkup(contract) {
  return `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">${escapeHtml(contract.name)}</p>
        <h1 class="workspace-title">Production Orders</h1>
        <p class="workspace-subtitle">View and open authorized manufacturing orders.</p>
      </div>
      <div class="workspace-meta"><span class="status-pill">Module ${escapeHtml(contract.version)}</span></div>
    </header>

    <section class="card panel production-orders-panel">
      <div class="production-orders-toolbar">
        <label class="production-orders-search">
          <span class="sr-only">Search Production Orders</span>
          <input id="production-orders-search" type="search" placeholder="Search order, product or customer…" autocomplete="off">
        </label>
        <label>
          <span class="sr-only">Filter by status</span>
          <select id="production-orders-state">
            <option value="">All statuses</option>
            <option value="PLANNED">Planned</option>
            <option value="RELEASED">Released</option>
            <option value="STARTED">Started</option>
            <option value="HOLD">On Hold</option>
            <option value="COMPLETED">Completed</option>
            <option value="CANCELLED">Cancelled</option>
          </select>
        </label>
        <button id="production-orders-refresh" class="button-secondary" type="button">Refresh</button>
      </div>

      <div id="production-orders-status" class="status info" role="status" aria-live="polite">Loading Production Orders…</div>

      <div class="table-scroll">
        <table class="data-table">
          <caption class="sr-only">Production Orders</caption>
          <thead>
            <tr>
              <th scope="col">Order</th>
              <th scope="col">Product</th>
              <th scope="col">Quantity</th>
              <th scope="col">Stage</th>
              <th scope="col">Status</th>
              <th scope="col">ETA</th>
              <th scope="col"><span class="sr-only">Open</span></th>
            </tr>
          </thead>
          <tbody id="production-orders-body">${loadingRow()}</tbody>
        </table>
      </div>
    </section>
  `;
}

function normalizeOrders(result) {
  const source = Array.isArray(result) ? result : result?.orders;
  if (!Array.isArray(source)) return [];
  return source.filter(Boolean).map((order) => ({
    id: order.id ?? order.order_id ?? order.orderNumber ?? order.order_number ?? "",
    orderNumber: order.orderNumber ?? order.order_number ?? order.id ?? "—",
    product: order.productName ?? order.product_name ?? order.product ?? "—",
    quantity: order.quantity ?? order.order_quantity ?? "—",
    stage: order.currentStage ?? order.current_stage ?? order.stage ?? "—",
    state: order.state ?? order.status ?? "—",
    eta: order.eta ?? order.estimated_completion ?? order.planned_completion ?? "—"
  }));
}

function orderRow(order) {
  return `<tr data-production-order-id="${escapeHtml(order.id)}" tabindex="0">
    <td><strong>${escapeHtml(order.orderNumber)}</strong></td>
    <td>${escapeHtml(order.product)}</td>
    <td>${escapeHtml(order.quantity)}</td>
    <td>${escapeHtml(order.stage)}</td>
    <td><span class="status-pill status-${escapeHtml(String(order.state).toLowerCase())}">${escapeHtml(order.state)}</span></td>
    <td>${escapeHtml(order.eta)}</td>
    <td><button class="table-link" type="button" data-open-production-order="${escapeHtml(order.id)}">Open</button></td>
  </tr>`;
}

function bindOrderSelection(workspaceView) {
  workspaceView.querySelectorAll("[data-open-production-order]").forEach((button) => {
    button.addEventListener("click", () => openOrder(workspaceView, button.dataset.openProductionOrder));
  });
  workspaceView.querySelectorAll("tr[data-production-order-id]").forEach((row) => {
    row.addEventListener("dblclick", () => openOrder(workspaceView, row.dataset.productionOrderId));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter") openOrder(workspaceView, row.dataset.productionOrderId);
    });
  });
}

function openOrder(workspaceView, orderId) {
  workspaceView.dispatchEvent(new CustomEvent("phoenix:production-order-open", {
    bubbles: true,
    detail: { orderId }
  }));
}

function setStatus(element, message, type) {
  element.className = `status ${type}`;
  element.textContent = message;
}

function loadingRow() {
  return `<tr><td colspan="7"><div class="table-state">Loading Production Orders…</div></td></tr>`;
}

function emptyRow() {
  return `<tr><td colspan="7"><div class="table-state"><strong>No Production Orders found</strong>Try another search or status filter.</div></td></tr>`;
}

function errorRow() {
  return `<tr><td colspan="7"><div class="table-state"><strong>Production Orders unavailable</strong>Retry using Refresh. No transaction has been performed.</div></td></tr>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
