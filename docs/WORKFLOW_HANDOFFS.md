# Workflow Handoffs — Stage-to-Stage Artifact Matrix

## Legend

Each row shows the artifacts produced by a stage and consumed by downstream stages.

| Stage | Produces | Consumes | Subsystem |
|---|---|---|---|
| `trigger_pipeline` | execution_id, pipeline context | — | RuntimeStore |
| `repository` | repo info (name, URL) | repository URL | RepositoryIntelligence |
| `workspace` | workspace_id | repo info | WorkspaceEngine |
| `sandbox_execution` | sandbox_id, sandbox result | workspace_id | ExecutionSandbox |
| `code_intel_scan` | code_intel_report | repository, branch | CodeIntelligence |
| `build` | build_id, build artifacts | workspace_id | BuildEngine |
| `qa` | test results, coverage | build_id | RuntimeStore |
| `security` | security_report | build_id | RuntimeStore |
| `patch_generation` | patch_plan | build_errors, code_intel_report | PatchPipeline |
| `engineering_review` | engineering_review | patch_plan | EngineeringExecutive |
| `approval` | approvals list | engineering_review | — |
| `pr` | — | approvals | — |
| `deployment` | deployment_id | workspace_id, build_id | DeploymentEngine |
| `gitops_sync` | gitops_result | deployment_id | ArgoCDIntelligence |
| `k8s_verification` | k8s_status | deployment_id | InfrastructureIntelligence |
| `observability` | metrics, logs, traces | deployment_id | Prometheus/Loki/Tempo |
| `root_cause_analysis` | rca_result | build_errors, tests, security, k8s_status | EnterpriseRCA |
| `learning` | learning_references | replay summary, lessons | LearningService |
| `recommendation` | recommendations | delivery context, observability, rca | RecommendationEngine |
| `replay_capture` | replay timeline | delivery_id | ReplayStore |
| `knowledge_graph` | knowledge entity | delivery summary | GraphService |
| `complete` | — | all artifacts | — |

## Cross-Service Handoff Map

```
GitHub Push
    │
    ▼
AutonomousTriggerRuntime
    │  (creates delivery via EnterpriseDeliveryOrchestrator)
    ▼
EnterpriseDeliveryOrchestrator ──► RuntimeStore (execution tracking)
    │
    ├──► RepositoryIntelligence      (stage: repository)
    ├──► WorkspaceEngine             (stage: workspace)
    ├──► ExecutionSandbox            (stage: sandbox_execution)
    ├──► CodeIntelligence           (stage: code_intel_scan)
    ├──► BuildEngine                (stage: build)
    ├──► PatchPipeline              (stage: patch_generation)
    ├──► EngineeringExecutive       (stage: engineering_review)
    ├──► DeploymentEngine           (stage: deployment)
    ├──► ArgoCDIntelligence         (stage: gitops_sync)
    ├──► InfrastructureIntelligence (stage: k8s_verification)
    ├──► Prometheus/Loki/Tempo      (stage: observability)
    ├──► EnterpriseRCA              (stage: root_cause_analysis)
    ├──► LearningService            (stage: learning)
    ├──► RecommendationEngine       (stage: recommendation)
    ├──► ReplayStore                (stage: replay_capture)
    └──► GraphService               (stage: knowledge_graph)
    │
    ▼
EventHub ──► WebSocket ──► Dashboard
ReplayStore
AnalyticsService
```

## Event Emissions

Every stage emits to three channels:
1. **EventHub** — real-time WebSocket delivery
2. **ReplayStore** — full event history for replay
3. **AnalyticsService** — metric recording
