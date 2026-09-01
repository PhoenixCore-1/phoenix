# Phoenix PCA Company Platform
## Company Platform Contract V1.0

### Status

**Architecture baseline — V1.0**

---

## 1. Purpose

PCA Company Platform is the company/tenant-level control and
configuration layer within the Phoenix customer/company data plane.

It is distinct from the Phoenix Platform Control Plane.

It must never become a second Platform Control Plane.

---

## 2. Authority Model

### Phoenix Core

Phoenix Core remains authoritative for:

- authentication
- authorization
- identity
- security boundaries
- Core security policy
- platform identity propagation

### Phoenix Platform Control Plane

The Platform Control Plane remains authoritative for:

- platform-wide tenant/company provisioning
- platform licensing
- module entitlements
- platform security
- global platform configuration
- platform-wide controls

### PCA Company Platform

PCA Company Platform owns company/tenant-level:

- company configuration
- company operational configuration
- company-level organisational structure
- company-level configuration consumed by business modules
- company-level control settings

---

## 3. Non-Ownership

PCA Company Platform does not own:

- Core authentication
- Core authorization
- platform-wide licensing
- platform-wide module entitlement
- platform provisioning
- global platform configuration
- Core database access
- a second platform security boundary

---

## 4. Identity

PCA receives authenticated identity from the established Phoenix
Core/System Platform boundary.

PCA does not authenticate users independently.

PCA must preserve:

- user identity
- company/organisation identity
- identity scope

Identity must not be silently replaced or recreated.

---

## 5. Company Scope

PCA Company Platform operates at:

**COMPANY**

The company/tenant context is authoritative for PCA company
configuration and operational configuration.

---

## 6. Item Master

Inventory is the authoritative company Item Master.

PCA must not create a second Products/Items master merely to
support another business module.

Sales, Production, Procurement and other modules must consume
the authoritative Inventory item identity.

A distinct product entity may only be introduced if a future,
explicit business requirement demonstrates that a separate
entity is genuinely required.

---

## 7. Database Boundary

PCA must not connect directly to the Phoenix Core database.

Database ownership and persistence access must be exposed through
the appropriate Phoenix application/service contracts.

---

## 8. Business Module Boundary

PCA provides the company-level configuration/control foundation
for business modules.

Business modules remain responsible for their own domain logic.

Examples include:

- CRM
- Sales
- Inventory
- Procurement
- Production
- Projects

PCA must not absorb their domain logic simply because they consume
company configuration.

---

## 9. Contract Version

Current contract:

**PCA Company Platform Contract V1.0**

Changes to ownership boundaries require an explicit architecture
decision and contract revision.
