# Phase 9.9C — Verification Report

**Phase:** Approval binding repair, and the first governed write
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-090
**Harness:** `scripts/phase99c_first_write_harness.py`
**Provisioner:** `scripts/phase99b_provision.sh` (reused unchanged)

---

## Definition of Done: **MET**

**78/78 checks. Exit 0. VERIFIED.**

CortexPrime performed its **first real irreversible write to a real external
system**: one governed `kubernetes.workload.rollout_restart` against a disposable
k3d Deployment, through approval → authorization → gateway → CONTAINED worker →
Kubernetes, with the outcome established by an independent read of the cluster
rather than by the worker's answer.

Milestones printed, each only when actually proven:

```
APPROVAL_VALIDATED
AUTHORIZATION_GRANTED
WORKER_STARTED
PROVIDER_WRITE_EXECUTED
WORLD_STATE_CHANGED
OUTCOME_ESTABLISHED
```

`ASSURANCE_SUPPORTED` was **not** printed. See §6.

---

## 1. The repair — [VERIFIED]

| | Check |
|---|---|
| A1 | The sealed binding carries the approval reference |
| A2 | The projection carries it into Execution |
| A3 | The gateway's re-authorization now supplies it |
| A4 | It is read from the sealed binding and from **nothing a caller supplies** |
| A5 | `ApprovalFacts` distinguishes the capability digest from the action digest |
| A6–A10 | The gateway still refuses an absent, invalid, expired, **unbound**, or **wrong-action** approval |

A4 checks the code with comments stripped. An earlier version matched the word
"payload" inside its own explanatory comment — exactly the kind of green a source
assertion must not be able to produce.

---

## 2. The security hole this phase found and closed — [VERIFIED]

The brief described one missing field. Tracing it found three defects, and the
third was live.

When a presented approval passed the policy's capability-level test,
authorization downgraded `REQUIRE_APPROVAL` to `ALLOW`. `facts_for` computed
`approval_required` from that downgraded effect, so the gateway's
`_check_approval` returned on its first line — **before the action-digest
comparison**. The gateway's strongest approval check was dead code whenever
authorization succeeded.

Measured on the real cluster, before the fix:

- an approval granted for `billing-api` **successfully restarted `payments-api`**
- an approval bound to **no action at all** succeeded
- **four real writes** occurred inside a negative matrix meant to prove zero

The first repair made the write possible; it also made this reachable. It was
found because a negative test that was expected to pass did not, and the run was
discarded rather than reported.

After the fix: all sixteen negatives refuse, zero provider writes.

---

## 3. The negative matrix — [VERIFIED], zero provider writes

| # | Negative | Result |
|---|---|---|
| B1 | missing approval | refused |
| B2 | unknown approval reference | refused |
| B3 | **revoked** approval | refused at dispatch |
| B4 | approval scoped to another tenant | refused |
| B5 | approval bound to another capability digest | refused |
| B6 | approval for another governance operation | refused |
| B7 | **approval granted for another workload** | refused |
| B8 | **unbound approval** | refused |
| B9 | an operation nobody declared | refused at the typed door |
| B10 | undeclared argument | refused |
| B11 | secret-bearing argument | refused |
| B12 | workload in another namespace | refused |
| B13 | wildcard target | refused |
| B14 | model-supplied approval reference | structurally impossible (A3/A4) |
| B15 | **zero provider writes across the whole matrix** | `0` |
| B16 | the cluster untouched after every refusal | no annotation |

Plus the 9.9B worker boundary and its seventeen binding refusals, re-proven in
this run rather than assumed.

---

## 4. The write — [VERIFIED]

```
before:  generation 1, resourceVersion 745, replicas 1, image busybox:1.36,
         annotation "", pod ede5eb72-…
after:   generation 2, annotation fbcf8f6c… (the action digest),
         pod 4bd0520d-…
provider writes: exactly 1, POST /execute, to kubernetes-contained
```

- [VERIFIED] The Deployment **identity is unchanged** — the same object was
  restarted, not replaced.
- [VERIFIED] The generation **advanced** — a real spec change, not a no-op.
- [VERIFIED] The annotation is CortexPrime's own key and carries the **action
  digest**, so the change is attributable to one authorized action.
- [VERIFIED] Replica count unchanged; image unchanged — a restart, not a deploy.
- [VERIFIED] The old pod was terminated and replaced; the replacement belongs to
  the intended Deployment.
- [VERIFIED] Exactly **one** provider write, and it went to the contained worker,
  not to the API server.

### Blast radius — [VERIFIED]

- [VERIFIED] The bystander Deployment in the same namespace is untouched.
- [VERIFIED] The same-named Deployment in the other namespace is untouched.

---

## 5. The outcome comes from reality — [VERIFIED]

The worker's answer establishes nothing. The outcome was established by:

1. a direct read of the cluster (section D), and
2. a **governed read** back through the platform, which reported the advanced
   revision (`revision: 2`, `replicas: 1`, `readyReplicas: 1`).

---

## 6. Audit, secrets, replay — and what is honestly not claimed

- [VERIFIED] No credential appears in any durable row of any table.
- [VERIFIED] No credential appears in the report.
- [VERIFIED] The approval reference is durably recorded in the **sealed binding**
  (`cp_binding.record`) and the **audit chain** (`cp_audit_record.document`).
  An earlier version of this check queried `cp_authorization`, which this
  composition never writes, and reported a missing reference that was in fact
  recorded in three places — a check that looks in one guessed table proves
  nothing.

### Not claimed

- [NOT CLAIMED] `ASSURANCE_SUPPORTED`. The governed read establishes the
  post-write state through the platform, but ingesting it as a restart
  Observation needs a declared predicate and freshness horizon this phase did not
  add. No Fact and no Assurance verdict is claimed for the restart.
- [DEFERRED] **Replay inertness of a completed execution.** The harness issued a
  *new* governed request rather than replaying a recorded one; that produced a
  second write and a second revision, which is correct — at-least-once is the
  contract and exactly-once is not claimed. The platform's replay path is
  unchanged by this phase and was proven inert in 9.3. Nothing new is claimed.
- [DEFERRED] Emergency stop, circuit breaker and the ten autonomy gates. All were
  verified against the real cluster in 9.6 and are unchanged by this repair; they
  were not re-run, so this phase claims nothing new about them.
- [DEFERRED] Fencing and crash semantics. Reused unchanged from 9.3/9.6; this
  phase changed no lease, leadership or recovery code.
- [NOT VERIFIED] Process-count limits and an egress firewall, as recorded in
  ADR-089 and unchanged here.

---

## 7. Results

| Check | Result |
|---|---|
| 9.9C harness | **78/78, exit 0, VERIFIED** |
| Regression (`contexts`, `intelligence`, `contracts`, `architecture`, `assurance`) | **2808 passed, 0 failed** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1183 modules |

One pre-existing test was superseded and updated:
`test_a_valid_approval_bound_to_this_exact_action_admits` bound its approval to
the *action* digest, which ADR-090 replaced with the approvable digest. The
property it protects is unchanged; only which digest changes.

Two regression guards were **added** for the hole in §2, both asserting the
refusal through the suite's shared `_refused` helper, which also proves no
provider call and no credential minted:

- `test_an_allowed_decision_still_has_its_approval_checked` — effect `ALLOW`,
  approval present, bound to a different action → refused.
- `test_an_unbound_approval_is_refused_even_when_allowed` → refused.

**No architecture fitness rule was added.** The candidate — a model-supplied
approval reference — is structurally impossible after this repair, because the
field is read from the sealed binding and there is no payload path to it. A rule
restating that would be cosmetic.

---

## 8. Honest summary

The phase's premise was that one field was missing. That was true, and repairing
it was necessary but not sufficient: it exposed a dead-code check that had been
silently un-runnable, and for one run the platform did the exact thing every
phase since 9.6 has been built to prevent — it performed an irreversible write
under an approval granted for something else.

That run was discarded, the hole was closed, and the environment rebuilt before
the write that counts. The approval that authorized the first real write was
bound to that exact action, and an approval for the workload next to it is now
refused.
