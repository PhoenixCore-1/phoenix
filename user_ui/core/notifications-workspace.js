import { renderProfileNavigation } from "./profile-navigation.js";

/* Phoenix User UI V0.1 — Core notification centre. */

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizeNotifications(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.notifications)) return payload.notifications;
  if (Array.isArray(payload?.items)) return payload.items;
  return [];
}

function notificationTitle(item) {
  return item.title || item.subject || item.message || item.type || "Notification";
}

function notificationBody(item) {
  if (item.message && item.message !== notificationTitle(item)) return item.message;
  return item.description || item.body || "No additional details provided.";
}

function notificationMeta(item) {
  return item.created_at || item.createdAt || item.timestamp || item.date || "";
}

function renderShell(workspaceView, navigate, body) {
  workspaceView.innerHTML = `
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Phoenix Core</p>
        <h1 class="workspace-title">Notifications</h1>
        <p class="workspace-subtitle">${body.subtitle}</p>
      </div>
    </header>
    <div data-profile-navigation></div>
    ${body.content}`;
  renderProfileNavigation(workspaceView.querySelector("[data-profile-navigation]"), navigate, "notifications");
}

export async function renderNotificationsWorkspace({ workspaceView, coreServiceAdapter, navigate }) {
  renderShell(workspaceView, navigate, {
    subtitle: "Your permission-aware notification centre.",
    content: '<section class="card panel"><div class="table-state">Loading notifications…</div></section>'
  });

  try {
    const payload = await coreServiceAdapter.getNotifications();
    const notifications = normalizeNotifications(payload);

    if (!notifications.length) {
      renderShell(workspaceView, navigate, {
        subtitle: "Your permission-aware notification centre.",
        content: '<section class="card panel"><div class="empty-state"><div><strong>No notifications</strong>You are up to date.</div></div></section>'
      });
      return;
    }

    const items = notifications.map((item) => `
      <article class="notification-center-item">
        <div class="notification-center-main">
          <strong>${escapeHtml(notificationTitle(item))}</strong>
          <span>${escapeHtml(notificationBody(item))}</span>
        </div>
        <div class="notification-center-meta">
          <span>${escapeHtml(notificationMeta(item))}</span>
        </div>
      </article>`).join("");

    renderShell(workspaceView, navigate, {
      subtitle: `${notifications.length} notification${notifications.length === 1 ? "" : "s"} available to you.`,
      content: `<section class="card panel"><div class="notification-center-list">${items}</div></section>`
    });
  } catch (error) {
    renderShell(workspaceView, navigate, {
      subtitle: "Your permission-aware notification centre.",
      content: `<div class="status error"><strong>Notifications unavailable.</strong> ${escapeHtml(error?.message || "The Core notification service could not be reached.")}</div>`
    });
  }
}
