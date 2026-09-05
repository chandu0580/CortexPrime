# ADR-092 — Phase 9 final hardening gate

**Status:** Accepted
**Date:** 2026-09-05
**Extends:** ADR-088 (trust model), ADR-089 (CONTAINED worker), ADR-090 (approval binds to the action), ADR-091 (first-write lifecycle)
**Implementation map:** `docs/PHASE_9_11_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_9_11_VERIFICATION_REPORT.md`

## Context

Phase 9 ends with one commissioned write capability proven end to end. This ADR
records what was hardened at the close, what remains honestly unproven, and why
Phase 10 may begin.

## Decision 1 — Both ADR-089 "NOT VERIFIED" limits are now enforced

ADR-089 honestly reported process-count and egress restrictions as unenforced.
Both turned out to be enforceable by the existing topology, and both are now
proven by **runtime probe rather than by reading a manifest**:

- **Process count.** The kubelet's `pod-max-pids=128` sets each pod cgroup's
  `pids.max`. Verified against the pod cgroup on the node: 9/9 pods at 128. The
  *container's* cgroup still reads `max`, and that is not a gap — a pod-level cap
  is what the flag means, and reading the wrong file is how this would have been
  mis-reported in either direction.
- **Egress.** k3s embeds kube-router and genuinely enforces NetworkPolicy. The
  worker now has an allow-list of exactly two destinations: the API server
  endpoint and DNS.

Enforcement is proven on a **disposable probe pod**, never by taking the worker
offline: a deny-all pod loses the API server, and a pod under the worker's exact
policy shape keeps the API server while losing the internet and unrelated cluster
services.

## Decision 2 — The egress trap, recorded because it nearly shipped

An `ipBlock` naming the API server's **ClusterIP** blocks the API server.
kube-proxy DNATs the ClusterIP and NetworkPolicy is evaluated on the post-DNAT
destination, so the rule must name the real endpoint (node IP `:6443`).

That exact policy was written, probed on a disposable pod, found to block the API
server, and corrected **before it touched the worker** — which is the failure Part
F warns about. It is recorded here because the correct-looking version is the
obvious one to write.

## Decision 3 — `execution_id` was an observability defect, fixed additively

`ExecutionReplayer.replay` now accepts an optional `execution_id` **hint**, used
only when the recorded events do not name one. An id the events carry always
wins, so a caller cannot relabel another run's history as its own.

It was observability, not safety: the outbox is keyed by execution id and
tenant-scoped, the audit chain carries it, and the replayer executes nothing
regardless. The fold is untouched.

## Decision 4 — Fencing proven with two real instances

The earlier attempt acquired twice from **one** store and reported a failure that
was the store behaving correctly — an instance re-acquiring its own role is a
renewal, not a second holder. *"An anonymous leader cannot be told apart from its
own restart."*

With two distinct instances: A takes token 1; B is refused while A is live
(`None`, the ordinary follower answer, not an exception); A goes stale; B takes
token 2; and **A's token, carried into a leader-only `UPDATE`, matches zero rows**
while B's matches one.

That last measurement is the fence. The code is explicit that `assert_current` is
advisory and that `fenced_where` — composed into the write itself — is the real
mechanism, so both were exercised and the report says which is which. No
`LeadershipRole` was added: that enum is a closed list whose docstring warns that
a role added by habit is a bottleneck. The probe uses the existing role under its
own scope.

## Decision 5 — No new capability, no new fitness rule

Part B forbids commissioning another write and nothing here needed one. Part L
forbids cosmetic rules; the gate passes with **zero blocking violations** and
discovery found no bypass, so none was added.

## Decision 6 — The V1 surface remains contained

Probed by **calling** the surfaces, not by reading the module graph: legacy
execution is disabled, there are no ungated surfaces, the legacy execution guard
refuses, the V1 `ScriptSandbox` refuses to execute Python, and the V1 credential
store refuses to construct. `BND-PROCESS-SPAWN`, `BND-DIRECT-HTTP`,
`BND-PROVIDER-SDK`, `BND-AMBIENT-CREDENTIALS` and `BND-EFFECT-GATE` all pass.

## Consequences

Phase 9 closes with:

- **one** commissioned write capability, proven end to end and hardened;
- three further declared writes that are **NOT COMMISSIONED** and have never
  executed;
- one execution authority, one gateway, one approval system, one credential
  broker, one audit chain, one World Plane, one Assurance Plane.

### Never claimed

**Exactly-once.** At-least-once remains the contract. A new governed request for
the same action is a new execution and writes again, correctly; only replay of a
*recorded* execution is inert.

### Still NOT VERIFIED at the close of Phase 9

- Four post-write crash boundaries (observation / outcome / verification / audit
  persistence). They sit after the irreversible act and test record durability,
  not write safety.
- Replay of `INTERRUPTED` and `FAILED_VERIFICATION` executions — each needs a
  ledger in that state, and this phase declined to manufacture one by corrupting
  it. Inertness is structural and state-independent regardless.
- Production capability, and a real LLM (Phase 5.5 credential blocker, untouched).
