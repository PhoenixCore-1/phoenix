# Phoenix Repository Architecture

## 1. Repository Root

The Phoenix directory is the authoritative local working repository.

The GitHub repository must mirror this clean working tree.

Historical development material remains outside the active repository unless explicitly approved.

---

## 2. Backend / Frontend Separation

Phoenix backend and frontend are separate architectural layers.

Frontend:

    frontend/

Backend:

    core/
    system-platform/
    pca-company-platform/
    modules/

The frontend communicates with backend services through defined API contracts.

The frontend must never connect directly to the database.

---

## 3. Phoenix Core

Location:

    core/

Phoenix Core contains generic, reusable Phoenix platform capabilities.

Core must remain independent of customer-specific business logic, confidential information, ERP mappings and proprietary processes.

Core changes require controlled patches and regression testing.

---

## 4. System Platform

Location:

    system-platform/

The System Platform contains Phoenix platform-wide control and administration functionality.

It is distinct from the PCA Company Platform.

The System Platform must not become a second PCA Company Platform.

---

## 5. PCA Company Platform

Location:

    pca-company-platform/

The PCA Company Platform is the company/tenant-level control and configuration layer within the Phoenix customer/company data plane.

It consumes Phoenix Core contracts.

Customer-specific company functionality belongs here or in appropriate modules/configuration/adapters.

---

## 6. Modules

Location:

    modules/

Business modules are independently maintained Phoenix modules.

Modules must consume approved Core and platform contracts rather than bypassing architectural boundaries.

---

## 7. Frontend

Location:

    frontend/

Frontend is separated from backend implementation.

    frontend/
    ├── shared/
    ├── system-platform/
    ├── company-platform/
    └── tenant/

Shared frontend components may be used by the supported Phoenix application platforms.

Authentication and data access are provided through backend/API contracts.

---

## 8. Tests

Location:

    tests/

Tests are maintained separately from production source.

Approved source must be tested before being promoted as working/authoritative code.

---

## 9. Migrations

Location:

    migrations/

Database migrations and controlled schema changes belong here.

Production databases and local runtime databases must not be committed to the repository.

---

## 10. Documentation

Location:

    docs/

Architecture decisions, contracts, policies and controlled project documentation belong here.

---

## 11. Assets

Location:

    assets/

Shared approved Phoenix assets belong here.

---

## 12. Patch Rule

Phoenix changes are performed through controlled patch files and PowerShell execution.

Manual editing of working source files using Notepad or other uncontrolled editors is not permitted.

A patch must be:

1. Created deliberately.
2. Applied through PowerShell.
3. Tested.
4. Reviewed.
5. Promoted into the clean working tree only after validation.

Historical patch files remain outside the active repository unless explicitly approved.

---

## 13. Working Source vs Historical Material

The active Phoenix repository contains approved working source only.

Historical material includes:

- backups
- beta versions
- PASSED snapshots
- experimental builds
- temporary test builds
- obsolete patches
- development archives

Historical material remains outside the active repository unless specifically promoted.

---

## 14. GitHub Rule

GitHub is the remote mirror of the approved Phoenix working repository.

Unfinished experiments, historical backups, confidential data, local databases and temporary development artifacts must not be pushed to GitHub.

---

## 15. Database Boundary

Applications must access data through the appropriate backend/service layer.

Frontend code must never access SQL databases directly.

---

## 16. Approval Flow

    Development
        |
        v
    Controlled Patch
        |
        v
    PowerShell Apply
        |
        v
       Tests
        |
        v
     Review
        |
        v
 Approved Working Tree
        |
        v
      Git Commit
        |
        v
       GitHub

This structure is the authoritative Phoenix repository organization going forward.
