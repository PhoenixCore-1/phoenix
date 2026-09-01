# Phoenix PCA Company Platform
## Company Structure Contract V1.0

### Status

**Architecture baseline — V1.0**

---

## 1. Purpose

This contract defines the ownership boundary for company
organisational structure used by PCA and downstream business
modules.

It prevents PCA Company Platform from creating duplicate
organisation, branch or location masters.

---

## 2. Existing Authority

The authoritative organisational identity remains with the
existing Phoenix System Platform.

### Organisation

Authoritative owner:

**Phoenix System Platform**

### Branch

Authoritative owner:

**Phoenix System Platform**

### Location

Authoritative owner:

**Phoenix System Platform**

PCA consumes these authoritative identities through approved
application contracts.

---

## 3. PCA Ownership

PCA Company Platform owns company-level operational
configuration associated with authoritative organisational
entities.

Examples may include:

- operational configuration
- company-specific configuration
- module-facing company settings
- company operational preferences

These are configuration concerns, not replacement master
identities.

---

## 4. No Duplicate Masters

PCA must not create:

- a second organisation master
- a second branch master
- a second location master

The existence of a PCA service that needs branch or location
information does not justify creating another master.

---

## 5. Platform Provisioning

Platform provisioning remains outside PCA.

PCA does not create or provision platform tenants/companies.

---

## 6. Identity

Phoenix Core remains authoritative for:

- user identity
- authentication
- authorization

PCA receives the authenticated identity through the established
Phoenix application boundary.

---

## 7. Database

PCA must not directly access the Core database.

Persistence must be introduced only through an approved
application/persistence contract.

---

## 8. Business Modules

Business modules consume authoritative company structure.

Examples include:

- CRM
- Sales
- Inventory
- Procurement
- Production
- Projects

Modules must reference the authoritative organisation,
branch and location identities.

They must not create competing master identities.

---

## 9. Contract Version

Current contract:

**PCA Company Structure Contract V1.0**

Changes to organisational ownership require an explicit
architecture decision and contract revision.
