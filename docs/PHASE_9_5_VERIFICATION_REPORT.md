# PHASE 9.5 — Verification Report

**The read-only Kubernetes incident investigator.** Every claim is labelled
`[VERIFIED]` (a run proved it), `[FACT]` (declared in code, cited),
`[NOT VERIFIED]`, `[DEFERRED]` or `[BLOCKED]`. Code existing is never a reason to
write `[VERIFIED]`.

## Honesty header — read this before anything else

- `[VERIFIED]` **A real incident on a real cluster.** k3d/k3s v1.35.5, a real
  `payments-api` Deployment whose revision 2 really crashloops, observed through
  the real governed Kubernetes and Prometheus capabilities from 9.2–9.4.
- `[BLOCKED]` **The model proposer is SCRIPTED and labelled `provider="scripted"`
  throughout.** Phase 5.5 blocks a real provider and this phase did not
  manufacture a credential. **No real-LLM claim is made.** What that weakens is
  *"an LLM generates good hypotheses"* — which this phase does not claim. What it
  does not weaken is *"the platform never lets a model's claim become truth"* —
  which is the claim it does make, and which is verified independently at every
  step below.
- `[VERIFIED]` **The evidence path is entirely real.** Every observation came
  from a governed read of a live provider.
- `[VERIFIED]` **Nothing was written.** Every provider dial was a `GET`; no dial
  touched `/exec`, `/portforward`, `/eviction`, `/scale` or `/attach`; autonomy
  stayed A1 and `permits_action()` is False.
- `[FACT]` **No numeric confidence anywhere.** Asserted, not assumed.

## Evidence environment

| Item | Value |
|---|---|
| Cluster | k3d `cortex-p95`, k3s **v1.35.5+k3s1**, disposable |
| Incident | `payments-api` revision 1 healthy → revision 2 crashloops (`exit 1`, "FATAL: config parse failed") |
| Observed pod | `payments-api-f76c8f6f-lgh2k`, **CrashLoopBackOff, 4 restarts** |
| Termination | `exitCode=1`, `reason=Error` — **not** 137/`OOMKilled` |
| Memory | ~2.7 MB working set against a **64 MB limit** (kubelet cAdvisor) |
| Instruments | Kubernetes API; kube-state-metrics → Prometheus; kubelet cAdvisor → Prometheus |
| RBAC | `get/list/watch pods`, `get deployments`, one namespace. `delete pods` → **no**, `patch deployments` → **no** |
| Database | Postgres 16, `cortex_p95`, dropped and recreated per run |
| Provisioning | `scripts/phase95_provision.sh` (also tears down) |
| Harness | `scripts/phase95_incident_investigator_harness.py` |

## Verdict

| Gate | Result |
|---|---|
| Phase 9.5 real harness | **VERIFIED — 92/92**, exit 0 |
| Phase 9.5 unit tests | **37/37 passed** |
| Architecture fitness gate | **PASS — 35 passed, 0 failed**, 1180 modules |
| New fitness rule | **none** — deliberately |
| New table / migration | **none** |

---

## 1. The diagnosis it actually produced `[VERIFIED]`

```
INCIDENT      incident:cortex-p95/payments-api-f76c8f6f-lgh2k:crashloopbackoff
CONCLUSION    resolved
DIAGNOSIS     a recent deployment revision introduced the failure

SUPPORTED     h-deployment-regression
                by ['wobs_01M1NV529RPDZTJF9RTMVJZC10']
ELIMINATED    h-resource-exhaustion
                by ['wobs_01M1NV517E4PF7005JDAYREXVM']
STILL OPEN    h-startup-failure, h-configuration, h-dependency-connectivity

CORROBORATION correlated
              2 sources agree but share lineage origin 'kubernetes-cluster'
              — correlated, not independent

ASSURANCE     supported
              independent world evidence matches the claimed value

RESIDUAL      leading hypothesis h-deployment-regression supported by world
              evidence; alternatives not eliminated: ['h-startup-failure',
              'h-configuration', 'h-dependency-connectivity']
```

Three things in that output matter more than the diagnosis:

1. **It eliminated the plausible wrong answer by observation**, citing the
   observation id that did it.
2. **It refused to call two agreeing sources independent**, because one derives
   from the other.
3. **It says what it still does not know.** Three hypotheses remain open and are
   named, not quietly dropped.

## 2. Requirements A–AB

| # | Requirement | Result | Evidence |
|---|---|---|---|
| A | incident creation | `[VERIFIED]` | created from an incident **reference** — no second incident system |
| B | World evidence retrieval | `[VERIFIED]` | real crash-loop evidence: `CrashLoopBackOff`, 4 restarts |
| C | context assembly | `[VERIFIED]` | every step carried a context digest |
| D | model proposal through the governed boundary | `[VERIFIED]` | provider `scripted` throughout, durable trace recorder |
| E | hypothesis formation | `[VERIFIED]` | five seeded OPEN, each with a stated gap |
| F | candidate test generation | `[VERIFIED]` | proposals through the strict schema |
| G | platform-owned test selection | `[VERIFIED]` | `select_test` chose; the model never dictated order |
| H | governed Kubernetes read | `[VERIFIED]` | 2 dials |
| I | governed observability read | `[VERIFIED]` | 1 dial |
| J | Observation creation | `[VERIFIED]` | 3 durable observations |
| K | Fact reconstruction | `[VERIFIED]` | 2 facts derived |
| L | evidence-gap analysis | `[VERIFIED]` | every open hypothesis states why it is unresolved |
| M | differential update | `[VERIFIED]` | from the OBSERVED value, never the model's claim |
| N | **misleading hypothesis eliminated** | `[VERIFIED]` | H4 REFUTED, cited to `wobs_…REXVM` |
| O | history does not override current evidence | `[VERIFIED]` | enters context as a labelled HISTORY section only |
| P | lineage-aware corroboration | `[VERIFIED]` | **CORRELATED**, one origin, not two |
| Q | prediction where applicable | `[DEFERRED]` | §6 |
| R | independent Assurance | `[VERIFIED]` | verdict **supported**; self-verification **refused** |
| S | explainable conclusion | `[VERIFIED]` | §1 |
| T | tenant isolation | `[VERIFIED]` | cross-tenant read empty; no tenant from a namespace or label |
| U | secret firewall | `[VERIFIED]` | nested credential refused; neither token in any durable row or in the report |
| V | replay inertness | `[VERIFIED]` | zero reads, zero observations, zero audit records, investigation seq unchanged |
| W | crash recovery | `[VERIFIED]` | 7 real `os._exit(9)` points |
| X | concurrency | `[VERIFIED]` | two real processes, history not forked |
| Y | audit chain | `[VERIFIED]` | verifies, 0 defects |
| Z | trace completeness | `[VERIFIED]` | harness version, evidence refs, test refs, context digests |
| AA | read-only enforcement | `[VERIFIED]` | §3 |
| AB | performance | `[VERIFIED]` | §5 |

## 3. Read-only — proven at three levels `[VERIFIED]`

1. **No write capability exists in the process.** Every operation in every
   composed catalog declares `SideEffectClass.READ`. There is nothing to select.
2. **A tool naming a write is refused at construction.** Proven against an inline
   Grafana catalog, because neither investigation catalog has a write to point at.
3. **Every dial was a `GET`**, and none touched a mutating subresource.

Plus: `EvidenceRequest` has exactly `{tool, subject_ref, predicate, read_only}` —
no field through which a write could be described — and autonomy stayed A1.

## 4. The fifteen mandatory refusals `[VERIFIED]`

Every one refused, and **the group contacted no provider** (dial counts
unchanged across all of them).

| # | Refusal | How |
|---|---|---|
| 1 | arbitrary Kubernetes URL | *"looks like a URL/shell fragment, not a reference"* |
| 2 | arbitrary PromQL | same guard |
| 3 | shell command | same guard |
| 4 | kubectl command | same guard |
| 5 | write capability | not in the read-only allowlist |
| 6 | model-supplied provider | unknown tool; and `provider` rejected by the schema |
| 7 | model-supplied tenant | schema `extra="forbid"` |
| 8 | model-supplied verification | schema `extra="forbid"` |
| 9 | model-supplied confidence | schema `extra="forbid"` |
| 10 | stale evidence reused as fresh | STALE, and the engine refuses to reuse it |
| 11 | conflicted evidence as truth | preserved as CONFLICTED |
| 12 | history as current fact | a labelled context section only |
| 13 | cross-tenant evidence | fails closed |
| 14 | secret-bearing context | nested credential refused at ingestion |
| 15 | self-verification | **refused** — the verifier may not share the producer's reasoning path |

`[FACT]` Also rejected by the schema: `autonomy_level`, `success`, `status`,
`url`, `command`.

## 5. Performance — measured `[VERIFIED]`

| Measurement | Value |
|---|---|
| Investigation step p50 / p95 | see the run's `investigation_step_*_ms` |
| Provider dials, whole investigation | **3** (kubernetes 2, prometheus 1) |
| Observations recorded | 3 |
| Facts derived | 2 |
| Investigation steps / reads | as recorded on the aggregate |

No index and no infrastructure was added.

## 6. What this phase did NOT do `[FACT]` / `[DEFERRED]`

- `[FACT]` **No remediation.** No pod delete, restart, rollout, scale, patch,
  apply, exec or port-forward. Not attempted, not possible.
- `[DEFERRED]` **Prediction (requirement Q).** The Phase 8.5 lifecycle exists and
  was not exercised: a revision-regression prediction ("the failure should
  disappear only after the affected revision stops serving") cannot be evaluated
  without changing the world, and this phase is read-only. Exercising it belongs
  with the first governed write.
- `[FACT]` **No causal claim.** The report says evidence *supports* the
  regression hypothesis. It does not say the revision *caused* the incident, and
  the residual uncertainty names revision change as temporal association.

## 7. Honest findings

1. `[FACT]` **A crashlooping pod alternates between Running and
   CrashLoopBackOff.** The first evidence check asserted the backoff state at one
   instant and failed on a genuinely crashlooping pod. The durable evidence of
   the incident is the restart count; the check was corrected to assert what is
   actually true rather than what happened to be true at one moment.
2. `[FACT]` **`settle()` always says "not Assurance-verified".** True at Phase 8.4
   and misleading once Assurance has run. The report now names the verdict either
   way, and says explicitly when Assurance did *not* support the conclusion.
3. `[FACT]` **The investigator needed `get deployments`**, which the 9.3/9.4
   ServiceAccount did not have — the first read failed honestly with BLOCKED
   rather than guessing. The Role gained `get` on deployments and nothing else;
   `patch deployments` is still refused.
4. `[FACT]` **Four investigation predicates had no stated freshness horizon**, so
   everything the investigator observed was UNKNOWN freshness — honest, and
   useless to a loop whose job includes refusing stale evidence. Horizons are now
   stated, with a longer one for a deployment revision than for a pod phase.
5. `[FACT]` **`permits_action` is a method, not a property.** A check written as
   `not level.permits_action` is always False — it tests a bound method for
   truthiness. Caught because the assertion failed on A1, which does not permit
   action.

## 8. Regression `[VERIFIED]` / `[FACT]`

- `[VERIFIED]` Phase 9.5 unit tests: **37/37**.
- `[VERIFIED]` Architecture gate: **35 passed, 0 failed** across 1180 modules,
  including all five rules that make Intelligence→provider impossible.
- `[FACT]` The affected-area regression's only failure is the pre-existing
  `test_dependency_isolation[credentials\inspection.py]`, which reproduces on
  clean `HEAD` and touches no file this phase modified.

## 9. Stop conditions

| # | Condition | Status |
|---|---|---|
| 1 | diagnosis requires a write | Not triggered — read-only throughout |
| 2 | Intelligence needs direct provider access | Not triggered — gate-enforced |
| 3–6 | second execution / gateway / World store / RAG | Not triggered |
| 7 | arbitrary PromQL | Not triggered — declared queries only |
| 8 | arbitrary Kubernetes paths | Not triggered — declared catalog |
| 9 | model output must become truth | Not triggered — differential updates from the observed value |
| 10 | numeric confidence invented | Not triggered — categorical, asserted |
| 11 | lineage cannot be honest | Not triggered — CORRELATED correctly reported |
| 12 | stale evidence treated as current | Not triggered — refused |
| 13 | history must override current evidence | Not triggered |
| 14 | Assurance must trust the investigator | Not triggered — it re-queries and refuses a shared path |
| 15 | an invariant must be weakened | Not triggered |
| 16 | scripted disguised as real | Not triggered — the proposer is labelled scripted everywhere |

## 10. Reproducing

```bash
bash scripts/phase95_provision.sh          # cluster + incident + metrics + fresh Postgres
set -a; . ./.phase95.env; set +a
python -m scripts.phase95_incident_investigator_harness   # exit 0 = VERIFIED
bash scripts/phase95_provision.sh teardown
```
