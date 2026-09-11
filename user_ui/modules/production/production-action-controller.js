import {
  PRODUCTION_ACTIONS,
  executeProductionAction
} from "./production-module-adapter.js";

/*
 * Production action controller.
 *
 * The UI owns confirmation, request state and presentation only. The
 * Core/API + Production service remains authoritative for permission,
 * tenant, workflow-state and business validation.
 */

export const PRODUCTION_ACTION_LABELS = Object.freeze({
  release: "Release",
  start: "Start",
  hold: "Place on Hold",
  resume: "Resume",
  complete: "Complete"
});

export async function requestProductionAction(action, orderId, payload = {}) {
  if (!PRODUCTION_ACTIONS.includes(action)) {
    throw new Error("Unsupported Production action.");
  }
  if (!orderId) {
    throw new Error("A Production Order is required.");
  }

  return executeProductionAction(action, orderId, payload);
}

export function actionLabel(action) {
  return PRODUCTION_ACTION_LABELS[action] || action;
}

export function actionRequiresConfirmation(action) {
  return ["release", "start", "hold", "resume", "complete"].includes(action);
}

export function normalizeActionResult(result) {
  const source = result?.result ?? result ?? {};
  const accepted = source.accepted ?? source.success ?? source.status === "accepted";
  const completed = source.completed ?? source.status === "completed";

  return {
    accepted: Boolean(accepted),
    completed: Boolean(completed),
    status: source.status ?? (accepted ? "accepted" : "failed"),
    message: source.message ?? source.detail ?? (accepted ? "Action accepted by the Production service." : "Production action was not accepted."),
    order: source.order ?? null,
    auditId: source.auditId ?? source.audit_id ?? null,
    correlationId: source.correlationId ?? source.correlation_id ?? null
  };
}
