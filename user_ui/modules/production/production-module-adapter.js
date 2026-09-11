/* Phoenix User UI -> Production integration boundary.
 *
 * The adapter never imports the Python Production package and never opens
 * the database. It consumes the existing Phoenix Core HTTP API, while still
 * allowing a host application to inject window.PhoenixCoreApi.production.
 */

import { getCoreRequest } from "../../core/core-service-adapter.js";

export const PRODUCTION_MODULE_CODE = "production";
export const PRODUCTION_UI_CONTRACT_VERSION = "1.0";

export const PRODUCTION_ACTIONS = Object.freeze([
  "release",
  "start",
  "hold",
  "resume",
  "complete"
]);

const CORE_PRODUCTION_BASE = "/api/production";

export function getProductionContract(moduleMetadata) {
  if (!moduleMetadata || moduleMetadata.code !== PRODUCTION_MODULE_CODE) {
    throw new Error("Production module is not available in this session.");
  }

  return {
    code: PRODUCTION_MODULE_CODE,
    name: moduleMetadata.name || "Production",
    version: moduleMetadata.version || "—",
    uiContractVersion: PRODUCTION_UI_CONTRACT_VERSION,
    menu: Array.isArray(moduleMetadata.menu) ? moduleMetadata.menu : [],
    permissions: Array.isArray(moduleMetadata.permissions) ? moduleMetadata.permissions : [],
    actions: Array.isArray(moduleMetadata.actions) ? moduleMetadata.actions : []
  };
}

function coreHttpProductionApi() {
  const request = getCoreRequest();

  return {
    async listOrders(query = {}) {
      const params = new URLSearchParams();
      if (query.search) params.set("q", query.search);
      return request(`${CORE_PRODUCTION_BASE}/orders${params.toString() ? `?${params}` : ""}`);
    },

    async getOrder(orderId) {
      return request(`${CORE_PRODUCTION_BASE}/orders/${encodeURIComponent(orderId)}`);
    },

    async getStages(orderId) {
      const order = await request(`${CORE_PRODUCTION_BASE}/orders/${encodeURIComponent(orderId)}`);
      return order?.stages || [];
    },

    async executeAction({ action, orderId, payload = {}, idempotencyKey, correlationId }) {
      const headers = {
        "X-Phoenix-Idempotency-Key": idempotencyKey,
        "X-Phoenix-Correlation-Id": correlationId
      };
      const id = encodeURIComponent(orderId);

      if (action === "release") {
        return request(`${CORE_PRODUCTION_BASE}/orders/${id}/release`, {
          method: "POST",
          headers,
          body: "{}"
        });
      }

      if (action === "start") {
        return request(`${CORE_PRODUCTION_BASE}/orders/${id}/start`, {
          method: "POST",
          headers,
          body: "{}"
        });
      }

      const stageId = payload.stageId ?? payload.stage_id;
      if (!stageId) throw new Error(`Production ${action} requires the current stage.`);

      if (action === "hold") {
        return request(`${CORE_PRODUCTION_BASE}/orders/${id}/stages/${encodeURIComponent(stageId)}/hold`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            problem_type: payload.problemType || payload.problem_type || "Production Problem",
            description: payload.reason || payload.description || "Production hold requested",
            affected_quantity: payload.affectedQuantity ?? payload.affected_quantity ?? 0
          })
        });
      }

      if (action === "resume") {
        return request(`${CORE_PRODUCTION_BASE}/orders/${id}/stages/${encodeURIComponent(stageId)}/resume`, {
          method: "POST",
          headers,
          body: JSON.stringify({ resolution: payload.resolution || "Production resumed" })
        });
      }

      if (action === "complete") {
        return request(`${CORE_PRODUCTION_BASE}/orders/${id}/stages/${encodeURIComponent(stageId)}/finish`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            completed_qty: payload.completedQty ?? payload.completed_qty ?? 0,
            rejected_qty: payload.rejectedQty ?? payload.rejected_qty ?? 0,
            notes: payload.notes || ""
          })
        });
      }

      throw new Error("Unsupported Production action.");
    }
  };
}

export function getProductionApi() {
  return window.PhoenixCoreApi?.production || coreHttpProductionApi();
}

export function productionServiceState() {
  return getProductionApi() ? "connected" : "not-connected";
}

export async function listProductionOrders(query = {}) {
  const api = getProductionApi();
  if (!api?.listOrders) throw new Error("Production Orders service is not connected.");
  return api.listOrders(query);
}

export async function getProductionOrder(orderId) {
  const api = getProductionApi();
  if (!api?.getOrder) throw new Error("Production Order service is not connected.");
  return api.getOrder(orderId);
}

export async function getProductionStages(orderId) {
  const api = getProductionApi();
  if (!api?.getStages) throw new Error("Production Stages service is not connected.");
  return api.getStages(orderId);
}

export async function executeProductionAction(action, orderId, payload = {}) {
  if (!PRODUCTION_ACTIONS.includes(action)) throw new Error("Unsupported Production action.");

  const api = getProductionApi();
  if (!api?.executeAction) throw new Error("Production action service is not connected.");

  return api.executeAction({
    action,
    orderId,
    payload,
    idempotencyKey: crypto.randomUUID(),
    correlationId: crypto.randomUUID()
  });
}