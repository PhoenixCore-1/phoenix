/* Phoenix User UI V0.1 — Core service boundary.
 *
 * This adapter consumes authenticated Phoenix Core HTTP services. It does
 * not access storage directly. Hosts may inject window.PhoenixCoreApi for
 * deployments that provide a richer API client.
 *
 * V2 context rule: authenticated requests that resolve tenant-scoped data
 * require the authoritative organisation context. The UI may carry that
 * context between Core calls, but Core remains responsible for validating
 * membership, permissions and entitlements.
 */

const CORE_API_BASE = "/api";
let coreContext = { sessionId: null, token: null, organisationId: null };

export function setCoreContext(context = {}) {
  coreContext = {
    sessionId: context.sessionId ?? context.session_id ?? coreContext.sessionId,
    token: context.token ?? coreContext.token,
    organisationId: context.organisationId ?? context.organisation_id ?? coreContext.organisationId
  };
}

export function clearCoreContext() {
  coreContext = { sessionId: null, token: null, organisationId: null };
}

function unwrapApiResponse(body) {
  if (body && Object.prototype.hasOwnProperty.call(body, "data")) return body.data;
  return body;
}

export async function getCoreRequest() {
  return async function request(path, options = {}) {
    const headers = {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(coreContext.sessionId ? { "X-Phoenix-Session-Id": coreContext.sessionId } : {}),
      ...(coreContext.organisationId ? { "X-Phoenix-Organisation-Id": coreContext.organisationId } : {}),
      ...(coreContext.token ? { Authorization: `Bearer ${coreContext.token}` } : {}),
      ...(options.headers || {})
    };

    const response = await fetch(path, {
      credentials: "same-origin",
      ...options,
      headers
    });

    let body = null;
    try { body = await response.json(); } catch (_) { body = null; }

    if (!response.ok) {
      const payload = unwrapApiResponse(body);
      const error = new Error(payload?.error || body?.error || `Phoenix Core API request failed (${response.status}).`);
      error.status = response.status;
      error.code = payload?.code || body?.code;
      throw error;
    }
    return unwrapApiResponse(body);
  };
}

const request = async (path, options = {}) => (await getCoreRequest())(path, options);

export const coreServiceAdapter = {
  setContext: setCoreContext,
  clearContext: clearCoreContext,

  async getUserContext() {
    const injected = window.PhoenixCoreApi?.getUserContext;
    if (typeof injected === "function") {
      const result = await injected();
      const data = unwrapApiResponse(result);
      if (data?.session_id || data?.sessionId || data?.token || data?.organisation_id || data?.organisationId) setCoreContext(data);
      return data;
    }

    const data = await request(`${CORE_API_BASE}/session`);
    if (data?.session_id || data?.sessionId || data?.token || data?.organisation_id || data?.organisationId) setCoreContext(data);
    return data;
  },

  async getAuthorizedModuleCatalog() {
    const injected = window.PhoenixCoreApi?.getAuthorizedModuleCatalog;
    return typeof injected === "function"
      ? unwrapApiResponse(await injected())
      : request(`${CORE_API_BASE}/module-catalog`);
  },

  async getMyWork(userId) {
    const injected = window.PhoenixCoreApi?.getMyWork;
    if (typeof injected === "function") return unwrapApiResponse(await injected(userId));

    const [tasks, notifications] = await Promise.all([
      request(`${CORE_API_BASE}/workflow/tasks?status=Open`),
      request(`${CORE_API_BASE}/notifications`, { headers: { "X-Unread-Only": "1" } })
    ]);

    const assignedTasks = Array.isArray(tasks)
      ? tasks.filter((task) => String(task.assigned_to ?? "") === String(userId ?? ""))
      : [];

    return { tasks: assignedTasks, notifications: Array.isArray(notifications) ? notifications : [] };
  },

  async completeWorkflowTask(taskId, notes = null) {
    const injected = window.PhoenixCoreApi?.completeWorkflowTask;
    if (typeof injected === "function") return unwrapApiResponse(await injected(taskId, notes));
    throw new Error("Core workflow task completion endpoint is not connected yet.");
  },

  async search(query = {}) {
    const injected = window.PhoenixCoreApi?.search;
    if (typeof injected === "function") return unwrapApiResponse(await injected(query));
    throw new Error("Core Search service endpoint is not connected yet.");
  },

  async getNotifications() {
    const injected = window.PhoenixCoreApi?.getNotifications;
    return typeof injected === "function" ? unwrapApiResponse(await injected()) : request(`${CORE_API_BASE}/notifications`);
  },

  async getCommunicationContext() {
    const injected = window.PhoenixCoreApi?.getCommunicationContext;
    if (typeof injected === "function") return unwrapApiResponse(await injected());
    throw new Error("Core Communication service endpoint is not connected yet.");
  },

  async openAIWorkspace() {
    const injected = window.PhoenixCoreApi?.openAIWorkspace;
    if (typeof injected === "function") return unwrapApiResponse(await injected());
    throw new Error("Core AI service endpoint is not connected yet.");
  }
};
