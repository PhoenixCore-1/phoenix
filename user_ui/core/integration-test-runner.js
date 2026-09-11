/* Phoenix User UI V0.1 — lightweight browser integration harness. */

export async function runCoreIntegrationChecks({ coreServiceAdapter, moduleCatalogAdapter }) {
  const results = [];

  try {
    const session = await coreServiceAdapter.getUserContext();
    results.push({ id: "AUTH-02", label: "Authenticated Core session", passed: Boolean(session?.user), detail: session?.user ? "Authenticated user context received." : "Core returned no user context." });
    results.push({ id: "TEN-01", label: "Tenant context", passed: Boolean(session?.user?.organisation_id), detail: session?.user?.organisation_id ? "Organisation context received from Core." : "Organisation context missing." });

    try {
      const catalog = await coreServiceAdapter.getAuthorizedModuleCatalog();
      const modules = moduleCatalogAdapter(catalog);
      results.push({ id: "MOD-01", label: "Authorized module catalog", passed: Array.isArray(modules), detail: `${Array.isArray(modules) ? modules.length : 0} authorized module(s) exposed.` });
    } catch (error) {
      results.push({ id: "MOD-01", label: "Authorized module catalog", passed: false, detail: error?.message || "Module catalog request failed." });
    }
  } catch (error) {
    const passed = error?.status === 401 || error?.status === 403;
    results.push({ id: "AUTH-01", label: "Protected session boundary", passed, detail: passed ? "Protected Core endpoint correctly rejected unauthenticated access." : (error?.message || "Session request failed unexpectedly.") });
    results.push({ id: "AUTH-02", label: "Authenticated Core session", passed: false, detail: "Authenticated session could not be established." });
  }

  return results;
}
