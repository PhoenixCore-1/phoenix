# Phoenix Core Module Licensing & Entitlements v1.0

Commercial module access is organisation-specific.

## Access chain

Module Catalogue
-> Organisation Licence / Entitlement
-> Valid Licence
-> Organisation Module Enabled
-> User Role / Permission
-> Access

## Licence statuses

- NOT_LICENSED
- TRIAL
- ACTIVE
- EXPIRED
- SUSPENDED

A module cannot be enabled for an organisation without a valid TRIAL or
ACTIVE licence.

A normal user cannot grant a licence or enable a module for themselves.
Licensing and module enablement require the Core `licensing.manage`
permission.

The module catalogue is global; licence and enabled state are stored per
organisation so one customer cannot enable a module for another customer.

## Important distinction

- Catalogue availability does not mean licensed.
- Licensed does not mean enabled.
- Enabled does not mean every user can access it.
- User access still requires the appropriate Core/module permission.

No customer-specific commercial rules belong in Phoenix Core.
