# Phoenix Security & Administration v0.1

Generic platform administration layer for Phoenix.

## Included

### Security
- Role definitions
- Role permissions
- User-role assignments
- Security event log
- Permission-controlled administration

### Organisation administration
- Branches
- User-branch assignments
- Module settings
- Feature flags

### Configuration
- Number sequences
- Custom-field definitions
- Custom-field values

### Platform controls
- Administrative dashboard
- Tenant isolation
- Audit trail
- Permission model

## Architectural purpose

This layer makes Phoenix configurable without embedding customer-specific
business rules into Phoenix Core.

Example:

```text
Customer A
  Roles
  Branches
  Enabled modules
  Numbering
  Custom fields

Customer B
  Roles
  Branches
  Enabled modules
  Numbering
  Custom fields
```

Both use the same Phoenix Core.

## Security note

v0.1 adds the administration data model and controls. A production deployment
still needs hardened authentication/session handling, password policy, MFA,
rate limiting, secret management and deployment security.

## Deliberate exclusions

- Customer-specific roles
- Customer-specific permissions
- Hard-coded branch structures
- Statutory configuration
- Identity-provider integrations
- MFA implementation
- Password reset/email infrastructure
- SSO
- Production secret vault integration

These should be later patches or adapters.

## Run

```bash
python app.py
```

Open http://localhost:8080

Development bootstrap:
- admin
- ChangeMe123!

Production hardening remains required before deployment.
