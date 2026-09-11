/* Phoenix User UI V0.1 — Profile navigation registry. */
export const PROFILE_SCREENS = Object.freeze([
  { route: "profile", label: "My Profile" },
  { route: "profile-preferences", label: "Preferences" },
  { route: "security", label: "Security" },
  { route: "notifications", label: "Notifications" },
  { route: "devices-sessions", label: "Devices & Sessions" },
  { route: "activity", label: "Activity" },
  { route: "help-support", label: "Help & Support" },
  { route: "about-phoenix", label: "About Phoenix" },
  { route: "sign-out", label: "Sign Out" }
]);

export function renderProfileNavigation(container, navigate, activeRoute = "profile") {
  if (!container) return;
  container.innerHTML = PROFILE_SCREENS.map((screen) => `<button class="profile-nav-item ${screen.route === activeRoute ? "active" : ""}" type="button" data-profile-route="${screen.route}">${screen.label}</button>`).join("");
  container.querySelectorAll("[data-profile-route]").forEach((item) => item.addEventListener("click", () => navigate(item.dataset.profileRoute)));
}
