import { coreServiceAdapter } from "./core-service-adapter.js";

/* Phoenix User UI V0.1 — My Work workspace.
 *
 * This workspace presents action-oriented information supplied by Core.
 * The UI does not decide business meaning, authorization, or workflow state.
 */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function taskLabel(task) {
  return task.step_name || task.workflow_name || "Workflow task";
}

function taskRecordLabel(task) {
  if (task.entity_type && task.entity_id != null) {
    return `${task.entity_type} #${task.entity_id}`;
  }
  return "Related record";
}

function notificationTitle(item) {
  return item.title || item.subject || item.notification_type || "Notification";
}

function notificationBody(item) {
  return item.message || item.body || item.description || "Notification requiring your attention.";
}

function notificationTime(item) {
  return item.created_at || item.sent_at || item.updated_at || "";
}

export async function renderMyWorkWorkspace({ workspaceView, userId }) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">User Workspace</p>
        <h1 class="workspace-title">My Work</h1>
        <p class="workspace-subtitle">Your open tasks, attention items and actionable context.</p>
      </div>
      <div class="workspace-meta">
        <span class="status-pill">Core-backed</span>
        <button type="button" class="button-secondary" id="my-work-refresh">Refresh</button>
      </div>
    </header>
    <div id="my-work-status"></div>
    <div id="my-work-content"></div>
  `;

  const status = workspaceView.querySelector("#my-work-status");
  const content = workspaceView.querySelector("#my-work-content");
  const refresh = workspaceView.querySelector("#my-work-refresh");

  const load = async () => {
    refresh.disabled = true;
    status.innerHTML = `<div class="status info">Loading your work from Phoenix Core…</div>`;
    content.innerHTML = "";

    try {
      const result = await coreServiceAdapter.getMyWork(userId);
      const tasks = Array.isArray(result?.tasks) ? result.tasks : [];
      const notifications = Array.isArray(result?.notifications) ? result.notifications : [];

      status.innerHTML = "";
      content.innerHTML = `
        <div class="card-grid">
          <article class="card kpi"><div class="kpi-label">Open Tasks</div><div class="kpi-value">${tasks.length}</div><div class="kpi-note">Assigned to you</div></article>
          <article class="card kpi"><div class="kpi-label">Attention</div><div class="kpi-value">${tasks.length}</div><div class="kpi-note">Actionable workflow items</div></article>
          <article class="card kpi"><div class="kpi-label">Unread Notifications</div><div class="kpi-value">${notifications.length}</div><div class="kpi-note">Supplied by Core</div></article>
          <article class="card kpi"><div class="kpi-label">Work State</div><div class="kpi-value" style="font-size:18px">${tasks.length || notifications.length ? "Needs attention" : "Clear"}</div><div class="kpi-note">Current session</div></article>
        </div>

        <div class="content-grid">
          <section class="card panel">
            <h2 class="panel-title">Open Tasks</h2>
            <p class="panel-subtitle">Workflow tasks currently assigned to you.</p>
            <div id="my-work-tasks"></div>
          </section>
          <section class="card panel">
            <h2 class="panel-title">Attention &amp; Notifications</h2>
            <p class="panel-subtitle">Unread Core notifications related to your current work.</p>
            <div id="my-work-notifications"></div>
          </section>
        </div>
      `;

      const taskContainer = content.querySelector("#my-work-tasks");
      taskContainer.innerHTML = tasks.length
        ? tasks.map((task) => `
            <article class="work-item" tabindex="0" data-task-id="${escapeHtml(task.workflow_task_id)}" data-entity-type="${escapeHtml(task.entity_type)}" data-entity-id="${escapeHtml(task.entity_id)}">
              <div class="work-item-main">
                <strong>${escapeHtml(taskLabel(task))}</strong>
                <span>${escapeHtml(taskRecordLabel(task))}</span>
              </div>
              <div class="work-item-meta">
                <span>${escapeHtml(task.workflow_name || "Workflow")}</span>
                <span>${escapeHtml(task.due_at ? `Due ${task.due_at}` : "No due date")}</span>
              </div>
              <button type="button" class="button-secondary work-item-open">Open</button>
            </article>
          `).join("")
        : `<div class="table-state">No open tasks are currently assigned to you.</div>`;

      const notificationContainer = content.querySelector("#my-work-notifications");
      notificationContainer.innerHTML = notifications.length
        ? notifications.slice(0, 10).map((item) => `
            <article class="work-item notification-item">
              <div class="work-item-main">
                <strong>${escapeHtml(notificationTitle(item))}</strong>
                <span>${escapeHtml(notificationBody(item))}</span>
              </div>
              <div class="work-item-meta"><span>${escapeHtml(notificationTime(item))}</span></div>
            </article>
          `).join("")
        : `<div class="table-state">No unread notifications.</div>`;

      taskContainer.querySelectorAll(".work-item-open").forEach((button) => {
        button.addEventListener("click", (event) => {
          const item = event.currentTarget.closest(".work-item");
          window.dispatchEvent(new CustomEvent("phoenix:my-work-open", {
            detail: {
              taskId: item?.dataset.taskId || null,
              entityType: item?.dataset.entityType || null,
              entityId: item?.dataset.entityId || null
            }
          }));
        });
      });
    } catch (error) {
      status.innerHTML = `<div class="status error"><strong>My Work could not be loaded.</strong> ${escapeHtml(error?.message || "The Core service is unavailable.")}</div>`;
      content.innerHTML = `<section class="card panel"><div class="empty-state"><div><strong>No false success</strong>Your work was not marked complete. Retry when Core connectivity is restored.</div></div></section>`;
    } finally {
      refresh.disabled = false;
    }
  };

  refresh.addEventListener("click", load);
  await load();
}
