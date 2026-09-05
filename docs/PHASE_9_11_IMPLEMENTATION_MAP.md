# Phase 9.11 — Implementation Map (discovery output)

**Written before production modifications.** Required by Part A.

This is the Phase 9 closure gate. It commissions no capability (Part B) and
connects no production infrastructure (Part N).

---

## 1. The Phase 9 capability matrix, source-cited

Every **write-capable** operation declared anywhere in the platform, enumerated
from the catalogs themselves rather than from documentation:

| Capability | Provider | Operation | SideEffect | CodeTrust | Isolation | Approval | Assurance | Autonomy ceiling | Credential path | World observation | Reversible | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rollout restart | `kubernetes-contained` | `kubernetes.workload.rollout_restart` | `IRREVERSIBLE_WRITE` | `FIXED` | `CONTAINED` (real, out-of-process) | Required, action-bound (ADR-090) | SUPPORTED via `deployed_revision` | A3 (never A4) | Broker → `DevelopmentCredentialProvider` → transport header | Governed read → Observation → Fact | **No** | **VERIFIED** |
| Create issue | `github` | `repository.create_issue` | `IRREVERSIBLE_WRITE` | — | — | — | — | — | none | none | No | **NOT COMMISSIONED** |
| Create issue comment | `github` | `repository.create_issue_comment` | `IRREVERSIBLE_WRITE` | — | — | — | — | — | none | none | No | **NOT COMMISSIONED** |
| Create folder | `grafana` | `folder.create_folder` | `REVERSIBLE_WRITE` | — | — | — | — | — | none | none | Yes | **NOT COMMISSIONED** |

**Four declared writes. One commissioned.** The other three have no credential
adapter, no worker and have never executed; Phase 5.5's credential blocker is
untouched. That is the expected conclusion, not a gap.

Read-side capabilities (`kubernetes.pods.list`, `.pod.get`, `.deployment.get`,
`.pods.watch`, Prometheus) remain `READ` / `AMBIENT` / in-process, unchanged.

---

## 2. What 9.10 left open, and what this phase can actually close

| 9.10 item | Finding | Action |
|---|---|---|
| Process-count limit (NOT VERIFIED, ADR-089) | The kubelet's `pod-max-pids` sets the **pod** cgroup's `pids.max`; the pids controller is delegated in the k3d node | **Enforce and probe** |
| Egress restriction (NOT VERIFIED, ADR-089) | k3s embeds kube-router and genuinely enforces NetworkPolicy — proven by probe before any policy was written | **Enforce and probe** |
| `executions.history` cannot name the execution | Purely observability: the outbox is keyed by execution id and tenant-scoped, the audit chain has it, and replay executes nothing | **Smallest additive fix** |
| Live two-holder fencing race | `SqlLeadershipStore` + `fenced_where` already exist; 9.10 only re-proved the wiring | **Run the real race** |
| Four post-write crash boundaries | They sit *after* the irreversible act | **Prove the property they protect; state the limit** |
| Replay of UNKNOWN / INTERRUPTED / FAILED_VERIFICATION | Needs executions durably recorded in those states | **Prove what exists; decline to manufacture the rest** |
| Exactly-once | Never claimed | **Never claim** |

---

## 3. The egress trap, found by probing

An `ipBlock` naming the API server's **ClusterIP** (`10.43.0.1`) **blocks the API
server**. kube-proxy DNATs the ClusterIP and NetworkPolicy is evaluated on the
post-DNAT destination, so the rule must name the real endpoint (the node IP at
`:6443`).

This exact mistake was made, caught by probing on a disposable pod, and corrected
**before** any policy touched the worker — which is the failure mode Part F
explicitly warns about.

---

## 4. Planned changes (all additive)

1. `scripts/phase99b_provision.sh` — `--kubelet-arg=pod-max-pids=128` and a
   worker egress NetworkPolicy (API endpoint + DNS only).
2. `ExecutionReplayer.replay(events, *, execution_id=None)` — an identity
   **hint**, used only when the events do not name one. An id the events carry
   always wins, so a caller cannot relabel another run's history.
3. `ExecutionService.replay` passes the id it already has.
4. `scripts/phase911_final_gate_harness.py`.

No new capability, provider, executor, gateway, approval system, credential
broker, lease or election. **No new fitness rule** unless discovery finds a real
bypass (Part L); the gate currently passes with zero blocking violations.

---

## 5. Stop rule

Any of the brief's stop conditions ends the phase. Of particular note for Part I:
if any V1 bypass can execute externally, the phase stops and Phase 10 is not
recommended.
