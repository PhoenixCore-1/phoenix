/* Phoenix User UI V0.1 — module discovery adapter.
 *
 * The browser consumes a sanitized Core/API response. It does not import
 * Python modules, inspect the database, or decide authorization itself.
 */

export function normalizeModuleCatalog(catalog) {
  if (!Array.isArray(catalog)) return [];

  return catalog
    .filter((module) => module && module.code && module.name)
    .map((module) => ({
      code: String(module.code),
      name: String(module.name),
      version: String(module.version || ""),
      description: String(module.description || ""),
      menu: Array.isArray(module.menu)
        ? module.menu
            .filter((item) => item && item.label && item.route)
            .map((item) => ({
              code: String(item.code || ""),
              label: String(item.label),
              route: String(item.route),
              permission: String(item.permission || ""),
              order: Number.isFinite(Number(item.order)) ? Number(item.order) : 100
            }))
        : []
    }))
    .sort((a, b) => {
      const aOrder = a.menu[0]?.order ?? 100;
      const bOrder = b.menu[0]?.order ?? 100;
      return aOrder - bOrder || a.name.localeCompare(b.name);
    });
}

export function getHostModuleCatalog() {
  return normalizeModuleCatalog(window.PhoenixCoreModuleCatalog);
}

export function moduleFromMenuRoute(modules, route) {
  return modules.find((module) => module.menu.some((item) => item.route === route)) || null;
}
