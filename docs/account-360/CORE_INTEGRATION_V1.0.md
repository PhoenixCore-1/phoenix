# Phoenix Account 360 — Core Integration V1.0

## Status

Integrated on the Phoenix Core feature branch `feature/account-360-build-v1`.

## Module registration

- Code: `account_360`
- Name: `Account 360`
- Version: `1.0.0`
- Core-owned: `false`
- Default enabled: `false`
- Navigation: `/account-360`

Account 360 is an independently owned module. Core provides the platform
services and lifecycle controls; Account 360 provides the account experience,
projection contracts and domain-facing adapters.

## Security and licensing

Core remains authoritative for authentication, tenant isolation,
server-side permissions, licensing and navigation. The module is not enabled
by default and must pass the existing licensing/entitlement chain before use.

The registered permissions are:

- `account_360.view`
- `account_360.financial.view`
- `account_360.commercial.view`
- `account_360.operations.view`
- `account_360.communication.view`
- `account_360.communication.content.view`
- `account_360.timeline.view`
- `account_360.actions.execute`
- `account_360.ai.use`
- `account_360.ai.action.execute`

## Loading boundary

Core loads the external `account_360` package through
`core.module_adapters.account_360`. Core does not import Account 360 internal
business implementation directly.

## Ownership boundary

Account 360 does not become the system of record for financial, CRM, Sales,
Inventory or Procurement data. It consumes approved service/event contracts
and keeps references/projections only. Commands continue to route to the
owning module.

## Release baseline

The Account 360 module is maintained in the separate
`PhoenixCore-1/Phoenix-Account` repository and is currently version `1.0.0`.
Its V1.0 schema baseline is the module's `migrations/001_initial_account_360.sql`.

## Integration test gate

Core integration tests must verify module registration, permission catalogue,
runtime module catalogue and adapter presence before this branch is considered
ready for controlled integration testing.
