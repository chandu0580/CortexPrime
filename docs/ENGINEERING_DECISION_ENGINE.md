# Engineering Decision Engine

## Overview

The Engineering Decision Engine is CortexPrime's reasoning layer. Before any engineering workflow executes, the Decision Engine analyzes the change and determines WHAT should happen. This enables CortexPrime to THINK before it ACTS.

## Architecture

```
Trigger Event (GitHub Webhook / API / Cron)
    │
    ▼
EngineeringDecisionEngine.analyze()
    │
    ├── Phase 1  → Repository Change Intelligence
    ├── Phase 2  → Dependency Impact Analysis
    ├── Phase 3  → Engineering Risk Engine
    ├── Phase 4  → Execution Planner
    ├── Phase 5  → Approval Intelligence
    ├── Phase 6  → Deployment Strategy Intelligence
    ├── Phase 7  → Learning Integration
    ├── Phase 8  → Recommendation Integration
    ├── Phase 9  → Knowledge Graph
    ├── Phase 10 → Decision Explainability
    ├── Phase 11 → Executive Summary
    └── Phase 12 → Persistence to RuntimeStore
```

## File Location

`backend/services/engineering_decision_engine.py` (987 lines)

## Core Classes

| Class | Purpose |
|-------|---------|
| `EngineeringDecisionEngine` | Central decision intelligence — singleton entry point |
| `DecisionReport` | Top-level container for all phase outputs |
| `ChangeReport` | Phase 1 — what changed |
| `ImpactGraph` | Phase 2 — what is affected |
| `RiskAssessment` | Phase 3 — risk score + level + factors |
| `ExecutionPlan` | Phase 4 — which pipeline stages to run/skip |
| `ApprovalRequirements` | Phase 5 — who must approve |
| `DeploymentStrategyDecision` | Phase 6 — how to deploy |
| `DecisionRecord` | Phase 7+8 — record for learning |
| `DecisionExplanation` | Phase 10 — why every decision was made |
| `ExecutiveSummary` | Phase 11 — executive-facing report |

## Entry Point

```python
from backend.services.engineering_decision_engine import engineering_decision_engine

report = await engineering_decision_engine.analyze(
    source="github",
    event_type="push",
    payload=payload,
    repository="org/repo",
    branch="main",
    commit_sha="abc123",
)
# report is a DecisionReport with all phases populated
```

## Reused Services

| Service | File | Phase |
|---------|------|-------|
| EnterpriseCodeIntelligence | `enterprise_code_intelligence.py` | Phase 2 — impact analysis |
| EnterpriseLearningService | `enterprise_learning_service.py` | Phase 3 — past failure patterns |
| EnterpriseEventHub | `enterprise_event_hub.py` | Phase 7 — learning integration |
| MissionReplayStore | `mission_replay_store.py` | Phase 7 — decision recording |
| EnterpriseGraphService | `enterprise_graph_service.py` | Phase 9 — knowledge graph |
| EnterpriseRuntimeStore | `enterprise_runtime_store.py` | Phase 12 — persistence |

## Event Types

| Event | Constant | Phase |
|-------|----------|-------|
| `engineering.decision_made` | `EET.ENGINEERING_DECISION_MADE` | Phase 7 |

## API Routes

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/engineering/decision/analyze` | Run full decision analysis |
| GET | `/api/engineering/decision/report/{id}` | Fetch a decision report |
| GET | `/api/engineering/decision/history` | List recent decision reports |
