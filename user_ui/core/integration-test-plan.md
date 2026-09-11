# Phoenix User UI V0.1 — Security & Integration Test Plan

## Purpose
Verify the User UI integration boundary without treating browser checks as authoritative security controls.

## Test matrix

| ID | Journey / control | Expected result | Status |
|---|---|---|---|
| AUTH-01 | Unauthenticated User UI request | Core rejects protected session/API access | Requires runtime test |
| AUTH-02 | Authenticated user loads User UI | Core session establishes user + tenant context | Requires runtime test |
| AUTH-03 | Invalid/expired session | UI shows session-unavailable state; no protected data is assumed | Requires runtime test |
| TEN-01 | Tenant context | UI displays tenant supplied by Core | Implemented |
| TEN-02 | Cross-tenant record access | Core denies access; UI does not bypass authorization | Requires runtime test |
| MOD-01 | Authorized module catalog | Only Core-authorized modules are rendered | Implemented |
| MOD-02 | Unauthorized module route | UI cannot obtain module data without Core authorization | Requires runtime test |
| PROD-01 | Production action | Server validates action and returns authoritative result | Requires runtime test |
| PROD-02 | Failed production action | UI does not display false success | Implemented by action-state handling |
| DATA-01 | Direct database access | No database connection exists in User UI | Implemented by architecture/check |
| DATA-02 | API failure | Explicit error state is rendered | Implemented |
| NAV-01 | Unknown route | Workspace unavailable state is rendered | Implemented |
| NAV-02 | Module failure | Core shell remains available | Implemented by workspace isolation |
| SESS-01 | Logout/session termination | Protected User UI cannot continue as authenticated user | Requires V2 runtime integration |

## Release gate

V0.1 cannot be declared security/integration-complete until AUTH-01/02/03, TEN-02, MOD-02, PROD-01 and SESS-01 have been executed against the actual integrated Core V2 runtime.

## Known integration dependency

The current repository User UI consumes `/api/session` and `/api/module-catalog`. The previously observed Core V2 organisation/session failure must be resolved in the V2 runtime before tenant-isolation and logout tests can be accepted as passed.
