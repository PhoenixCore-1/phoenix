/* Phoenix User UI V0.1 — client-side security/integration checks.
 *
 * These checks validate the UI boundary only. They do not replace server-side
 * authentication, authorization, tenant isolation, or security controls.
 */

export function runUserUiSecurityChecks({ session, authorizedModules = [], location = window.location } = {}) {
  const checks = [];

  checks.push({
    id: "authenticated-session",
    label: "Authenticated Core session",
    passed: Boolean(session?.user),
    detail: session?.user ? "Core returned an authenticated user context." : "No authenticated Core user context was returned."
  });

  checks.push({
    id: "tenant-context",
    label: "Tenant context present",
    passed: Boolean(session?.user?.organisation_id),
    detail: session?.user?.organisation_id ? "Organisation context is supplied by Core." : "Organisation context is missing."
  });

  checks.push({
    id: "authorized-module-catalog",
    label: "Authorized module catalog",
    passed: Array.isArray(authorizedModules),
    detail: Array.isArray(authorizedModules)
      ? `${authorizedModules.length} authorized module(s) exposed to the UI.`
      : "Module catalog is not a valid Core response."
  });

  checks.push({
    id: "no-db-url",
    label: "No direct database access",
    passed: !location.search.includes("database=") && !location.search.includes("db="),
    detail: "User UI data access remains through the Core/API boundary."
  });

  return checks;
}
