# End-to-End Autonomous Engineering Workflow

## Overview

The autonomous engineering workflow connects **GitHub push events** directly to an **Executive Dashboard** through a 22-stage delivery pipeline. Every stage delegates to an existing subsystem — no new orchestrators, engines, or services were created.

The entire pipeline runs within the **EnterpriseDeliveryOrchestrator**, which already existed as the central delivery state machine. It was extended from 12 to 22 stages, with failure recovery, approval gates, artifact tracking, and observability built in.

## Trigger Chain

```
1. GitHub Webhook ──► EventBus
2. AutonomousTriggerRuntime subscribes to EventBus
3. On push event, extracts: branch, commit, repo_url, pusher
4. Creates delivery via EnterpriseDeliveryOrchestrator.create_delivery()
5. Injects pipeline context artifacts (branch, repo_url, commit)
6. Calls start_delivery() — enters state machine
```

## Pipeline Architecture

### Stage Execution

Each stage follows the same pattern:
1. `_update_runtime_stage(id, stage, "running")` — sync to RuntimeStore
2. Delegate to subsystem (e.g., `BuildEngine`, `DeploymentEngine`)
3. Store result artifacts in `DeliveryBlueprint`
4. `_update_runtime_stage(id, stage, "completed")` — sync completion

On failure:
1. `_update_runtime_stage(id, stage, "failed")` — sync failure
2. Recovery logic triggers (patch/rollback) or transitions state to `failed`/`retrying`

### Artifact Passing via DeliveryBlueprint

The `DeliveryBlueprint` class carries all stage outputs:
- `build_errors`, `patch_plan`, `code_intel_report` — build/patch/intel results
- `engineering_review`, `approvals` — review/approval state
- `deployment`, `gitops_result`, `k8s_status` — deployment artifacts
- `observability`, `rca_result` — monitoring/RCA data
- `learning_references`, `recommendations` — knowledge artifacts
- `replay`, `sandbox_id` — execution trace

All fields roundtrip through `to_dict()` / `from_dict()`.

### Observability

Every stage emits to three channels via `_emit_all()`:
1. **EnterpriseEventHub** — real-time WebSocket delivery to Dashboard
2. **MissionReplayStore** — full event history for debugging/replay
3. **EnterpriseAnalyticsService** — metric recording for dashboards

### Failure Recovery

**Build/QA/Security failures:**
```
Stage fails ──► record build_errors ──► PatchPipeline.create_plan()
    ──► PatchPipeline.generate_candidates() ──► PatchPipeline.compare_candidates()
    ──► retry failed stage ──► success → continue
```

**Deployment/K8s verification failures:**
```
Stage fails ──► DeliveryRollbackEngine.rollback()
    ──► redeploy ──► success → continue
```

### Approval Gates

The `approval` stage checks `blueprint.approvals`. If insufficient, it:
1. Transitions delivery to `waiting_approval` state
2. Returns the delivery (pipeline pauses)
3. On manual approval: `update_blueprint()` adds approvals → `resume_delivery()`
4. Pipeline resumes from `approval` stage

## Subsystems Reused (Zero New Services)

| Subsystem | Role |
|---|---|
| EnterpriseDeliveryOrchestrator | Central state machine (extended) |
| AutonomousTriggerRuntime | Webhook trigger (extended) |
| RuntimeStore | Execution state persistence |
| EnterpriseEventHub | Event emission |
| MissionReplayStore | Replay capture |
| EnterpriseAnalyticsService | Metric recording |
| WorkspaceEngine | Workspace + repository management |
| ExecutionSandbox | Isolated execution environment |
| CodeIntelligence | Code analysis |
| BuildEngine | Build execution |
| PatchPipeline | Auto-patch generation |
| EngineeringExecutive | Code review |
| DeploymentEngine | Deployment orchestration |
| ArgoCDIntelligence | GitOps sync |
| InfrastructureIntelligence | K8s health verification |
| PrometheusIntelligence | Metrics query |
| LokiIntelligence | Log query |
| TraceIntelligence | Trace query |
| EnterpriseRCA | Root cause analysis |
| LearningService | Lesson recording |
| RecommendationEngine | Recommendation generation |
| GraphService | Knowledge graph updates |
| PatchEngine | Patch rollback |
