# Phoenix User UI V0.1

Phoenix User UI is the authenticated user-facing workspace layer of Phoenix.

## Boundary

- The User UI never connects directly to a database.
- Core remains authoritative for identity, authentication, session, tenant context, authorization, navigation registration, and shared platform services.
- Business modules remain authoritative for business entities, rules, workflows, and transactions.
- Company Platform remains a separate tenant administration and oversight layer.
- Module visibility is discovered from authorized module registration; future modules are not hard-coded into the shell.

## V0.1 foundation

This first build establishes the browser-side User UI shell only:

- Phoenix Core header
- persistent left navigation
- workspace container
- responsive enterprise layout
- explicit loading, empty, error, and no-permission states
- service boundary for later Core/API integration

The current shell uses a development context adapter and does not claim live business data or transaction success.

## Planned build sequence

1. User UI foundation
2. User Shell
3. Core Header
4. Left Navigation
5. Workspace container
6. Home
7. My Work
8. Core service interfaces
9. Dynamic module discovery/loading
10. Production workspace integration
11. Profile
12. Security/integration testing
13. V0.1 acceptance
