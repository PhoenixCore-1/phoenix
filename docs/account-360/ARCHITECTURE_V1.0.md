# Phoenix Account 360 V1.0 — Architecture Baseline

**Status:** Build baseline — architecture first
**Workstream:** Phoenix Account 360 Build
**Branch:** `feature/account-360-build-v1`
**Date:** 2026-09-07

## 1. Purpose

Phoenix Account 360 is the unified account/customer experience across Phoenix. It presents a consolidated commercial, relationship, operational and financial view without taking ownership of data that belongs to another Phoenix module.

Account 360 is an aggregation and experience layer. It is not a parallel ERP, CRM, Sales, Inventory, Procurement or Accounts database.

## 2. Locked ownership boundaries

| Capability | System of record |
|---|---|
| Phoenix identity, tenant, permissions, navigation, audit/event infrastructure | Phoenix Core |
| Customer relationship management and customer relationship data | CRM |
| Quotes and sales orders | Sales |
| Physical stock, delivery/POD and inventory operations | Inventory |
| Purchasing and supplier procurement | Procurement |
| Financial accounts, AR/AP, invoices, payments, VAT, banking, GL, financial reporting and financial controls | Accounts |
| Unified account/customer presentation and cross-module context | Account 360 |

Account 360 MUST NOT create duplicate financial truth. Financial balances, invoices, payments, allocations, VAT, GL and other controlled financial values remain authoritative in Accounts.

## 3. Integration rule

Cross-module access MUST use Phoenix Core-approved contracts, services and events/API boundaries. Account 360 MUST NOT connect directly to another module's SQL database.

The Account 360 layer may maintain only data required for its own presentation, indexing, integration state, preferences and other explicitly approved non-authoritative projections.

## 4. Account identity

Phoenix uses one canonical customer/account identity across modules. Account 360 resolves module records to that identity and uses stable Phoenix identifiers rather than module-local identifiers as its primary cross-module reference.

The architecture must support:

- account/customer master identity;
- parent/child account relationships;
- branches, sites and locations;
- contacts and relationship roles;
- account ownership and responsibility;
- tenant isolation;
- active/inactive status;
- controlled merge/link/reference behaviour where supported by Core.

## 5. Account 360 structure

The Account 360 experience contains the following authoritative sections:

1. Overview
2. Financial Position
3. Credit & Exposure
4. Invoices
5. Orders & Quotes
6. Deliveries & POD
7. Payments & Allocations
8. Customer Ledger
9. Aging & Collections
10. Statements
11. Documents
12. Communication
13. Tax & VAT
14. Credit Notes / Adjustments / Disputes

The exact data displayed in each section is supplied by the owning module through approved contracts.

## 6. Timeline

Account 360 provides a unified chronological timeline of relevant account events and interactions. Timeline entries are references to authoritative records/events, not replacement copies of the source transactions.

Timeline events may include:

- CRM interactions;
- calls and communications;
- meetings and visits;
- quotes;
- orders;
- deliveries/POD;
- invoices;
- payments and allocations;
- credit notes and adjustments;
- disputes;
- collection activity;
- documents;
- important account-status events.

## 7. Financial controls

Financial information displayed by Account 360 is read from or derived from Accounts-controlled services/contracts. Account 360 must preserve financial-control semantics including:

- authoritative balances;
- credit limits and credit status;
- invoice state;
- payment state and allocation;
- aging;
- tax/VAT treatment;
- credit notes and adjustments;
- disputes;
- financial audit context;
- role-based financial access.

Any financial command/action must execute through Accounts-controlled operations and their approval/control rules.

## 8. Security

Account 360 inherits Phoenix Core tenant isolation, authentication, authorization, session/device controls, MFA policy, encryption requirements and audit requirements.

Permissions must be evaluated server-side. UI visibility is not a security boundary.

Financial sections and actions must support the Accounts permission model. Sensitive information must not be exposed merely because a user can open an account.

## 9. UI/navigation

Account 360 must follow the existing Phoenix Core navigation and back-stack rules. It must register through Core rather than implementing an independent navigation system.

The account view should provide:

- account header/context;
- clear section navigation;
- attention/exception indicators;
- role-appropriate quick actions;
- unified timeline;
- drill-down to authoritative source records;
- predictable back-stack behaviour.

## 10. Events and consistency

Account 360 consumes approved domain/integration events and APIs from owning modules. Events must be idempotently processed where projections or indexes are maintained.

The design must distinguish:

- authoritative transaction state;
- cached/projected Account 360 state;
- event delivery state;
- integration errors/reconciliation state.

A stale projection must never be presented as authoritative when the owning service can provide current controlled data.

## 11. Automation

Account 360 may surface or initiate approved workflows such as follow-ups, collection actions, reminders and account attention items. Automation execution must use Phoenix Core workflow/automation infrastructure and must respect module ownership and authorization.

## 12. Performance

The Account 360 landing view must avoid fan-out database access. Aggregated data should be obtained through bounded contracts and appropriate projections/caching where approved.

Large histories, invoices, orders, ledger entries and communications must be paginated. Expensive financial calculations remain owned by Accounts or an approved Accounts service.

## 13. Disaster recovery and resilience

Account 360 must be recoverable without becoming the authoritative store for other modules. Projection/index rebuild procedures must exist for derived Account 360 data.

Integration failures must be observable, retryable and auditable. Source-of-truth records remain recoverable through their owning module.

## 14. Testing and acceptance

Before release, Account 360 must demonstrate:

- tenant isolation;
- authorization enforcement;
- correct canonical account resolution;
- correct cross-module references;
- no direct cross-module database access;
- correct financial authority and drill-down;
- event idempotency and retry behaviour;
- stale-data handling;
- timeline correctness;
- pagination/performance behaviour;
- audit coverage;
- navigation/back-stack correctness;
- integration failure handling;
- projection rebuild/recovery;
- regression compatibility with Phoenix Core and integrated modules.

## 15. Explicit non-goals

Account 360 V1.0 does not:

- replace CRM;
- replace Sales;
- replace Inventory;
- replace Procurement;
- replace Accounts;
- maintain an independent financial ledger;
- write directly into another module's database;
- bypass Core permissions, workflows or audit;
- create a second customer identity system.

## 16. Build gate

This architecture is the first build gate. Database schema, domain code, UI implementation and module integration should proceed only from this baseline and from the detailed contracts derived from it.

**Next implementation gate:** define the Account 360 module contract, canonical account-reference model, integration/event contract and acceptance test matrix before implementing runtime/database/UI code.
