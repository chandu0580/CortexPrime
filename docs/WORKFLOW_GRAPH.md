# Autonomous Engineering Workflow — Stage Graph

## 22-Stage Delivery Pipeline

```
GitHub Push
    │
    ▼
┌─ 1. trigger_pipeline ──────────────────────────────────────┐
│   Register execution in RuntimeStore, create pipeline context │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 2. repository ────────────────────────────────────────────┐
│   Analyze repository metadata (branch, URL, commit info)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 3. workspace ─────────────────────────────────────────────┐
│   Create isolated workspace for the delivery                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 4. sandbox_execution ─────────────────────────────────────┐
│   Execute in isolated sandbox, prepare repository           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 5. code_intel_scan ───────────────────────────────────────┐
│   Analyze codebase: modules, dependencies, impact analysis   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 6. build ─────────────────────────────────────────────────┐
│   Compile/build from workspace                              │
│   ┌─ On failure ──► patch_generation ──► retry build ───┐  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 7. qa ────────────────────────────────────────────────────┐
│   Run test suite, collect coverage                         │
│   ┌─ On failure ──► patch_generation ──► retry QA ──────┐  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 8. security ──────────────────────────────────────────────┐
│   Vulnerability scan, compliance check                     │
│   ┌─ On failure ──► patch_generation ──► retry security ─┐  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 9. patch_generation ──────────────────────────────────────┐
│   Auto-generate fix patches (triggered by build/QA/security  │
│   failures or run as standard stage)                        │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 10. engineering_review ───────────────────────────────────┐
│    Architect + reviewer agents evaluate changes             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 11. approval ─────────────────────────────────────────────┐
│    Wait for required approvals                              │
│    ┌─ Pending ──► waiting_approval (delivery paused) ──┐   │
│    │   On approve ──► continue                             │   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 12. pr ───────────────────────────────────────────────────┐
│    Create pull request with changes                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 13. deployment ───────────────────────────────────────────┐
│    Deploy to target environment (rolling update)            │
│    ┌─ On failure ──► rollback ──► redeploy ────────────┐   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 14. gitops_sync ──────────────────────────────────────────┐
│    Sync with ArgoCD/manifest repository                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 15. k8s_verification ─────────────────────────────────────┐
│    Verify K8s deployment health (pods, services, ingress)   │
│    ┌─ On failure ──► rollback ──► redeploy ────────────┐   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 16. observability ────────────────────────────────────────┐
│    Collect metrics (Prometheus), logs (Loki), traces (Tempo) │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 17. root_cause_analysis ──────────────────────────────────┐
│    Analyze failures across build, test, security, K8s       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 18. learning ─────────────────────────────────────────────┐
│    Record lessons learned, update knowledge base            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 19. recommendation ───────────────────────────────────────┐
│    Generate recommendations from delivery results           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 20. replay_capture ───────────────────────────────────────┐
│    Capture full event timeline for replay/debug             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 21. knowledge_graph ──────────────────────────────────────┐
│    Update enterprise knowledge graph with delivery entity   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─ 22. complete ─────────────────────────────────────────────┐
│    Finalize delivery, mark completed                       │
└────────────────────────────────────────────────────────────┘
                         │
                         ▼
              Executive Dashboard
```

## Stage Recovery Transitions

| Failed Stage | Recovery Action | Retry Count |
|---|---|---|
| `build` | `patch_generation` → retry `build` | 1 attempt |
| `qa` | `patch_generation` → retry `qa` | 1 attempt |
| `security` | `patch_generation` → retry `security` | 1 attempt |
| `deployment` | `rollback` → retry `deployment` | 1 attempt |
| `k8s_verification` | `rollback` → retry `deployment` | 1 attempt |

## State Machine Transitions

```
pending  ──► queued ──► running ──► waiting_approval ──► running
                                  │                      │
                                  ├──► paused ──► resumed ──► running
                                  │
                                  ├──► retrying ──► running
                                  │
                                  ├──► completed
                                  │
                                  └──► failed ──► retrying
                                                └──► cancelled
```
