# Phoenix Core v1.0 — Complete Runnable Baseline

This package contains the complete runnable source set from the Phoenix Core
foundation build, including all Python dependencies required by `app.py`.

## Run

```text
python app.py
```

Then open:

```text
http://localhost:8080
```

## Included

- app.py
- core.py
- schema.sql
- index.html
- security/admin foundation
- notifications
- module contract/foundation
- the current application module implementations required by the runnable app:
  CRM, Projects, Sales, Production, Inventory, Procurement, Accounts,
  Workflow, Reporting and Integrations.

## Important architecture note

The current runnable baseline contains these module implementations because
the existing app.py imports them directly. They are included here so this
package is genuinely runnable and complete.

The next Phoenix development step should separate these business modules into
their own project/module packages while preserving this Core baseline. That
separation should be treated as a controlled architectural refactor, not as
an undocumented change to the frozen baseline.

Do not delete dependency files from this package unless the application is
refactored and regression-tested first.
