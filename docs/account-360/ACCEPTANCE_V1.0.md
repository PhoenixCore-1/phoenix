# Phoenix Account 360 V1.0 — Acceptance Matrix

| ID | Acceptance requirement | Priority |
|---|---|---|
| A360-001 | User can open an account using the canonical Phoenix account/customer identity | Critical |
| A360-002 | Tenant isolation prevents access to another tenant's account data | Critical |
| A360-003 | Server-side permissions control account and financial information | Critical |
| A360-004 | Account 360 displays the agreed 14 sections | Critical |
| A360-005 | Account 360 does not become a second financial system of record | Critical |
| A360-006 | Financial values drill into Accounts-controlled authoritative records/services | Critical |
| A360-007 | No direct SQL/database access occurs across module ownership boundaries | Critical |
| A360-008 | CRM interactions and customer relationship context appear in the unified account view | High |
| A360-009 | Sales quotes and orders appear with source references | High |
| A360-010 | Inventory delivery/POD context appears with source references | High |
| A360-011 | Payments and allocations are shown with correct Accounts authority | Critical |
| A360-012 | Ledger and aging information are consistent with Accounts | Critical |
| A360-013 | Timeline entries are correctly ordered and source-linked | High |
| A360-014 | Duplicate events do not create duplicate Account 360 projection records | High |
| A360-015 | Stale projection state is detectable and authoritative financial data is refreshed when required | Critical |
| A360-016 | Integration failures are logged, observable and retryable | High |
| A360-017 | Projection/index rebuild can reconstruct derived Account 360 state | High |
| A360-018 | Large histories are paginated and do not cause unbounded queries | High |
| A360-019 | Core navigation registration and back-stack behaviour are correct | High |
| A360-020 | Audit context exists for Account 360-controlled actions and delegated commands | Critical |
| A360-021 | Source-module commands are executed only by the owning module | Critical |
| A360-022 | Account 360 remains functional when a non-critical source integration is temporarily unavailable, with clear unavailable/stale indicators | High |
| A360-023 | Module registration/licensing follows Phoenix Core rules | Critical |
| A360-024 | Regression tests pass against the supported Phoenix Core/module contracts | Critical |

## Release gate

All Critical requirements must pass. High-priority requirements may not have unresolved defects affecting data integrity, security, financial correctness, or navigation. Performance, recovery and integration tests must be demonstrated before V1.0 release.
