# Phoenix Core Foundation — Frozen Baseline v0.1

## Freeze status

Phoenix Core Foundation v0.1 is now the **frozen platform baseline**.

This means the Core architecture is considered established for the next
development stage.

## Included in Core

### Platform
- Multi-tenant organisation foundation
- Tenant isolation
- Users
- Roles and permissions
- Branches
- User-to-branch access

### Configuration
- Module settings
- Feature flags
- Number sequences
- Custom fields

### Security & governance
- Security events
- Audit trail
- Permission model

### Communications
- In-app notifications
- Notification preferences
- Notification templates
- Delivery queue/status
- Notification history/events

## What is NOT frozen as production-grade security

The architecture is frozen, but production hardening remains a controlled
patch stream. This includes MFA, SSO, password recovery, rate limiting,
secure secret management and deployment hardening.

## Change control

No direct edits should be made to the frozen baseline.

Future changes must be represented as:

```text
Phoenix Core Foundation v0.1
          |
          +-- Core Patch v0.1.x
          +-- Security Patch v0.1.x
          +-- Module Patch
          +-- Integration Adapter
          +-- Customer Configuration
```

## IP separation

Phoenix Core must remain reusable and generic.

Do not place customer-specific:
- confidential data
- business rules
- proprietary processes
- ERP mappings
- BOMs
- costing rules
- customer workflows
- customer credentials

inside Phoenix Core.

## Module rule

A module may use Core services, but Core must not depend on customer-specific
module behaviour.

## Freeze principle

The purpose of this freeze is stability: we can now build modules against a
known platform contract instead of continuously changing the platform beneath
them.
