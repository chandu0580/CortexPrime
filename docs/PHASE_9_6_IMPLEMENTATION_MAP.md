# PHASE 9.6 — Implementation Map (DISCOVERY OUTPUT)

**Status: DISCOVERY COMPLETE — NO PRODUCTION CODE WRITTEN.** Two findings change
what this phase can honestly claim (§2, §3). No stop condition fires, but §2
requires a decision you should see before I build.

Labels: `[FACT]` read in source · `[VERIFIED]` proven by a run · `[BLOCKED]` ·
`[DEFERRED]`.

---

## 1. The governance apparatus is already complete `[FACT]`

Every gate this phase's mission enumerates already exists and is already wired.
`AutonomyPolicy.evaluate` (`backend/intelligence/application/autonomy.py:71-200`)
runs them **in this order**, before any action is permitted:

| # | Gate | Cite |
|---|---|---|
| 1 | **Emergency stop** — blocks new autonomous actions | `autonomy.py:99-102` |
| 2 | **Circuit breaker** — a tripped breaker halts autonomy | `autonomy.py:105-108` |
| 3 | **Blast-radius cap by risk** — deterministic, "never a model score" | `autonomy.py:117-124` |
| 4 | **Version compatibility** — calibration must match the current model/harness | `autonomy.py:127-135` |
| 5 | **Calibration evidence** — required to *earn* action; INSUFFICIENT_DATA refuses | `autonomy.py:138-151` |
| 6 | **Assurance coverage floor** | `autonomy.py:155-160` |
| 7 | **Drift** — downgrades authority to non-action | `autonomy.py:163-169` |
| 8 | **Stale / conflicted world** — downgrades to non-action | `autonomy.py:172-181` |
| 9 | **Reversibility** — an irreversible mutating action at/above A3 forces `HUMAN_APPROVAL_REQUIRED` and **no delegated autonomy** | `autonomy.py:184-190` |
| 10 | Approval requirement for the earned level | `autonomy.py:193-200` |

The result is an `AutonomyDecision` carrying `requested_level`, `allowed_level`
and `effective_level` — exactly the three the mission asks to be proven.

### 1.1 Human approval is already typed, scoped and digest-bound `[FACT]`

`ApprovalFacts.is_valid_for` (`connectivity/application/authorization.py:107-127`)
checks **five** things, each with a stated reason:

```
outcome is GRANTED              …an approval that was denied authorizes nothing
not expired                     …"an expired approval authorizes nothing"
scope_tenant_id == tenant       …"an approval for tenant A must not authorize tenant B"
operation matches               …"an approval to READ must not authorize DELETE"
bound_digest == capability_digest …"version 1 must not authorize version 2"
```

`NoApprovals` fails closed. `PolicyEffect.REQUIRE_APPROVAL` is emitted for
risk ≥ the configured threshold (`policy.py:238-255`), and only a *valid* approval
converts it to ALLOW (`authorization.py:252-267`).

`[FACT]` **`HumanEvent` already refuses `approver_name = "admin"`**: *"actor_ref
must be a namespaced identity reference … never a bare name"*
(`investigation.py:305-311`). The mission's requirement is a construction-time
invariant that predates it.

`[FACT]` `ApprovalArtifact` has **no `summary` field**, deliberately: *"A
separately-supplied summary is precisely the attack that defeated
human-in-the-loop review in published penetration testing."*

### 1.2 Everything else is reuse

Capability catalog, authorization chain, lease, scheduler, dispatcher, gateway,
transport, audit chain, World Plane, Observation/Fact/WorldQuery,
PredictionLifecycle (8.5), AssuranceVerifier, calibration (8.7), the investigator
(9.5) and the three now-closed ports (9.3/9.4/9.5) are all reused unchanged.

---

## 2. FINDING 1 — rollout restart is **NOT reversible**, and must not be called so `[FACT]`

This is the finding the mission most wants tested, and the answer is no.

`SideEffectClass.REVERSIBLE_WRITE` is defined as *"Changes state; **a declared
inverse fully restores the prior state**"*, and `requires_inverse` is True for it
(`contracts/execution.py:48-59`).

A Kubernetes rollout restart is:

```
PATCH /apis/apps/v1/namespaces/{ns}/deployments/{name}
{"spec":{"template":{"metadata":{"annotations":{"…/restartedAt":"<value>"}}}}}
```

It **mutates the pod template** (an annotation), which changes the template hash,
which creates a **new ReplicaSet and a new revision in the rollout history**.
There is no operation that removes the annotation and restores the prior revision
number. `kubectl rollout undo` does not undo it — it creates *another* revision.

So the mission's suggested framing — *"does not mutate the desired deployment
specification"* — is **false as stated**, and I will not use it. The pod template
is part of the spec.

**Honest classification: `IRREVERSIBLE_WRITE`, `reversible=False`.**

`[FACT]` **This requires no policy weakening — the existing model handles it
correctly and lands exactly where the mission wants:** gate 9 fires
(`side_effect_class.mutates and not capability.reversible` at/above A3), producing
`HUMAN_APPROVAL_REQUIRED`, `ApprovalRequirement.HUMAN_APPROVAL`, forced to A3, and
*"no delegated autonomy"*. A4 is unreachable for this operation by construction.

What *is* honestly true and will be documented instead: the operation preserves
the **declared workload configuration** — image, command, env, replicas,
resources are untouched — and changes only a platform-owned annotation. That is a
narrower and true claim than "reversible".

---

## 3. FINDING 2 — `ProviderOperationSpec` cannot express a nested request body `[FACT]`

`plan()` builds the body as a **flat** dict: `body[spec.wire_name] = value`
(`provider_operation.py:742`). Every existing write is flat — GitHub's
`create_issue` is `{title, body, labels}`, Grafana's `create_folder` is
`{title, uid}`. Nothing has ever needed nesting.

Every Kubernetes mutation is nested. A restart patch is four levels deep.

Three ways to close it, and only one is safe:

| Option | Verdict |
|---|---|
| Let a caller supply a nested BODY parameter (e.g. a `spec` object) | **Rejected.** That is the arbitrary-patch hole the mission forbids — the model, or anything upstream, could then send any spec mutation under one approved capability. |
| Add a body *template* with path-substitution to the generic spec | **Rejected.** New generic machinery, and a path syntax is a small language; the next operation widens it. |
| **A fourth narrow provider port, `ProviderBodyBuilder`** | **Chosen.** |

The port mirrors the three that already exist (`ProviderResponseTranslator`,
`ProviderBodyNormalizer`, `ProviderBodyDecoder`): the provider's own dialect lives
in the provider's own module, and the generic adapter stays generic. It is pure,
receives only the spec and the **already-validated** payload plus the platform's
idempotency key, and **cannot** change the method, path, destination, headers or
credential — those still come from the catalog and the channel.

`[FACT]` **The annotation value will be the platform's own action identity, not a
clock.** `plan()` is documented as deterministic — *"Nothing here reads a clock, a
counter, an attempt number or a random source"* — so a timestamp would break that
invariant. Using the authority's idempotency key means the same authorized action
always produces the same request, which is what makes replay and duplicate
suppression meaningful, and it is strictly better than a timestamp for a governed
system.

---

## 4. FINDING 3 — there are currently **zero** Kubernetes write operations `[VERIFIED]`

Confirmed by enumerating the catalog rather than assuming:

```
kubernetes.deployment.get    GET  read      kubernetes.pod.get     GET read
kubernetes.deployments.list  GET  read      kubernetes.pod.logs    GET read
kubernetes.events.list       GET  read      kubernetes.pods.list   GET read
                                            kubernetes.pods.watch  GET read
```

Rollout restart does not exist. It will be the **first and only** Kubernetes
mutation, and the catalog will contain exactly one.

---

## 5. The scenario — and an honesty problem worth naming up front `[FACT]`

Phase 9.5's incident is a **deployment regression**: revision 2 carries a broken
command. **A rollout restart does not fix that** — new pods run the same broken
command and crashloop identically.

So if I reuse 9.5's incident, the prediction is falsified and the platform must
report NOT RECOVERED. That is a *genuinely valuable* demonstration and I will keep
it — but on its own it would leave "the governed write works" unproven against a
successful path.

So the environment stages **two** workloads:

| Workload | Incident | Restart is | Expected honest outcome |
|---|---|---|---|
| `config-consumer` | `envFrom` a ConfigMap whose value was fixed *after* the pods started. Env is injected at pod creation and never updated live, so running pods keep the broken value. | **the correct remediation** | prediction **SUPPORTED**, recovered |
| `payments-api` | 9.5's regression: revision 2 has a broken command | **not** a remediation | prediction **FALSIFIED**, honestly reported NOT RECOVERED |

The second is the more important result: it proves the platform reports what
reality did, not what it hoped.

---

## 6. Minimal implementation plan

1. **`ProviderBodyBuilder`** — the fourth narrow port on `ConnectorAdapter`
   (§3), defaulting to today's flat behaviour.
2. **`kubernetes.workload.rollout_restart`** in the Kubernetes catalog:
   `PATCH`, `IRREVERSIBLE_WRITE`, `NON_IDEMPOTENT_WRITE`, declared parameters
   `namespace` + `name` only, static strategic-merge-patch content type, a
   `KubernetesRestartBodyBuilder` in the same module, and a read-back
   verification procedure. Real exposure becomes 5 reads + **1** write.
3. **A `CapabilityProfile`** for it: `reversible=False`,
   `verification_requirement=INDEPENDENT_READBACK`, ceiling A3, resource scope
   `deployment`.
4. **`backend/api/remediation.py`** — the composition-layer lifecycle: pre-action
   assurance → approval artifact → autonomy decision → governed write → post-action
   observation → prediction evaluation → post-action assurance → explainable result.
   No new executor; it *calls* the existing ones.
5. **`scripts/phase96_provision.sh`** — 9.5's cluster plus the two workloads, and
   RBAC granting `patch deployments` on **one namespace** only.
6. **`scripts/phase96_reversible_remediation_harness.py`** — A–AE.
7. `tests/intelligence/test_governed_remediation.py`.
8. Docs: ADR-086, verification report, this map, memory addendum.

**No new fitness rule is expected.** `BND-INTELLIGENCE-CANNOT-EXECUTE`,
`BND-INTELLIGENCE-CANNOT-BYPASS-WORLD`, `BND-WORLD-CANNOT-EXECUTE`,
`BND-DIRECT-HTTP`, `BND-PROVIDER-SDK` and `BND-EFFECT-GATE` already make
Intelligence→Kubernetes-write impossible. §8 will re-check against the gate.

---

## 7. Stop-condition review

| # | Condition | Status |
|---|---|---|
| 1 | operation cannot be represented honestly as reversible/safe | **Partially triggered — resolved by telling the truth.** It is NOT reversible; classified `IRREVERSIBLE_WRITE`, which the existing policy already routes to human approval at A3. No invariant weakened. |
| 2–4 | second execution / governance / approval authority | Not triggered — all three exist and are reused |
| 5 | arbitrary Kubernetes API access | Not triggered — one declared path, two declared parameters, a body built by a declared builder |
| 6 | arbitrary shell | Not triggered |
| 7 | model output must become authorization | Not triggered — approval and autonomy are platform-owned |
| 8 | model output must become truth | Not triggered — outcome comes from a governed read-back |
| 9 | stale evidence must be accepted | Not triggered — gate 8 refuses |
| 10 | conflicted evidence as truth | Not triggered — gate 8 refuses |
| 11 | world state cannot be independently verified | Not triggered — `AssuranceVerifier` re-queries |
| 12 | provider outcome cannot be classified honestly | Not triggered — `ProviderDelivery.UNKNOWN` survives to the aggregate |
| 13 | duplicate writes cannot be prevented | See §8 — at-least-once is what the platform claims; the idempotency key is carried and the *intent* is single |
| 14 | tenant isolation unprovable | Not triggered |
| 15 | real Kubernetes unavailable | Not triggered — k3d works |
| 16 | credentials would need fabricating | Not triggered — a disposable SA token, Phase 5.5 untouched |
| 17 | an existing invariant must be weakened | **Not triggered** — §2 is the test of this, and the answer was to classify honestly rather than to bend the definition |

---

## 8. What I will NOT be able to claim, stated now

- `[BLOCKED]` **Exactly-once.** The platform claims at-least-once. A write whose
  outcome is `UNKNOWN` (delivered-but-unanswered) stays UNKNOWN; the harness will
  prove the *intent* is single and that no second write is issued on a known
  outcome, not that duplication is impossible.
- `[FACT]` **A successful restart does not prove the causal hypothesis.** The
  report will keep diagnosis support, prediction support, execution result and
  assurance as four separate axes, as the mission requires.
- `[BLOCKED]` **The model proposer remains scripted** (Phase 5.5). The model
  proposes nothing that matters here anyway: approval, autonomy and the write are
  all platform-owned.
- **Rollback is unavailable** and will be classified so. There is no inverse; a
  rollback capability would be a separate governed capability and is not built.

---

# Post-implementation: what discovery did not find

Discovery (above) was written before any production code changed, and it was
right about the extension points: the four narrow provider ports, the two typed
doors onto one `_perform()`, the blast radius living in the type, and the honest
`IRREVERSIBLE_WRITE` classification all landed as planned.

It missed one thing, and that one thing stopped the phase.

## The isolation invariant nobody had ever exercised

`IsolationTier` sufficiency (`_TIER_SUFFICIENCY`) is:

| Tier | Sufficient for |
|---|---|
| `AMBIENT` | `READ` |
| `CONTAINED` | `READ`, `REVERSIBLE_WRITE` |
| `SEALED` | everything, incl. `IRREVERSIBLE_WRITE` |

The Kubernetes connector is `CONTAINED` and runs **in-process**
(`capability_execution_composition.py:663`; ADR-059 states the gap openly). An
honestly-classified rollout restart therefore hits two independent refusals:

| | Where | What it does |
|---|---|---|
| Gate 1 | `contexts/connectivity/domain/contract.py:206` — `CapabilityContract.__post_init__` | refuses to **register** the capability: *"isolation tier 'contained' is insufficient for a 'irreversible_write' capability"* |
| Gate 2 | `contexts/execution/infrastructure/worker_directory.py:514` — `WorkerImplementation.permits_side_effect` | refuses to **select** the worker for that side effect |

Discovery missed this because **no irreversible-write capability has ever been
registered in this repository.** GitHub's connector declares some, but was never
commissioned — Phase 5.5's credential blocker stopped it. The invariant was
correct, load-bearing, and completely untested for the whole life of the project
until an honest classification finally reached it.

## Why the phase stopped rather than routed around it

Three ways forward existed:

1. Reclassify the restart as `REVERSIBLE_WRITE` — a lie about the operation, and
   forbidden by the brief.
2. Declare the in-process connector `SEALED` — asserting *"full virtualization,
   no ambient credentials"* about a worker running inside this process.
3. Stop and report BLOCKED.

We took 3. No tier was widened, no classification softened, no gate bypassed, no
autonomy policy weakened.

## What this changes about the plan

- Phase 9.6's Definition of Done is **NOT met** and moves unchanged to Phase 9.7.
- Phase 9.7 is now defined by this finding: build a real **SEALED execution
  tier** — an out-of-process, credential-brokered, virtualized worker — and only
  then perform the first irreversible write.
- Everything 9.6 built (operation spec, `ProviderBodyBuilder`, typed write door,
  remediation lifecycle, pre-action gate) ships unit-verified and is ready for
  9.7 to reach. It is unreachable in production until then, and that is correct.

See `docs/PHASE_9_6_VERIFICATION_REPORT.md` and ADR-086.
