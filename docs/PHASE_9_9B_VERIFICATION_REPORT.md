# Phase 9.9 Part B — Verification Report

**Phase:** A real CONTAINED worker
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-089
**Harness:** `scripts/phase99b_contained_worker_harness.py`
**Provisioner:** `scripts/phase99b_provision.sh`

---

## Definition of Done: **NOT MET**

`CONTAINED` now has a real occupant and 61 of 62 checks pass against real
infrastructure. **The first real irreversible Kubernetes write did not happen.**

```
provider_writes            = 0
provider_dials_total       = 0
restart annotation on the target Deployment = <none>
target Deployment generation = 1 (unchanged)
```

The single failing check is the write itself, and it failed for a reason that is
neither the boundary nor the isolation model: **the gateway cannot dispatch any
capability whose policy requires approval**, because the approval reference never
reaches its re-authorization. See §5.

---

## 1. Environment (real, disposable)

| Component | What it actually was |
|---|---|
| Kubernetes | Real k3d cluster `cortex-p99b`, real TLS |
| Worker | A real Pod, built from `workers/contained_k8s_restart`, imported into the cluster, serving HTTPS |
| Identities | Two ServiceAccounts: `cortex-restarter` (patch+get deployments, one namespace) and `cortex-reader` (read-only) |
| Credentials | Short-lived tokens minted by real `TokenRequest` (`kubectl create token --duration=2h`) |
| Database | Real PostgreSQL, fresh, real migrations |
| Workloads | `payments-api` (target), `billing-api` (bystander), and a same-named deployment in a second namespace |

---

## 2. The boundary is real — [VERIFIED], measured from inside the container

| | Check | Result |
|---|---|---|
| A1 | Runs as a non-root user | uid **65532** |
| A2 | PID 1 in its own PID namespace — a separate process, not a thread of the platform | **pid=1** |
| A3 | Root filesystem is read-only | **yes** |
| A5 | No Docker socket exposed | **absent** |
| A6 | No CortexPrime repository mounted | **absent** |
| A7 | No developer kubeconfig | **absent** |
| A8 | **No credential-bearing variable in its environment at all** | **none** |
| A9 | The only `CORTEX_*` variables are bindings, not secrets | 8 binding vars |
| A10 | It has its own kubelet-mounted ServiceAccount token | present |

Runtime-enforced hardening, read back from the live Pod spec: [VERIFIED]
`allowPrivilegeEscalation=false`, all Linux capabilities dropped,
`readOnlyRootFilesystem=true`, `runAsNonRoot=true`, `RuntimeDefault` seccomp,
memory limit **96Mi**, CPU limit **250m**.

### Honestly not claimed

- [NOT VERIFIED] **Process-count limit.** The worker reports
  `rlimit_nproc = [-1, -1]`. Kubernetes exposes this only via the kubelet's
  `podPidsLimit`, which k3d does not set. No cap is claimed.
- [NOT VERIFIED] **Egress firewall.** No NetworkPolicy is applied, so outbound
  destinations are not restricted at the network layer. What *is* proven is that
  the worker's Kubernetes destination comes from its own environment and cannot
  be supplied by a caller.
- This is `CONTAINED`. It shares the host kernel (ADR-087), so it is **not**
  `SANDBOXED` and never `SEALED`.

---

## 3. The worker is bound, not general — [VERIFIED], every refusal executed

Each of these was posted to the live worker and refused with the named reason
code — none is a source-text assertion:

| Attack | Refused with |
|---|---|
| A different operation (`kubernetes.pod.delete`) | `operation_mismatch` |
| A different provider (`arbitrary-provider`) | `provider_mismatch` |
| A different tenant | `tenant_mismatch` |
| A different capability id | `capability_id_mismatch` |
| A changed capability version | `capability_version_mismatch` |
| A changed implementation digest | `implementation_digest_mismatch` |
| An extra envelope field (`url`) | `envelope_unknown_fields` |
| **A credential smuggled into the envelope body** | `envelope_unknown_fields` |
| An extra argument (`path`) | `arguments_unknown_fields` |
| A workload outside the bound namespace | `namespace_out_of_scope` |
| A wildcard target `*` | `name_not_a_single_target` |
| A comma-separated list `a,b` | `name_not_a_single_target` |
| A path traversal `../../secrets` | `name_not_a_single_target` |
| Missing idempotency key | `idempotency_key_missing` |
| Missing approval reference | `approval_ref_missing` |
| Missing authorization reference | `authorization_ref_missing` |
| No credential | `credential_missing` |

- [VERIFIED] Every refusal reports `provider_called = False`.
- [VERIFIED] **Binding is checked before the credential**: a wrong-tenant
  envelope sent with *no* credential refuses on `tenant_mismatch`, not on the
  missing credential.
- [VERIFIED] There is no `/exec`, `/shell`, `/eval` or `/proxy` endpoint.

---

## 4. Least privilege — [VERIFIED] against the live API server

`kubectl auth can-i` as `system:serviceaccount:cortex-p99b:cortex-restarter`:

| Verb / resource | Namespace | Answer |
|---|---|---|
| `patch deployments` | `cortex-p99b` | **yes** |
| `get deployments` | `cortex-p99b` | **yes** |
| `delete deployments` | `cortex-p99b` | no |
| `create pods` | `cortex-p99b` | no |
| `get secrets` | `cortex-p99b` | no |
| `create pods/exec` | `cortex-p99b` | no |
| `patch deployments` | `cortex-p99b-other` | no |
| `patch deployments` | `kube-system` | no |

No wildcard verb, no wildcard resource, no ClusterRole for the writing identity.

---

## 5. The blocking finding — [BLOCKED]

**An approval-requiring capability cannot be dispatched.**

The gateway re-authorizes at dispatch, which is correct — an approval can be
revoked between authorization and dispatch. But the `AuthorizationRequest` that
`facts_for` builds carries **no `approval_artifact_id`**
(`backend/api/capability_execution_composition.py`). So the `ApprovalLookup` is
never given anything to look up, `approval_valid` can never become true, and the
policy's `REQUIRE_APPROVAL` always refuses.

Observed, not inferred:

```
dispatch result: dispatched=False  invocation_refusal=approval_required
```

Proven three ways (harness section Z):
- [VERIFIED] The re-authorization request contains no `approval_artifact_id`.
- [VERIFIED] `AuthorityFacts` *does* have the field and the gateway *does* check
  it — the value is simply never fed on this path.
- [VERIFIED] `InvocationRequest` has no approval field either, so nothing on the
  dispatch path could carry it today.

**Never hit before:** 9.6 was blocked by isolation before dispatch, and every
earlier phase was read-only. No approval-requiring capability has ever reached a
real gateway here.

**Identified fix, deliberately not applied:** carry the approval reference on the
sealed binding — exactly as `code_trust` now is — and pass it into `facts_for`'s
`AuthorizationRequest`. Additive and fail-closed. Not applied because it changes
how approvals bind to executions, which is governance surface this phase was told
not to alter unilaterally.

### What this means for the write

- [VERIFIED] `provider_writes = 0` and `provider_dials_total = 0`.
- [VERIFIED] Without a valid approval the chain refuses and the cluster is
  untouched.
- [VERIFIED] The target Deployment carries no CortexPrime restart annotation and
  its generation is unchanged at 1.
- [BLOCKED] The real Kubernetes write, the post-write readback, prediction
  evaluation, and the resulting World observation.

---

## 6. Defects this phase found in Part A

Both were found by running the real chain; neither was caught by a unit test.

1. **`code_trust` threading was incomplete.** Part A added it to the contract,
   both gates and `BoundCapability`, but not to `CandidateSnapshot`,
   `CapabilityBinding` or `project_binding`. The first real execution to resolve
   a binding raised `TypeError`. Now threaded end to end and fail-closed at the
   projection.
2. **The adapter declared the wrong worker kind.** `WorkerKind.KUBERNETES` while
   the runtime's resolver answers `"connector"` for every governed capability, so
   selection never matched it. Corrected to `CONNECTOR`; Kubernetes-ness lives in
   `supported_providers` and `supported_operations`, where selection reads it.

---

## 7. Secrets — [VERIFIED]

- [VERIFIED] No credential appears in any durable row of any table (every text,
  varchar, json and jsonb column of every public table was scanned for both
  tokens).
- [VERIFIED] No credential appears in this report or the harness report.
- [VERIFIED] The envelope has no `credential` field, and one supplied is refused.
- [VERIFIED] Exactly one `reveal()` call site still exists in the backend; this
  phase added none.

---

## 8. Not covered

Deferred honestly, because the write never happened and most of these are
properties *of* the write:

- [DEFERRED] Crash semantics across the eleven named points, replay inertness of
  a completed irreversible execution, duplicate-action prevention, fencing of a
  contained worker mid-execution, and the resulting World observation and
  Assurance verdict. Each needs a completed write to be meaningful.
- [DEFERRED] Autonomy-gate coverage through this path — all ten gates were
  verified in 9.6 and are unchanged, but they were not re-run here.
- [NOT VERIFIED] Process-count and egress limits, as recorded in §2.

**No architecture fitness rule was added.** The candidates named in the brief are
already enforced: ambient credentials by the worker's measured environment,
arbitrary dispatch by the compiled binding and the unknown-field rule, capability
binding by both gates, and gateway bypass by the `ProviderAuthority` requirement
plus `BND-DIRECT-HTTP`. A rule restating them would be cosmetic.

---

## 9. Honest summary

The boundary is real and does what `CONTAINED` says: a separate process, in a
separate container, holding no CortexPrime secret, able to perform exactly one
operation on exactly one namespace, refusing everything else — and all of that is
measured rather than declared.

The write still has not happened. The obstacle has moved three times now —
hardware, then taxonomy, now a single unfed field on one authorization request —
and every one of those moves was found by running the real chain against real
infrastructure rather than by reasoning about it. The current obstacle is the
smallest and most ordinary of the three, and the fix is identified and additive.

It is also governance surface, so it is the owner's call rather than mine.
