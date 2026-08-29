# Phoenix Core Baseline Policy — v0.1

## Status

Phoenix Security & Administration is now a **Core platform capability**.

It is not an optional module and it is not an Upat-specific component.

## Core foundation

- Organisation / tenant structure
- Users
- Roles
- Permissions
- Branches
- User-to-branch access
- Module settings
- Feature flags
- Number sequences
- Custom fields
- Security events
- Audit trail

## Architecture rule

Core owns the platform mechanisms.

Business modules consume those mechanisms.

```text
PHOENIX CORE
├── Security & Administration
├── Tenant / Organisation
├── Users / Roles / Permissions
├── Configuration
├── Audit / Security Events
└── Shared platform services
        │
        ├── CRM
        ├── Projects
        ├── Sales
        ├── Production
        ├── Inventory
        ├── Procurement
        ├── Accounts
        ├── Workflow
        ├── Reporting
        └── Integrations
```

## Patch policy

The foundation should not be redesigned for every customer.

Future changes are controlled patches. Customer-specific logic belongs in a
customer module or configuration layer.

## IP separation

Phoenix Core must remain reusable and generic. Customer-specific confidential
information, data, proprietary processes, ERP mappings and business rules must
not be embedded into Core.

## Freeze rule

Once accepted as the baseline, future changes should be made through controlled
patches and regression-tested against this baseline.

## Production hardening

MFA, SSO, password recovery, rate limiting, secure secret management and
deployment hardening remain separate security patches.
