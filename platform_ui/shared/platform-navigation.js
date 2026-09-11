const PLATFORM_PATHS = Object.freeze({
  USER: "/user",
  COMPANY: "/company",
  SYSTEM: "/system",
});

export function currentPlatform(pathname = window.location.pathname) {
  if (pathname === PLATFORM_PATHS.COMPANY || pathname.startsWith(`${PLATFORM_PATHS.COMPANY}/`)) return "COMPANY";
  if (pathname === PLATFORM_PATHS.SYSTEM || pathname.startsWith(`${PLATFORM_PATHS.SYSTEM}/`)) return "SYSTEM";
  if (pathname === PLATFORM_PATHS.USER || pathname.startsWith(`${PLATFORM_PATHS.USER}/`)) return "USER";
  return null;
}

export function platformLabel(platform) {
  return ({ USER: "User Workspace", COMPANY: "Company Platform", SYSTEM: "System Platform" })[platform] || "Phoenix";
}

export function platformLinks(allowedPlatforms = []) {
  const allowed = new Set(allowedPlatforms);
  return ["USER", "COMPANY", "SYSTEM"]
    .filter((platform) => allowed.has(platform))
    .map((platform) => ({ platform, href: PLATFORM_PATHS[platform], label: platformLabel(platform) }));
}

export function renderPlatformSwitcher(container, allowedPlatforms, activePlatform) {
  if (!container) return;
  container.replaceChildren();
  const links = platformLinks(allowedPlatforms);
  if (links.length <= 1) return;

  const label = document.createElement("div");
  label.className = "platform-switcher-label";
  label.textContent = "Phoenix Platforms";
  container.appendChild(label);

  for (const item of links) {
    const link = document.createElement("a");
    link.href = item.href;
    link.className = `platform-switcher-link${item.platform === activePlatform ? " active" : ""}`;
    link.textContent = item.label;
    link.setAttribute("aria-current", item.platform === activePlatform ? "page" : "false");
    container.appendChild(link);
  }
}
