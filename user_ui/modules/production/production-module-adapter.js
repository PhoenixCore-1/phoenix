/* Phoenix User UI -> Production integration boundary.
 *
 * This adapter is deliberately UI-facing only. It does not import the
 * Python Production package, open a database, or implement production
 * business rules. Live reads/actions are expected to arrive through the
 * Core/API module contract.
 */

export const PRODUCTION_MODULE_CODE = "production";
export const PRODUCTION_UI_CONTRACT_VERSION = "1.0";

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
    permissions: Array.isArray(moduleMetadata.permissions) ? moduleMetadata.permissions : []
  };
}

export function getProductionApi() {
  const api = window.PhoenixCoreApi?.production;
  if (!api) {
    return null;
  }

  return api;
}

export function productionServiceState() {
  return getProductionApi() ? "connected" : "not-connected";
}

export async function listProductionOrders(query = {}) {
  const api = getProductionApi();
  if (!api?.listOrders) {
    throw new Error("Production Orders service is not connected.");
  }

  return api.listOrders(query);
}

export async function getProductionOrder(orderId) {
  const api = getProductionApi();
  if (!api?.getOrder) {
    throw new Error("Production Order service is not connected.");
  }

  return api.getOrder(orderId);
}

export async function getProductionStages(orderId) {
  const api = getProductionApi();
  if (!api?.getStages) {
    throw new Error("Production Stages service is not connected.");
  }

  return api.getStages(orderId);
}
