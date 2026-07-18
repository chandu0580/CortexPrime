# Dependency Impact Analysis

## Overview

Phase 2 of the Engineering Decision Engine. Determines what systems, services, and infrastructure are affected by a change by reusing Enterprise Code Intelligence.

## Architecture

```
ChangeReport
    │
    ▼
EnterpriseCodeIntelligence.analyze_impact(file)
    │
    ├── Code Dependency Graph
    ├── Service Graph
    ├── API Graph
    └── Module Graph
    │
    ▼
ImpactGraph
```

## ImpactGraph Structure

```
ImpactGraph
├── affected_modules: List[str]
├── affected_services: List[str]
├── affected_apis: List[str]
├── affected_packages: List[str]
├── affected_deployments: List[str]
├── affected_k8s_resources: List[str]
├── affected_pipelines: List[str]
├── affected_terraform_modules: List[str]
├── affected_helm_releases: List[str]
├── affected_dashboards: List[str]
├── affected_monitoring_rules: List[str]
├── affected_alert_rules: List[str]
├── affected_documentation: List[str]
└── total_affected_entities: int
```

## Infrastructure Impact Detection

| Change Type | Impact Fields |
|-------------|---------------|
| Terraform (.tf) | `affected_terraform_modules` |
| Helm chart | `affected_helm_releases` |
| Kubernetes manifest | `affected_k8s_resources` |
| Database migration | `affected_deployments` → `"database-migration"` |
| Auth/RBAC change | `affected_deployments` → `"security-layer"` |

## Implementation

Method: `EngineeringDecisionEngine._analyze_impact(change)`

Primary path: Delegates to `code_intelligence.analyze_impact(file)` for detailed dependency analysis. Limited to first 20 files for performance.

Fallback path: Uses `_classify_impact_basic()` when Code Intelligence is unavailable. Scans file paths for `/api/`, `/routes/`, `/services/`, `/controllers/` patterns.

## Reused Service

`EnterpriseCodeIntelligence` (backend/services/enterprise_code_intelligence.py:975 lines)
- Repository Scanner — languages, packages, modules, builds
- Code Parser — functions, classes, routes, services, models, components
- Dependency Graph — call, module, service, API, DB, component graphs
- Code Knowledge Graph — code entities and relationships
- Impact Analysis — affected files, APIs, tests, services, risk score
