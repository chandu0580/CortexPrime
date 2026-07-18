# Enterprise Context Intelligence

## Overview

The Enterprise Context Intelligence layer aggregates engineering context from every existing CortexPrime subsystem into a single immutable `ContextSnapshot` BEFORE any engineering decision is made.

This enables the Engineering Decision Engine to consider live operational context — not just repository changes — when reasoning about what should happen.

## Architecture

```
EngineeringDecisionEngine.analyze()
    │
    ├── Optional: context_snapshot passed by caller
    │
    └── If None: EnterpriseContextIntelligence.build_snapshot()
            │
            ├── Phase 1: RuntimeStore + CodeIntelligence
            ├── Phase 2: KnowledgeGraph (dependency)
            ├── Phase 3: Prometheus + Loki + Infrastructure + ArgoCD + GitHub + CI/CD + Terraform
            ├── Phase 4: Learning + Recommendation + RCA + Replay
            ├── Phase 5: Business context (environment, freeze, hours)
            │
            ▼
        ContextSnapshot (immutable)
            │
            ▼
        EngineeringDecisionEngine (all phases use context)
```

## File Location

`backend/services/enterprise_context_intelligence.py` (~450 lines)

## Core Classes

| Class | Phase | Purpose |
|-------|-------|---------|
| `ContextSnapshot` | 1 (Aggregation) | Immutable context for every decision |
| `DependencyContext` | 2 | Service dependencies, critical paths |
| `OperationalContext` | 3 | Alerts, health, latency, rollbacks |
| `HistoricalContext` | 4 | Past failures, RCA, recommendations |
| `BusinessContext` | 5 | Environment, freeze, hours, hotfix |

## Context Sources

| Source | Service | Data Collected |
|--------|---------|---------------|
| RuntimeStore | `enterprise_runtime_store.py` | Recent executions, dashboard stats |
| CodeIntelligence | `enterprise_code_intelligence.py` | Repository graph, code entities |
| KnowledgeGraph | `enterprise_graph_service.py` | Service dependencies, relationships |
| Prometheus | `enterprise_prometheus_intelligence.py` | Active alerts, rules, metrics |
| Loki | `enterprise_loki_intelligence.py` | Log streams, labels |
| Infrastructure | `enterprise_infrastructure_intelligence.py` | K8s clusters, pods, Docker |
| ArgoCD | `enterprise_argocd_intelligence.py` | Application sync/health status |
| GitHub | `enterprise_github_integration.py` | Recent activity, workflow runs |
| CI/CD | `enterprise_cicd_intelligence.py` | Pipeline timeline, dashboard |
| Terraform | `enterprise_terraform_intelligence.py` | Workspace state, resources |
| Learning | `enterprise_learning_service.py` | Failure patterns, lessons |
| Recommendations | `enterprise_recommendation_engine.py` | Active recommendations |
| RCA | `enterprise_root_cause_analysis.py` | Past incidents, analyses |
| ReplayStore | `mission_replay_store.py` | Replay timeline, events |

## Decision Integration

The Engineering Decision Engine now accepts an optional `context_snapshot` parameter:

```python
report = await engineering_decision_engine.analyze(
    source="github",
    event_type="push",
    payload=payload,
    context_snapshot=snapshot,  # Optional ContextSnapshot
)
```

When not provided, the decision engine automatically builds one via `EnterpriseContextIntelligence.build_snapshot()`.

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/engineering/context/snapshot` | Build full context snapshot |
| GET | `/api/engineering/context/snapshot` | Build via GET parameters |
| GET | `/api/engineering/context/health` | Check source availability |

## Context-Aware Decision Adjustments

### Risk Engine (Phase 3)
- **Active alerts**: +5 per alert (max +25)
- **Ongoing rollbacks**: +15
- **Deployment freeze**: +20
- **Maintenance window** (infra changes): -10

### Execution Planner (Phase 4)
- Future: context-aware stage selection based on operational health

### Approval Intelligence (Phase 5)
- **Deployment freeze**: Platform approval required
- **Hotfix mode**: Engineering override

### Deployment Strategy (Phase 6)
- **Hotfix mode**: HOTFIX strategy (95% confidence)
- **Deployment freeze**: NO_DEPLOYMENT
- **Cluster degraded**: BLUE_GREEN preferred
- **Ongoing rollbacks**: NO_DEPLOYMENT

### Explainability (Phase 10)
Evidence chain includes `enterprise_context` step with:
- Active alerts count
- Runtime health
- Environment
- Deployment freeze status
- Business hours
- Maintenance window
