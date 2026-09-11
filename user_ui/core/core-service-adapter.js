/* Phoenix User UI V0.1 — Core service boundary.
 *
 * This adapter consumes authenticated Phoenix Core HTTP services. It does
 * not access storage directly. Hosts may inject window.PhoenixCoreApi for
 * deployments that provide a richer API client.
 */

const CORE_API_BASE = "/api";

async function request(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  let body = null;
  try { body = await response.json(); } catch (_) { body = null; }

  if (!response.ok) {
    const error = new Error(body?.error || `Phoenix Core API request failed (${response.status}).`);
    error.status = response.status;
    error.code = body?.code;
    throw error;
  }
  return body;
}

export const coreServiceAdapter = {
  async getUserContext() {
    const injected = window.PhoenixCoreApi?.getUserContext;
    return typeof injected === "function" ? injected() : request(`${CORE_API_BASE}/session`);
  },
  async getAuthorizedModuleCatalog() {
    const injected = window.PhoenixCoreApi?.getAuthorizedModuleCatalog;
    return typeof injected === "function" ? injected() : request(`${CORE_API_BASE}/module-catalog`);
  },
  async getMyWork(userId) {
    const injected = window.PhoenixCoreApi?.getMyWork;
    if (typeof injected === "function") return injected(userId);

    const [tasks, notifications] = await Promise.all([
      request(`${CORE_API_BASE}/workflow/tasks?status=Open`),
      request(`${CORE_API_BASE}/notifications`, { headers: { "X-Unread-Only": "1" } })
    ]);

    const assignedTasks = Array.isArray(tasks)
      ? tasks.filter((task) => String(task.assigned_to ?? "") === String(userId ?? ""))
      : [];

    return {
      tasks: assignedTasks,
      notifications: Array.isArray(notifications) ? notifications : []
    };
  },
  async completeWorkflowTask(taskId, notes = null) {
    const injected = window.PhoenixCoreApi?.completeWorkflowTask;
    if (typeof injected === "function") return injected(taskId, notes);
    throw new Error("Core workflow task completion endpoint is not connected yet.");
  },
  async search(query = {}) {
    const injected = window.PhoenixCoreApi?.search;
    if (typeof injected === "function") return injected(query);
    throw new Error("Core Search service endpoint is not connected yet.");
  },
  async getNotifications() {
    const injected = window.PhoenixCoreApi?.getNotifications;
    return typeof injected === "function" ? injected() : request(`${CORE_API_BASE}/notifications`);
  },
  async getCommunicationContext() {
    const injected = window.PhoenixCoreApi?.getCommunicationContext;
    if (typeof injected === "function") return injected();
    throw new Error("Core Communication service endpoint is not connected yet.");
  },
  async openAIWorkspace() {
    const injected = window.PhoenixCoreApi?.openAIWorkspace;
    if (typeof injected === "function") return injected();
    throw new Error("Core AI service endpoint is not connected yet.");
  }
};
