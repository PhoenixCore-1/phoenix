import { renderProfileNavigation } from "./profile-navigation.js";

/* Phoenix User UI V0.1 — Sign Out workspace.
 * Logout authority belongs to Phoenix Core. Browser state is cleared only
 * after Core confirms session revocation.
 */

export function renderSignOutWorkspace({ workspaceView, coreServiceAdapter, onSignedOut, navigate }) {
  workspaceView.innerHTML = `
    <header class="workspace-header"><div><p class="eyebrow">User Profile</p><h1 class="workspace-title">Sign Out</h1><p class="workspace-subtitle">End the current Phoenix session securely.</p></div></header>
    <div data-profile-navigation></div>
    <section class="card panel">
      <h2 class="panel-title">End this session?</h2>
      <p class="panel-subtitle">Phoenix Core will remain authoritative for session termination. The User UI will not claim logout succeeded until Core confirms it.</p>
      <div class="form-actions"><button class="button primary" type="button" data-sign-out>Sign Out</button><button class="button secondary" type="button" data-cancel>Cancel</button></div>
      <div class="status" data-signout-status role="status" aria-live="polite"></div>
    </section>`;

  renderProfileNavigation(workspaceView.querySelector("[data-profile-navigation]"), navigate, "sign-out");
  const status = workspaceView.querySelector("[data-signout-status]");
  workspaceView.querySelector("[data-cancel]").addEventListener("click", () => window.history.back());
  workspaceView.querySelector("[data-sign-out]").addEventListener("click", async () => {
    const button = workspaceView.querySelector("[data-sign-out]");
    button.disabled = true; status.className = "status"; status.textContent = "Ending Phoenix session…";
    try {
      if (typeof coreServiceAdapter.signOut !== "function") throw new Error("Core session revocation service is not connected yet.");
      await coreServiceAdapter.signOut();
      coreServiceAdapter.clearContext();
      status.textContent = "Phoenix Core confirmed session termination.";
      if (typeof onSignedOut === "function") onSignedOut();
    } catch (error) {
      button.disabled = false; status.className = "status error";
      status.textContent = error?.message || "Phoenix Core could not confirm session termination.";
    }
  });
}
