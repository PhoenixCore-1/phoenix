import {
  PRODUCTION_ACTIONS,
  executeProductionAction,
  getProductionContract,
  getProductionOrder,
  getProductionStages
} from "./production-module-adapter.js";

/* Production Order Detail workspace.
 * The UI may request an action, but Core/API and the Production module remain
 * authoritative for permission, tenant, state, validation and completion.
 */

export async function renderProductionOrderDetailWorkspace({ workspaceView, module, orderId }) {
  const contract = getProductionContract(module);
  workspaceView.innerHTML = detailLoadingMarkup(contract, orderId);

  try {
    const [orderResult, stagesResult] = await Promise.all([
      getProductionOrder(orderId),
      getProductionStages(orderId)
    ]);
    const order = normalizeOrder(orderResult, orderId);
    const stages = normalizeStages(stagesResult);
    workspaceView.innerHTML = detailMarkup(contract, order, stages);
    bindDetailNavigation(workspaceView);
    bindActions(workspaceView, order);
  } catch (error) {
    workspaceView.innerHTML = detailErrorMarkup(contract, orderId, error?.message);
    workspaceView.querySelector("[data-production-detail-back]")?.addEventListener("click", () => goBackToOrders(workspaceView));
  }
}

function detailLoadingMarkup(contract, orderId) {
  return `<header class="workspace-header"><div><p class="eyebrow">${escapeHtml(contract.name)}</p><h1 class="workspace-title">Production Order</h1><p class="workspace-subtitle">Loading authorized order ${escapeHtml(orderId)}…</p></div><div class="workspace-meta"><span class="status-pill">Module ${escapeHtml(contract.version)}</span></div></header><section class="card panel"><div class="table-state">Loading Production Order details…</div></section>`;
}

function detailMarkup(contract, order, stages) {
  return `<header class="workspace-header"><div><p class="eyebrow">${escapeHtml(contract.name)}</p><h1 class="workspace-title">${escapeHtml(order.orderNumber)}</h1><p class="workspace-subtitle">Production Order detail and stage context.</p></div><div class="workspace-meta"><span class="status-pill">${escapeHtml(order.state)}</span><span class="status-pill">Module ${escapeHtml(contract.version)}</span></div></header>
    <div class="workspace-actions"><button class="button-secondary" type="button" data-production-detail-back>← Production Orders</button></div>
    <section class="content-grid production-order-detail-grid"><article class="card panel"><h2 class="panel-title">Order Summary</h2><div class="detail-grid">${detailItem("Product", order.product)}${detailItem("Customer", order.customer)}${detailItem("Quantity", order.quantity)}${detailItem("Current Stage", order.stage)}${detailItem("Status", order.state)}${detailItem("ETA", order.eta)}${detailItem("Planned Completion", order.plannedCompletion)}${detailItem("Actual Completion", order.actualCompletion)}</div></article>
      <article class="card panel"><h2 class="panel-title">Production Stages</h2><p class="panel-subtitle">Stage progress supplied by the Production service.</p><div class="production-stage-list" aria-label="Production stages">${stages.length ? stages.map(stageMarkup).join("") : stageEmptyMarkup()}</div></article></section>
    <section class="card panel" aria-labelledby="production-actions-title"><h2 class="panel-title" id="production-actions-title">Actions</h2><p class="panel-subtitle">Available actions are presented from the authorized module contract. Final permission and state validation occurs on the server.</p><div class="production-action-bar" data-production-actions>${actionButtons(contract)}</div><div class="action-feedback" data-production-action-feedback aria-live="polite"></div></section>`;
}

function actionButtons(contract) {
  const declared = new Set(contract.actions.map(normalizeActionName));
  const permissionMap = { release: "production.manage", start: "production.operate", hold: "production.hold", resume: "production.resume", complete: "production.operate" };
  const labels = { release: "Release", start: "Start", hold: "Hold", resume: "Resume", complete: "Complete" };
  return PRODUCTION_ACTIONS.map((action) => {
    const declaredByServer = declared.size === 0 || declared.has(action);
    const permitted = contract.permissions.includes(permissionMap[action]);
    const available = declaredByServer && permitted;
    return `<button class="button-primary production-action" type="button" data-production-action="${action}" ${available ? "" : "disabled"}>${labels[action]}</button>`;
  }).join("");
}

function bindActions(workspaceView, order) {
  workspaceView.querySelectorAll("[data-production-action]").forEach((button) => button.addEventListener("click", async () => {
    const action = button.dataset.productionAction;
    if (!action || button.disabled) return;
    const feedback = workspaceView.querySelector("[data-production-action-feedback]");
    if (["hold", "complete"].includes(action) && !window.confirm(`Confirm ${action} for ${order.orderNumber}? The Production service will validate the request before any change is made.`)) return;
    setActionBusy(workspaceView, true);
    showActionFeedback(feedback, "info", `${formatAction(action)} requested. Waiting for server validation…`);
    try {
      const result = await executeProductionAction(action, order.id);
      showActionFeedback(feedback, "success", actionResultMessage(result, action));
      window.dispatchEvent(new CustomEvent("phoenix:production-action-result", { detail: { action, orderId: order.id, result } }));
    } catch (error) {
      showActionFeedback(feedback, "error", `The ${formatAction(action).toLowerCase()} request was not completed. ${error?.message || "Server validation failed."}`);
    } finally {
      setActionBusy(workspaceView, false);
    }
  }));
}

function setActionBusy(workspaceView, busy) {
  workspaceView.querySelectorAll("[data-production-action]").forEach((button) => { button.disabled = busy; });
}

function showActionFeedback(element, type, message) {
  if (!element) return;
  element.className = `action-feedback ${type}`;
  element.textContent = message;
}

function actionResultMessage(result, action) {
  const status = result?.status ?? result?.result ?? result?.state;
  if (status) return `${formatAction(action)} response: ${status}. Server response is authoritative.`;
  return `${formatAction(action)} request accepted by the service boundary. Server response is authoritative.`;
}

function formatAction(action) { return action.charAt(0).toUpperCase() + action.slice(1); }
function normalizeActionName(action) {
  if (typeof action === "string") return action.toLowerCase();
  if (action && typeof action.code === "string") return action.code.toLowerCase();
  if (action && typeof action.action === "string") return action.action.toLowerCase();
  return "";
}

function detailErrorMarkup(contract, orderId, message) {
  return `<header class="workspace-header"><div><p class="eyebrow">${escapeHtml(contract.name)}</p><h1 class="workspace-title">Production Order</h1><p class="workspace-subtitle">Order ${escapeHtml(orderId)}</p></div></header><section class="card panel"><div class="status error" role="alert"><strong>Production Order unavailable.</strong> ${escapeHtml(message || "The order could not be loaded through the authorized service boundary.")}</div><div class="workspace-actions"><button class="button-secondary" type="button" data-production-detail-back>← Production Orders</button></div><p class="panel-subtitle">No transaction has been performed.</p></section>`;
}

function normalizeOrder(result, fallbackId) {
  const source = result?.order ?? result ?? {};
  return { id: source.id ?? source.order_id ?? fallbackId, orderNumber: source.orderNumber ?? source.order_number ?? source.id ?? fallbackId, product: source.productName ?? source.product_name ?? source.product ?? "—", customer: source.customerName ?? source.customer_name ?? source.customer ?? "—", quantity: source.quantity ?? source.order_quantity ?? "—", stage: source.currentStage ?? source.current_stage ?? source.stage ?? "—", state: source.state ?? source.status ?? "—", eta: source.eta ?? source.estimated_completion ?? source.planned_completion ?? "—", plannedCompletion: source.planned_completion ?? source.plannedCompletion ?? "—", actualCompletion: source.actual_completion ?? source.actualCompletion ?? "—" };
}

function normalizeStages(result) {
  const source = Array.isArray(result) ? result : result?.stages;
  if (!Array.isArray(source)) return [];
  return source.filter(Boolean).map((stage, index) => ({ name: stage.name ?? stage.stageName ?? stage.stage_name ?? stage.code ?? `Stage ${index + 1}`, state: stage.state ?? stage.status ?? "—", quantity: stage.quantity ?? stage.completed_quantity ?? stage.actual_quantity ?? "—", planned: stage.planned_quantity ?? stage.plannedQuantity ?? "—", eta: stage.eta ?? stage.estimated_completion ?? "—" }));
}

function stageMarkup(stage) {
  return `<div class="production-stage-item"><div><strong>${escapeHtml(stage.name)}</strong><span>${escapeHtml(stage.state)}</span></div><div><span>Quantity</span><strong>${escapeHtml(stage.quantity)}</strong></div><div><span>Planned</span><strong>${escapeHtml(stage.planned)}</strong></div><div><span>ETA</span><strong>${escapeHtml(stage.eta)}</strong></div></div>`;
}
function stageEmptyMarkup() { return `<div class="empty-state"><div><strong>No stage data returned</strong>The Production service did not provide stage records for this order.</div></div>`; }
function detailItem(label, value) { return `<div class="detail-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`; }
function bindDetailNavigation(workspaceView) { workspaceView.querySelector("[data-production-detail-back]")?.addEventListener("click", () => goBackToOrders(workspaceView)); }
function goBackToOrders(workspaceView) { workspaceView.dispatchEvent(new CustomEvent("phoenix:production-orders-back", { bubbles: true })); }
function escapeHtml(value) { return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;"); }
