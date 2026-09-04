# PHASE 9.5 — Implementation Map (DISCOVERY OUTPUT)

**Status: IMPLEMENTED AND VERIFIED (92/92 real-incident harness).** §§1–7 are the pre-implementation discovery, kept verbatim because they are the source-cited map the design was argued from. §8 records what the build changed.

**Discovery status when written: COMPLETE.** Every statement is cited to source read in this
session; prior phase reports were used only as pointers. No stop condition fires.

Labels: `[FACT]` read in source · `[VERIFIED]` proven by a run · `[NOT VERIFIED]`
· `[DEFERRED]` · `[BLOCKED]`.

---

## 1. The headline: the investigator is already built `[FACT]`

Phase 8 built the entire loop this phase describes. `engine.py:104-247` is the
mission's lifecycle, line for line:

```
OBSERVE     _gather_world_evidence(...)              # WorldQuery, via port
ORIENT      assembler.assemble(...)                  # deterministic, digest-stamped
PROPOSE     model.propose(...)                       # governed boundary
            -> ModelTraceUnavailable  => BLOCKED     # L14 fail-closed, pre-action
            -> ModelSchemaRejected    => step consumed, no state pretends success
RECORD      upsert_hypothesis(...)                   # proposals become OPEN hypotheses
GAPS        analyze_gaps(inv)                        # per-hypothesis, deterministic
DECIDE      select_test(candidates, ...)             # PLATFORM picks, not the model
            -> none admissible       => settle(inv)  # honest terminal read
VALIDATE    policy.validate(...)                     # TestRejected on anything smuggled
REUSE       _reuse_existing_evidence(...)            # FRESH+AFFIRMED only
ACQUIRE     evidence.acquire(...)                    # the ONLY new world contact
UPDATE      _update_differential(...)                # from the OBSERVED value
CHECKPOINT  svc.checkpoint(...)                      # durable, budget-advancing
TERMINATE   _maybe_conclude(...)
```

`[FACT]` The engine's own docstring states the invariant this phase must prove:
*"The platform controls every transition. The model never changes
status/autonomy, never creates truth, never concludes, and never executes."*

### 1.1 Component-by-component reuse `[FACT]`

| Requirement | Already exists | Cite |
|---|---|---|
| Investigation state, durable, event-sourced | `InvestigationService` + `sql_investigation.py` + `cw_investigation` (0019) | `investigation_service.py` |
| Deterministic context, 12 sections, digest | `ContextAssembler`, `SECTION_ORDER` | `context.py:32-46` |
| Governed model boundary, `extra="forbid"` | `GovernedModelProposalPort`, `InvestigationProposalSchema` | `model_boundary.py:120-201` |
| Model may not smuggle authority | schema rejects `success/verified/autonomy/provider/model/url/command` | `model_boundary.py:8-13` |
| Platform-owned test selection | `select_test` + `classify_test` | `differential.py:167-232` |
| Test admissibility (5 checks) | `EvidenceSelectionPolicy.validate` | `proposal.py:212-260` |
| Evidence-gap analysis | `analyze_gaps` | `differential.py:138-164` |
| Differential w/o numeric confidence | `HypothesisStatus` enum, `DifferentialHypothesis` | `investigation.py:199-230` |
| Honest terminal read + residual uncertainty | `settle` → `DiagnosticSummary` | `differential.py:235+` |
| Prediction lifecycle | `prediction.py` (8.5) | — |
| Independent assurance, refuses self-verification | `AssuranceVerifier.verify` | `verifier.py:169-195` |
| Historical experience as HISTORY | `experience_port`, section `historical_investigation_experience` | `engine.py:264-275` |
| Lineage-aware corroboration | `BeliefFormation._corroborate` (9.4) | `belief.py:368-425` |
| Governed K8s / Prometheus reads | 9.2 / 9.3 / 9.4 | — |

`[FACT]` **Evidence reuse already honours the mission's rules.**
`_reuse_existing_evidence` (`engine.py:290-312`): *"STALE/CONFLICTED/UNKNOWN
return None (freshness != truth; a conflict is preserved, never overwritten;
unknown is not evidence)"* — and it consumes WorldQuery's verdicts, *"it never
reclassifies them itself"*.

### 1.2 Incident input — no incident system is needed `[FACT]`

`Investigation.incident_ref: str` (`investigation.py:329`) is a **plain reference**.
The aggregate *"references World evidence (never duplicates it)"*. So the mission's
"do not create a second incident-management system" is satisfied by doing nothing:
option B (a reference) is what the contract already takes.

---

## 2. The one real gap: `EvidenceAcquisitionPort` has no production implementation `[FACT]`

`proposal.py:280-287` declares it, with the strongest docstring in the codebase:

> *"The governed READ path (backed by composition): governed read -> Observation
> -> Fact -> Belief, returning references. **This is the ONLY way the Intelligence
> Plane obtains new world evidence; it never touches a connector itself.**"*

`grep -rn "def acquire"` across `backend/` finds **only** durability internals.
Every implementation lives in `scripts/phase82…phase86_*.py` — harness stubs.

**This is the third instance of the same pattern**, and it is now a recognisable
one:

| Phase | Port declared | Production adapter | Added in |
|---|---|---|---|
| 7.2–9.2 | observation ingestion mapping | absent (harness-only) | **9.3** (`GovernedReadObserver`) |
| 8.x | `WorldReadPort` | absent (harness-only) | **9.4** (`WorldQueryEvidencePort`) |
| 8.x | `EvidenceAcquisitionPort` | **absent (harness-only)** | **9.5** ← this phase |

With this one closed, the investigation loop is composable from production code
end to end for the first time.

---

## 3. What must be built

### 3.1 `GovernedEvidenceAcquisition` — the missing port `[PLAN]`

Maps a validated `EvidenceRequest(tool, subject_ref, predicate)` onto a governed
capability read, ingests the result as an Observation, derives a Fact, and returns
references plus the **observed** value.

Read-only is a **construction-time** guarantee, not a runtime check: the adapter
refuses at construction any tool whose capability is not `SideEffectClass.READ`.
A write capability cannot be reached because it cannot be registered.

### 3.2 The CrashLoopBackOff investigation domain `[PLAN]`

A declared, frozen tool catalog — the `available_tools` the model may name — each
entry binding one tool key to one governed capability, one subject shape and one
predicate:

| Tool | Capability | Discriminates | Evidence |
|---|---|---|---|
| `k8s.pod_state` | `kubernetes.pod.get` | H1, H2 | phase, `waitingReason`, restart count |
| `k8s.pod_termination` | `kubernetes.pod.get` | H1, H4 | last-terminated `exitCode`, `reason` |
| `k8s.deployment_revision` | `kubernetes.deployment.get` | H5 | revision annotation, container image |
| `metrics.pod_memory` | `prometheus.pod_memory_bytes` | H4 | working-set bytes vs limit |
| `metrics.pod_restarts` | `prometheus.pod_restarts` | corroboration | restart count (9.4) |

`[FACT]` `kubernetes.pod.get` and `kubernetes.deployment.get` are **already
declared** in the 9.1 catalog but are not in `KUBERNETES_REAL_READ_OPERATIONS`.
Real-exposing them is a deliberate two-line extension of an existing declaration,
not a new contract.

Needed normalizer additions (declared fields, same discipline):
- `pod.get`: lift `lastState.terminated.exitCode` / `.reason` — the single most
  discriminating fact for a CrashLoopBackOff and currently not lifted.
- `deployment.get`: lift the revision annotation and the container image.
- Prometheus: one new declared op for container memory (H4's falsifier).

### 3.3 The hypothesis vocabulary `[PLAN]`

H1 startup failure · H2 configuration · H3 dependency connectivity · H4
resource/OOM · H5 deployment regression.

`[FACT]` These are **seeded as OPEN hypotheses with explicit `missing_evidence`**,
never as findings. The engine already carries `HypothesisStatus.OPEN` and a gap
reason for exactly this.

### 3.4 An explainable investigation report `[PLAN]`

Assembles what already exists — `DiagnosticSummary` (supported / eliminated /
open / residual uncertainty), the per-hypothesis evidence with source and
lineage, the corroboration assessment, and the Assurance verdict — into the
document §"INCIDENT RESULT" describes. It **computes nothing new**; inventing a
verdict here would be the one thing this phase must not do.

---

## 4. Stop-condition review

| # | Condition | Status |
|---|---|---|
| 1 | diagnosis requires a write | **No** — every tool binds a READ capability, refused at construction otherwise |
| 2 | Intelligence needs direct provider access | **No** — the two ports exist and are gate-enforced |
| 3–6 | second execution / gateway / World store / RAG | **No** — all reused |
| 7 | arbitrary PromQL | **No** — declared `static_query` (9.4) |
| 8 | arbitrary K8s paths | **No** — declared catalog (9.1) |
| 9 | model output must become truth | **No** — differential updates from the OBSERVED value |
| 10 | numeric confidence | **No** — `HypothesisStatus` is categorical |
| 11 | lineage cannot be honest | **No** — 9.4's policy carries over |
| 12 | stale evidence treated as current | **No** — `_reuse_existing_evidence` refuses STALE |
| 13 | history must override current evidence | **No** — a labelled context section only |
| 14 | Assurance must trust the investigator | **No** — it re-queries World and refuses a shared reasoning path |
| 15 | an invariant must be weakened | **No** |
| 16 | scripted disguised as real | **No** — real cluster; the model port is labelled `scripted` (§5) |

**No stop condition fires.**

## 5. Honest scope statement, decided up front `[FACT]`

`[BLOCKED]` **The model provider is scripted, and will be labelled
`provider="scripted"`.** `model_boundary.py:16-19` states the real provider is
BLOCKED while credentials are placeholders (Phase 5.5). This phase does **not**
manufacture a credential.

That boundary is exactly where it should be for what this phase claims. The model
proposes; **every** decision that matters — test selection, admissibility, the
differential update, the conclusion, the assurance verdict — is platform-owned and
deterministic, and each is verified independently of the model. A scripted
proposer therefore weakens the *"an LLM can generate good hypotheses"* claim,
which this phase does not make, and weakens nothing about the *"the platform never
lets a model's claim become truth"* claim, which is the one it does.

The **evidence** path is fully real: real cluster, real Prometheus, real governed
reads, real observations.

## 6. Fitness rules — no new rule expected `[FACT]`

- `BND-INTELLIGENCE-CANNOT-EXECUTE` — no connector/transport/credential import.
- `BND-INTELLIGENCE-CANNOT-BYPASS-WORLD` — evidence only through the World
  application layer.
- `BND-WORLD-CANNOT-EXECUTE`, `BND-DIRECT-HTTP`, `BND-PROVIDER-SDK`.

"Investigation cannot perform writes" is stronger than a fitness rule here: it is
a construction-time refusal in the tool catalog plus `EvidenceRequest`'s having no
write field at all. A rule would restate what the type system already prevents.

## 7. Minimal implementation plan

1. `backend/api/governed_evidence_acquisition.py` — the missing port + the frozen
   read-only tool catalog.
2. `backend/api/incident_investigation.py` — the CrashLoopBackOff hypothesis
   seeds and the explainable report assembler.
3. Normalizer additions: pod termination (exit code/reason), deployment revision
   and image; one Prometheus memory operation.
4. Real-expose `kubernetes.pod.get` and `kubernetes.deployment.get`.
5. `scripts/phase95_provision.sh` — reuse the 9.4 topology, plus a workload whose
   crash cause is real and whose *misleading* hypothesis is genuinely available.
6. `scripts/phase95_incident_investigator_harness.py` — requirements A–AB.
7. `tests/intelligence/test_incident_investigator.py`.
8. Docs: ADR-085, verification report, this map, memory addendum.

---

## 8. What was actually built (post-implementation)

Discovery held. The loop needed no changes at all; what was missing was the port
and the domain.

### 8.1 Files

| File | What |
|---|---|
| `backend/api/governed_evidence_acquisition.py` | `InvestigationTool`, `ToolRegistry` (read-only at construction), `GovernedEvidenceAcquisition` — the port |
| `backend/api/incident_investigation.py` | the five seeded hypotheses, the frozen tool catalog, `InvestigationReport` |
| `.../connectors/kubernetes.py` | `lastExitCode`/`lastTerminationReason` on `pod.get`; `revision`/`image` on `deployment.get`; both real-exposed |
| `.../connectors/prometheus.py` | `prometheus.pod_memory_bytes` + `INSTRUMENT_KUBELET` |
| `backend/api/observability_evidence.py` | freshness horizons for the investigator's four predicates |
| `scripts/phase95_provision.sh` | cluster + staged regression + kube-state-metrics + cAdvisor scrape + fresh Postgres |
| `scripts/phase95_incident_investigator_harness.py` | the 92-check harness |
| `tests/intelligence/test_incident_investigator.py` | 37 unit tests |

**Unchanged:** the engine, context assembler, model boundary, differential,
selection policy, investigation service, assurance verifier, prediction,
experience, calibration, autonomy. Exactly as discovery predicted.

### 8.2 What discovery got wrong, and what the build found

1. **`get deployments` was missing from the ServiceAccount.** A regression
   hypothesis stands on the deployment's revision, and the 9.3/9.4 Role granted
   only pods. The first read failed honestly (BLOCKED) rather than guessing.
2. **Four investigation predicates had no freshness horizon**, so everything the
   investigator observed was UNKNOWN freshness — honest, and useless to a loop
   whose job includes refusing stale evidence.
3. **`settle()` always says "not Assurance-verified"** — true at 8.4, misleading
   once Assurance has run. The report now names the verdict either way.
4. **`permits_action` is a method, not a property.** `not level.permits_action`
   is always False. Caught by the assertion failing on A1.
5. **A crashlooping pod alternates between Running and CrashLoopBackOff**, so the
   durable evidence of the incident is the restart count, not the instantaneous
   state.
6. **cAdvisor needed its own scrape credential** — a second ServiceAccount with
   `nodes/metrics` + `nodes/proxy`, deliberately separate from CortexPrime's, so
   which principal read what stays legible.

### 8.3 Deferred, named

**Prediction (requirement Q).** The Phase 8.5 lifecycle exists and was not
exercised: the natural regression prediction ("the failure disappears only after
the affected revision stops serving") cannot be evaluated without changing the
world, and this phase is read-only. It belongs with the first governed write.
