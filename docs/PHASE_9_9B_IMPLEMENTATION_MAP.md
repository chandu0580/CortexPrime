# Phase 9.9 Part B — Implementation Map (discovery output)

**Written before any production code changed.** Required by the phase brief.

Part A left `CONTAINED` with **zero occupants**. This phase must make it real:
one genuinely out-of-process worker, executing exactly one FIXED capability,
behind the existing execution authority.

---

## 0. Correction to the brief's recollection

The brief restates Part A as `FIXED < RESTRICTED < ARBITRARY` over three tiers.
What Part A actually shipped, and what this phase builds against:

- `CodeTrust`: `FIXED < PARAMETERIZED < THIRD_PARTY < OPERATOR_SCRIPT < ARBITRARY`
- `IsolationTier`: `AMBIENT < CONTAINED < SANDBOXED < SEALED`

There is no `RESTRICTED` class. The result the brief turns on is unchanged and
verified in code: `minimum_isolation(FIXED, IRREVERSIBLE_WRITE) == CONTAINED`,
and `ARBITRARY` requires `SEALED` for every effect class.

`AMBIENT` matters here: it is the tier the in-process connectors now honestly
declare, and it is *why* they cannot perform this write.

---

## 1. What already exists and will be reused unchanged

Nothing in the forbidden list needs building. Every one of these is present,
complete, and load-bearing today.

| Concern | Reused component | Why it is not rebuilt |
|---|---|---|
| Execution authority | `InvocationGateway.invoke` → `WorkerRuntime.invoke` | *"Admit, invoke exactly once, check the result, record it. No loop, no retry, no fallback."* |
| **The worker seam** | `WorkerRuntime.invoke` → `adapter.run(context, request, authority=...)` | The single attachment point. A new worker is a new **adapter + registration**, never a new executor. |
| Adapter gate | `AdapterSeam.run` (fixed) + `_perform` (subclass hook) | Subclasses *may not* override `run`; the ambiguity rule is identical everywhere. `_perform` returns a `ProviderOutcome`; Execution decides what it means. |
| Authority threading | `CONSUMES_PROVIDER_AUTHORITY` marker; `ProviderAuthority` from the gateway | An adapter reached without the gateway gets a refusal, because the object it needs can only be produced there. |
| Transport | `TransportBroker` + `ProviderChannel.send` | Fenced by `BND-DIRECT-HTTP`. The worker is reached through this, not a new client. |
| Credential authority | `CredentialBroker` + `ScopedCredentialProvider` | Fail-closed, verifies *after* the provider answers, refuses credentials broader than the requesting authority, zero adapters by default. |
| Authority re-check at mint | `GatewayAuthorityRevalidator` | Re-reads the binding through the same Connectivity service. |
| Isolation gates | Gate 1 `CapabilityContract`, Gate 2 `WorkerImplementation.permits` → `worker_selection.py` → `ISOLATION_INSUFFICIENT` | Part A. Consult `minimum_isolation`. |
| Fencing | `WorkerRuntime.invoke(held_by=...)`, `ExecutionLease`, `SqlLeadershipStore.heartbeat` | Reused as in 9.3. **No new election mechanism.** |
| Approval / autonomy | Five voiding clauses; ten autonomy gates | All exercised in 9.6 against the real cluster. |
| Audit / World / Assurance | Hash-chained audit; `cw_observation`/`cw_fact`/…; independent assurance | Phase 7. Untouched. |
| The operation itself | `kubernetes.workload.rollout_restart` + `KubernetesRestartBodyBuilder` | Phase 9.6. **Not reclassified.** |

### The one thing that does not exist

**Any out-of-process worker.** `CONTAINED` and `SANDBOXED` have no occupants.
That is the whole of Part B's scope.

---

## 2. The blocking constraint that shapes the design

`BND-PROCESS-SPAWN` (`boundary_rules.py:530`) confines process creation to four
named legacy modules and states a fifth "is an ERROR, not a review comment."
Verified in Phase 9.7: exactly 4 entries, severity `ERROR`, 0 violations across
1181 modules.

Three ways to obtain a worker process, and only one survives:

| # | Approach | Verdict |
|---|---|---|
| a | The platform spawns the worker | **Rejected.** Needs a fifth allowlist entry — weakening an existing invariant. |
| b | The platform creates a Pod/Job for it | **Rejected.** Creating a Pod is itself an irreversible write, so a CONTAINED worker would require a CONTAINED worker (the ADR-087 regress). And `create pods` permits mounting any Secret and assuming any ServiceAccount in the namespace — strictly more authority than `patch deployments`. |
| c | **The operator pre-provisions it** | **Chosen.** The worker is deployment infrastructure, like PostgreSQL. The platform never creates it, only dispatches to it. No spawn, no regress, no privilege inversion. |

The provisioning script is a shell script outside `backend/`, so it is not in
the module graph the rule walks. That is not a loophole: the point is precisely
that the *platform* still cannot spawn, which is what makes (c) different from (a).

---

## 3. Planned design

### 3.1 The worker

A Kubernetes `Deployment` + `Service` inside the disposable cluster, built from
a local image and imported with `k3d image import`.

- **Python standard library only.** No pip, no third-party package, no
  `kubernetes` client. This is what makes `CodeTrust.FIXED` defensible rather
  than merely declared: there is no dependency that could contain behaviour
  nobody declared.
- One HTTP endpoint accepting a **typed execution envelope**.
- Its only outbound call is a `PATCH` to
  `/apis/apps/v1/namespaces/{ns}/deployments/{name}` on the in-cluster API
  server, addressed from `KUBERNETES_SERVICE_HOST` — deployment configuration,
  never anything in the envelope.
- It accepts no source, no path, no URL, no module name, no provider name, no
  operation other than the one compiled into it.

### 3.2 The platform side

A new `ContainedWorkerAdapter(AdapterSeam)` implementing `_perform` only:

1. Build the typed envelope from `WorkerExecutionRequest` + `ProviderAuthority`.
2. Dial the worker through the existing `ProviderChannel`/`TransportBroker`.
3. Return a `ProviderOutcome`. It decides nothing.

Registered as a `WorkerImplementation` with `isolation=IsolationTier.CONTAINED`
— **true because it is out-of-process**, not because it is convenient. That
declaration is the claim this whole phase has to earn.

### 3.3 Credentials

The credential is **brokered per execution** and travels in the envelope; the
worker holds no standing credential for the action and never persists it.

The provisioner mints a short-lived token with `kubectl create token` (a real
`TokenRequest`) bound to a ServiceAccount whose RBAC is namespace-scoped and
limited to `patch`/`get` on `deployments`. Honest limits to be reported:

- The platform does not itself call `TokenRequest`; doing so needs
  `create serviceaccounts/token`, which is a larger grant than the action.
- Whether the worker's environment can be proven free of *other* credentials is
  a runtime check, and will be reported as measured — not asserted.

### 3.4 Envelope binding

Verified by the worker at every request against values compiled into its image:
`tenant`, `execution_id`, `capability_id`, `capability_version`, `provider`,
`operation`, `implementation_digest`, and a strict argument schema. Any
mismatch, and any unexpected field, is refused before the credential is touched.

---

## 4. What this phase must prove, and what it may not claim

**Claimable if measured:** a real process boundary (separate container, separate
PID namespace, its own filesystem); non-root; dropped capabilities;
`allowPrivilegeEscalation=false`; `RuntimeDefault` seccomp; read-only root
filesystem; memory/CPU limits; no Docker socket; no host mount; platform-
controlled destination; capability/tenant/version binding; fencing; replay
inertness; audit completeness.

**Never claimable here:** VM isolation, separate kernel, gVisor, Kata. Phase 9.7
established by execution that this host offers only `runc` on one shared WSL2
kernel, with no `/dev/kvm`. A container boundary is `CONTAINED`. It is **not**
`SANDBOXED` unless every hardening control is measured, and it is **never**
`SEALED`.

**Expected to be reported `NOT VERIFIED`:** any egress firewall claim beyond
what k3s actually enforces, and process-count limits if the runtime does not
expose them. These will be marked, not weakened.

---

## 5. Stop rule for this phase

The first real write happens only after every boundary and safety check passes.
If credential isolation, tenant isolation, capability binding, destination
control, the process boundary, fencing, replay inertness or audit completeness
cannot be proven, the phase **stops before the write** and reports which
property failed — as 9.6 and 9.7 did.

Nothing is compensated for by weakening governance, reclassifying the operation,
declaring `CONTAINED` without implementing it, or bypassing the gateway.

---

## 6. Deliverables

- `scripts/phase99b_provision.sh` — disposable k3d cluster, namespace, target
  Deployment, worker SA + minimal RBAC, worker image build/import/deploy.
- The worker source and its image definition.
- `ContainedWorkerAdapter` + registration + credential wiring.
- `scripts/phase99b_contained_worker_harness.py`.
- `docs/adr/ADR-089-*.md`, `docs/PHASE_9_9B_VERIFICATION_REPORT.md`.

**No new architecture fitness rule is planned.** By this project's standard a
rule is justified only where an invariant is otherwise unenforced; the candidates
named in the brief are already enforced by Gate 1, Gate 2, `BND-DIRECT-HTTP`,
`BND-PROCESS-SPAWN` and the `ProviderAuthority` requirement. A rule will be added
only if implementation reveals a genuine gap, with `CURRENT = PASS` and
`SYNTHETIC = FAIL` demonstrated.

---

# Post-implementation

The design above held. The worker is operator-provisioned (contradiction 2 and 3
escaped as predicted — `BND-PROCESS-SPAWN` still passes at four modules), stdlib
only, HTTPS, credential in the transport header rather than the envelope.

**What discovery did not find**, both found by running the real chain:

1. **Part A's `code_trust` threading stopped short of the binding.** It reached
   the contract, both gates and `BoundCapability`, but not `CandidateSnapshot`,
   `CapabilityBinding` or `project_binding`. The first real execution to resolve
   a binding raised `TypeError`. Now threaded end to end, fail-closed at the
   projection.

2. **An approval-requiring capability cannot be dispatched at all.** The
   gateway's re-authorization request carries no `approval_artifact_id`, so
   `approval_valid` can never be true and `REQUIRE_APPROVAL` always refuses. This
   is the blocking finding; see ADR-089 and the verification report. The fix is
   identified, additive and fail-closed, and was **not applied** because it
   changes how approvals bind to executions.

**Result:** the boundary is verified (61/62 checks), and the write did not
happen — `provider_writes = 0`. Phase 9.9B's Definition of Done is NOT met.
