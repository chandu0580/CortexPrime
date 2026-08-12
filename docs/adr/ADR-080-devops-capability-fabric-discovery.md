# ADR-080 — DevOps Capability Fabric: Discovery & the Read-First Kubernetes Vertical

Status: Accepted (discovery/direction only — no implementation) · Date: 2026-08-12 · Phase 9.0 · Follows ADR-071–079 and the Phase 5/6 governance ADRs

## Context

CortexPrime's control architecture (Phases 5–8: One Plane of Action, World Plane, Assurance, Intelligence, calibration, controlled autonomy) is complete, but it has almost no *real* DevOps capability wired into the governed execution path. Phase 9.0 is a discovery phase (companion: `docs/PHASE_9_0_DEVOPS_CAPABILITY_DISCOVERY.md`) to decide the smallest real capability fabric that proves the CortexPrime loop while preserving every Phase 5–8 invariant. No code, migration, connector, execution/governance/credential change is made here.

## Findings (evidence in the discovery doc)

1. **The governed capability surface is tiny.** Only two real governed providers exist: GitHub (5 ops, credential-blocked by Phase 5.5) and Grafana (2 ops; `folder.create_folder` is the only governed write proven end-to-end), plus the scripted `controlled` test provider. A 19-connector V1 library (Kubernetes, Terraform, CI/CD, observability, ticketing) exists but is **none** registered as a governed `ProviderOperationSpec`; all fail-closed behind `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`. AWS/Azure/GCP infra, PagerDuty, Datadog, DNS are absent.

2. **No governed-plane bypass exists.** The strictly-governed planes cannot reach an external system without the full chain; fenced by existing ERROR-severity fitness rules. The only governed egress is the sanctioned `platform.transport` gateway and the `backend.connectors` V1 quarantine (writes fail-closed behind `BND-EFFECT-GATE`; reads ungoverned). Residual bypasses (dynamic connector dispatch, sandbox `exec`, boto3/azure SDK construction) live in V1/OTHER planes and are legacy-flag-gated — with one real fitness gap: cloud SDK client construction is caught by no rule.

3. **The capability-contract gap is a *bridge*, not new semantics.** Of 15 desired capability fields, ~7 exist on the governed `CapabilityContract`, ~4 partially, and 5 are gaps (`resource_scope`, `risk_classification`, `verification_requirement`, `autonomy_ceiling`, `rate_limit`). Critically, `reversible`/`risk`/`verification`/`autonomy_ceiling` semantics already exist — but on the **Phase-8 intelligence/autonomy plane** (`contracts/intelligence/autonomy.py`), decoupled from the connectivity `CapabilityContract`. The job is to bridge the two by reuse/reference, never to duplicate the risk/autonomy types.

4. **Two pre-existing blockers stand, untouched.** (a) The **Phase 5.5 credential blocker** — no real GitHub/cloud credential authenticates; the fabric is exercised with the scripted provider. (b) The **Kubernetes WATCH blocker** — the V1 connector strips `resourceVersion`, has no `watch()`, no 410 recovery; a governed connector preserving `resourceVersion` is the prerequisite. Building WATCH on the current connector would fabricate continuity (a STOP condition).

## Decision

**Adopt a read-first Kubernetes incident-investigator as the first product vertical**, and this Phase 9 roadmap (reuse-only; no second executor/scheduler/gateway/approval/audit/world-store/assurance/calibration/autonomy):

- **9.1** Capability-contract **bridge** + registry — a governed capability declares/references its `RiskClassification`, reversibility, `verification_requirement`, `autonomy_ceiling`, `resource_scope`, reusing the Phase-8 `Capability`/`AutonomyPolicy`/`RiskLevel`.
- **9.2** Governed **Kubernetes READ** connector (`ProviderOperationSpec`, preserves `resourceVersion`): pods/deployments/events/logs → Observation → Fact → WorldQuery.
- **9.3** Kubernetes **WATCH** (resourceVersion continuity + 410 → re-LIST recovery) — no fabricated continuity.
- **9.4** Observability governed reads (Prometheus/Loki) as **corroborating** World sources (authority/lineage/freshness).
- **9.5** **K8s deployment-failure / CrashLoopBackOff investigator** (read-only, A0–A2): the full loop minus write.
- **9.6** First governed **reversible write** (K8s rollout restart of a stateless dev deployment): risk-declared, independently read-back-verified, known rollback + autonomy ceiling.
- **9.7** AWS/GitHub governed reads — DEFERRED (credential-blocked; close the cloud-SDK fitness gap first).
- **9.8** V1 strangler + hardening + final gate.

Risk/blast-radius stays operation-specific (reuse `RiskFactors`/`RiskLevel`); autonomy stays earned via `AutonomyPolicy`; observability is derived (never authoritative because newer); experience informs but never authorizes.

## Rejected / deferred

- **REJECT:** enabling any V1 write connector directly; K8s WATCH on the current connector; telemetry-as-truth; a global trust score.
- **DEFER:** AWS/Azure/GCP infra connectors; GitHub governed writes & CI/CD reads (credential blocker); Terraform governed plan/apply (human-approved, late); Datadog/PagerDuty/DNS/LB.
- **New fitness rules** (`BND-WRITE-CAPABILITY-DECLARES-RISK-AND-VERIFICATION`, `-AUTONOMY-CEILING-REQUIRED`) proposed for 9.1 only if genuinely new (CURRENT=PASS/SYNTHETIC=FAIL); do **not** add cosmetic duplicates of already-enforced invariants.

## Consequences

Phase 9 proves the CortexPrime discipline (World + Evidence + Investigation + Assurance + Earned Authority + Governed Execution) against a real read surface, then a single verifiable reversible write — the smallest honest first product loop. No uniqueness is claimed beyond the discipline; the competitive bet is that discipline beats breadth for production remediation. L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the Phase 5.5 credential blocker remain intact and untouched. No implementation occurs in Phase 9.0.
