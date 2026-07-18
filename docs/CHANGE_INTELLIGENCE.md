# Repository Change Intelligence

## Overview

Phase 1 of the Engineering Decision Engine. Determines what changed by analyzing webhook payloads and categorizing every modified file.

## Detection Categories

| Category | Detection Pattern | Risk Weight |
|----------|-----------------|-------------|
| `frontend` | `/frontend/`, `/ui/`, `/web/`, `.tsx`, `.jsx`, `.vue`, `.css`, `.scss` | 10 |
| `backend` | `/backend/`, `/api/`, `/server/`, `.py`, `.go`, `.rs`, `.java`, `.cs` | 35 |
| `api` | API route files | 55 |
| `database` | `/migrations/`, `/migrate/`, `migration` | 90 |
| `infrastructure` | `terraform`, `.tf`, `helm`, `dockerfile`, `kubernetes`, `k8s` | 70 |
| `configuration` | `.env`, `.config`, `config.`, `settings`, `.yaml`, `.toml` | 45 |
| `authentication` | `auth`, `oauth`, `login`, `password`, `token` | 80 |
| `rbac` | `rbac`, `permission`, `role`, `policy` | 75 |
| `secrets` | `secret`, `vault`, `credential` | 85 |
| `test` | `/test`, `/spec`, `_test.`, `_spec.`, `.test.`, `.spec.` | 5 |
| `documentation` | `/docs/`, `.md`, `.rst`, `/wiki/` | 2 |
| `cicd` | CI/CD pipeline files | 40 |
| `dependency` | `requirements`, `package`, `yarn.lock`, `go.mod` | 30 |

## ChangeReport Structure

```
ChangeReport
├── changed_files: List[str]
├── changed_folders: List[str]
├── changed_services: List[str]
├── changed_apis: List[str]
├── has_db_migrations: bool
├── has_infrastructure_changes: bool
├── has_frontend_changes: bool
├── has_backend_changes: bool
├── has_test_changes: bool
├── has_documentation_changes: bool
├── has_config_changes: bool
├── has_auth_changes: bool
├── has_rbac_changes: bool
├── has_secret_changes: bool
├── has_dependency_changes: bool
├── categories: List[ChangeCategory]
├── summary: str
└── raw_payload: Dict[str, Any]
```

## Implementation

Method: `EngineeringDecisionEngine._analyze_change(payload)`

Webhook payloads are parsed for `commits[].added`, `commits[].modified`, `commits[].removed`, and `head_commit` fields. Files are deduplicated, then classified by path patterns. Changed services are extracted by scanning for `services/`, `service/`, `apps/`, `app/` folder patterns.

## Key Design Decisions

1. **Pattern-based classification** — No AST parsing needed for change detection; file path patterns are sufficient and fast
2. **Multi-category changes** — A single file can trigger multiple categories (e.g., `backend/auth/rbac.py` triggers `backend` + `authentication` + `rbac`)
3. **Service discovery** — Service names are extracted from path structure, not from configuration files
