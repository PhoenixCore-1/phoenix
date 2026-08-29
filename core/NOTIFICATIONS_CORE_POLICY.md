# Phoenix Notifications & Communications v0.1

Notifications & Communications is a **Phoenix Core capability**.

## Responsibilities

Core owns:

- notification records
- in-app notifications
- notification preferences
- notification templates
- delivery queue/status
- notification history/events
- provider-neutral channel records

## Provider boundary

External providers are adapters.

```text
Phoenix Core Notifications
        |
        +-- Email Provider Adapter
        +-- SMS Provider Adapter (future)
        +-- Push Provider Adapter (future)
        +-- WhatsApp/other adapter (future)
```

No customer-specific provider credentials or business rules belong in Core.

## Module usage

Business modules should request a notification through the Core service.

Examples:

- CRM: lead assignment
- Projects: task assignment
- Sales: quote approval
- Production: production delay
- Procurement: purchase approval
- Accounts: account alert
- Workflow: approval/action request

The business module supplies the event/context; Core controls notification
storage, preferences and delivery lifecycle.

## v0.1 boundary

This release queues notifications and tracks delivery state. It does not claim
to provide a production email/SMS provider implementation.

Provider adapters, retry workers, rate limits and production credentials are
separate controlled patches/integrations.
