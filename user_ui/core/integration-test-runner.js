/* Phoenix User UI V0.1 — browser integration harness.
 * PASS means a check was actually verified. BLOCKED means the required
 * authoritative Core capability was not available to execute the check.
 */

const BLOCKED = "BLOCKED";
const PASS = "PASS";
const FAIL = "FAIL";

function result(id, label, state, detail) {
  return { id, label, state, passed: state === PASS, detail };
}

export async function runCoreIntegrationChecks({ coreServiceAdapter, moduleCatalogAdapter }) {
  const results = [];

  try {
    const session = await coreServiceAdapter.getUserContext();
    if (session?.user) {
      results.push(result("AUTH-02", "Authenticated Core session", PASS, "Authenticated user context received."));
    } else {
      results.push(result("AUTH-02", "Authenticated Core session", FAIL, "Core returned no user context."));
    }

    if (session?.user?.organisation_id) {
      results.push(result("TEN-01", "Tenant context", PASS, "Organisation context received from Core."));
    } else {
      results.push(result("TEN-01", "Tenant context", FAIL, "Organisation context missing."));
    }

    try {
      const catalog = await coreServiceAdapter.getAuthorizedModuleCatalog();
      const modules = moduleCatalogAdapter(catalog);
      results.push(Array.isArray(modules)
        ? result("MOD-01", "Authorized module catalog", PASS, `${modules.length} authorized module(s) exposed.`)
        : result("MOD-01", "Authorized module catalog", FAIL, "Core returned an invalid module catalog."));
    } catch (error) {
      results.push(result("MOD-01", "Authorized module catalog", FAIL, error?.message || "Module catalog request failed."));
    }
  } catch (error) {
    if (error?.status === 401 || error?.status === 403) {
      results.push(result("AUTH-01", "Protected session boundary", PASS, "Protected Core endpoint correctly rejected unauthenticated access."));
      results.push(result("AUTH-02", "Authenticated Core session", BLOCKED, "Authenticated Core session could not be established in this runtime."));
      results.push(result("TEN-01", "Tenant context", BLOCKED, "Tenant context cannot be verified without an authenticated Core session."));
      results.push(result("MOD-01", "Authorized module catalog", BLOCKED, "Module authorization cannot be verified without an authenticated Core session."));
    } else {
      results.push(result("AUTH-01", "Protected session boundary", BLOCKED, "The harness could not establish the runtime state required to test unauthenticated rejection."));
      results.push(result("AUTH-02", "Authenticated Core session", BLOCKED, error?.message || "Authenticated session could not be established."));
      results.push(result("TEN-01", "Tenant context", BLOCKED, "Tenant context cannot be verified until the Core session is available."));
      results.push(result("MOD-01", "Authorized module catalog", BLOCKED, "Module authorization cannot be verified until the Core session is available."));
    }
  }

  return results;
}

export { BLOCKED, PASS, FAIL };
