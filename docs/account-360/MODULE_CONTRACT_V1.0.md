# Phoenix Account 360 V1.0 — Module Contract

**Status:** Build contract
**Module code:** `account_360`
**Display name:** `Account 360`
**Version:** `1.0.0`

## 1. Module responsibility

Account 360 owns the unified account presentation, cross-module context, account timeline projection/indexing where required, and Account 360-specific orchestration.

It does not own source transactions belonging to CRM, Sales, Inventory, Procurement or Accounts.

## 2. Core dependencies

Account 360 depends on Phoenix Core for:

- tenant context;
- authenticated identity;
- authorization;
- module registration/licensing;
- navigation registration;
- audit/event infrastructure;
- workflow infrastructure;
- approved service/event contracts.

## 3. Required source contracts

The module must consume explicit contracts for:

### CRM
- canonical customer reference;
- contacts;
- customer relationship roles;
- interactions;
- calls;
- meetings/visits;
- CRM activities and notes;
- customer status/context.

### Sales
- quotes;
- sales orders;
- order status;
- commercial totals exposed by Sales;
- opportunity references where applicable.

### Inventory
- delivery references;
- POD status/reference;
- customer-linked stock/operational references where applicable;
- returns and related inventory references.

### Procurement
- only account/customer-facing procurement context explicitly exposed by Procurement contracts.

### Accounts
- account financial identity;
- credit limit/status;
- balance/exposure;
- invoices;
- payments;
- allocations;
- customer ledger;
- aging;
- collections status;
- statements;
- tax/VAT context;
- credit notes;
- adjustments;
- disputes;
- financial documents;
- financial audit context;
- controlled financial commands.

## 4. Canonical reference

Every Account 360 record must be anchored to a Phoenix canonical account/customer identifier and tenant identifier.

Module-local IDs are retained only as source references and must never replace the canonical identity.

## 5. Read model rule

Account 360 may maintain projections for fast presentation, search, timeline ordering and integration state. Projections must carry source ownership and freshness metadata where required.

Financial values that require authoritative accuracy must be obtained from Accounts-controlled services when necessary rather than trusting an unverified projection.

## 6. Command rule

Account 360 commands are limited to actions that belong to the Account 360 experience or explicitly delegated orchestration.

Examples:

- open/drill into source records;
- create an Account 360 follow-up/workflow item through Core;
- request a source-module action through its contract.

Financial mutations must be executed by Accounts. Sales mutations must be executed by Sales. Inventory mutations must be executed by Inventory, and so on.

## 7. Event handling

Account 360 should subscribe to approved events such as:

- account/customer created or changed;
- contact changed;
- CRM interaction recorded;
- quote created/updated;
- order created/updated;
- delivery/POD changed;
- invoice issued/changed;
- payment recorded;
- payment allocated;
- credit note/adjustment recorded;
- dispute changed;
- collection status changed;
- document added/changed.

Exact event names and payload schemas are to be derived from the existing Phoenix Core integration/event contracts rather than invented independently.

## 8. Idempotency and ordering

Event consumers must tolerate duplicate delivery. Where ordering matters, the consumer must use source event/version metadata and reject or safely defer obsolete events.

## 9. Failure handling

Integration failures must be captured with enough context for retry/reconciliation. A failed projection update must not alter source-of-truth state.

## 10. Observability

The module must expose sufficient operational telemetry for:

- event consumption;
- failed integrations;
- projection lag;
- projection rebuilds;
- command failures;
- authorization failures;
- performance of Account 360 queries.

## 11. Security contract

All requests carry tenant and authenticated-user context. Authorization is evaluated server-side against Core/owning-module policy.

No module may obtain broader financial access by calling Account 360 instead of Accounts.

## 12. UI contract

Account 360 registers its navigation through Core. The Account 360 route must support direct account context, controlled section navigation, source-record drill-down and correct return/back-stack behaviour.

## 13. Versioning

The contract is versioned independently from implementation patches. Breaking changes require an explicit contract version increment and compatibility review.
