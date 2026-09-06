# Phase 10.7 — Implementation Map

**Written before implementation.** Discovery first, from the running code.

Labels: `[FACT]` read from this repository or a live probe, `[DECISION]`, `[GAP]`.

---

## 1. Discovery — the eighteen questions

| # | Question | Answer |
|---|---|---|
| 1 | Where is approval authority scoped? | `backend/auth/approver.py` — the grant string `approve:remediation` on `TenantUser.permissions`. **Tenant-wide** `[FACT]` |
| 2 | Where is execution authority scoped? | **Nowhere.** `execute_approval` checks only that the approval's outcome is `granted` `[FACT]` |
| 3 | Fields already on `cp_approval`? | tenant_id, capability_ref, capability_digest, operation, **environment**, principal_id, payload, approval_digest, outcome, requested_by, decided_by, expires_at, consumed_by_execution, investigation_ref `[FACT]` |
| 4 | Fields on capability definitions? | definition: capability_id, provider, reference(+version), digest, trust, status, tenancy. contract: **supported_environments**, side_effect_class, effect_semantics, code_trust, isolation_tier, required_permissions `[FACT]` |
| 5 | Capability scope without a new table? | **Yes** — `cp_approval.capability_ref` + `capability_digest` |
| 6 | Environment scope without a new table? | **Yes** — `cp_approval.environment`, cross-checkable against `contract.supported_environments`. Live probe: `(CapabilityEnvironment.DEVELOPMENT,)` `[FACT]` |
| 7 | Workload/namespace from the binding? | **Yes** — `cp_approval.payload` carries `{namespace, name}`, and the worker enforces its own namespace binding independently |
| 8 | Risk scope from existing classification? | **Yes** — `implied_risk_for(effect_semantics, side_effect_class)` (extracted in 10.4) and `RiskLevel`'s own ordering |
| 9 | Can autonomy scope be reused? | **As the vocabulary, yes** — see §2 |
| 10 | Scope as a projection rather than an authority? | **Yes** for the queue; the *decision* is still enforced server-side in the request path |
| 11 | Execution authorization reuse the gateway? | **Yes** — unchanged; the new check runs before it and adds nothing after |
| 12 | Any route executing on membership + approval alone? | **Yes — `POST /approvals/{id}/execute`.** That is the gap this phase closes `[FACT]` |
| 13 | Is the approval digest sufficient to bind the action? | **Yes** — ADR-090; payload, tenant, principal, capability and version are all inside it |
| 14 | Fields identifying the target? | `payload.namespace`, `payload.name` |
| 15 | Fields identifying the capability? | `capability_ref`, `capability_digest`, `operation` |
| 16 | Fields identifying the environment? | `cp_approval.environment` ↔ `contract.supported_environments` |
| 17 | Fields identifying the tenant? | `cp_approval.tenant_id`, and the verified session |
| 18 | Smallest meaningful scope? | **tenant + capability + environment (+ optional risk ceiling)** — every dimension already authoritative |

`[FACT]` **No new table is necessary.** Every scope dimension is already a column
on `cp_approval` or a field on the capability contract.

---

## 2. The scope vocabulary is borrowed, not invented `[DECISION]`

`[FACT]` `AutonomyScope` already exists and already says the thing this phase
needs: *"Autonomy is never universal: a grant is 'A4 is permitted for THIS
capability under THESE conditions', never 'the agent is A4'."* Its dimensions
are tenant, environment, service, capability_ref, operation, resource_class.

`[DECISION]` Approver and executor scope use the **same dimensions**, so the
platform has one idea of what "scope" means. `service` and `resource_class` are
**not** used: nothing populates them for a remediation approval today, and
naming a dimension the system cannot fill would be a label without authoritative
backing.

---

## 3. The grant grammar `[DECISION]`

`TenantUser.permissions` is a durable per-membership list of strings. It stays.

```
approve:remediation:capability=<ref>,environment=<env>[,max_risk=<level>]
execute:remediation:capability=<ref>,environment=<env>[,max_risk=<level>]
```

`[DECISION]` **No wildcards.** A grant names one capability explicitly; two
capabilities means two grants. The existing `PERMISSIONS` table already shows
what a wildcard does to an authority surface, and Phase 10.5 established that no
wildcard may confer approval.

`[DECISION]` **`capability` and `environment` are required.** A grant missing
either is not a narrower grant, it is an unscoped one.

`[DECISION]` **`max_risk` is optional** and compared using `RiskLevel`'s own
ordering against the risk the platform derives from the capability contract. The
caller never supplies a risk. Absent, the grant is limited by the named
capability's declared risk, which is already fixed.

### The bare grant stops working — deliberately

`[DECISION]` `approve:remediation` with no scope **no longer confers authority.**
"Tenant-wide authority remains when narrower scope exists" is a declared stop
condition, so the legacy form must fail closed rather than be grandfathered.

`[CONSEQUENCE]` **Operator action required:** grants issued under Phase 10.5 must
be re-issued with a capability and an environment. This is a breaking change to
the grant format and is recorded as one, not hidden. The harness proves a bare
grant is refused.

---

## 4. Execution authority — the gap Part C names `[DECISION]`

`[FACT]` Today any tenant member can execute any granted approval.

`[DECISION]` Execution requires `execute:remediation:…` scoped to the same
capability and environment as the approved action. It is a **third** grant,
distinct from approving.

`[DECISION]` **No new separation rule.** Phase 10.6's invariant is
`requester != approver` and nothing more. The requester may execute; the approver
may execute; a third party may execute — each only if they hold execution scope.
Imposing `requester != executor` would be inventing governance, which is exactly
what 10.5 and 10.6 refused to do.

---

## 5. Scope binds to the stored action, never to the request `[DECISION]`

Both checks read `cp_approval` and the capability contract. `[DECISION]` No
capability, environment, workload, namespace, risk, blast radius, autonomy, code
trust or isolation value is read from a request body, query, header or path —
the request models already set `extra="forbid"`, so an attempt is a 422 rather
than a silent ignore.

`[DECISION]` Scope evaluation **consumes** digests and never writes one. The
harness asserts `capability_digest`, `approval_digest` and `payload` are
byte-identical before and after every authorization decision, on the approve,
reject, allowed-execute and refused-execute paths.

---

## 6. What is added

### Backend

```
backend/auth/approver.py               (modified: parse and evaluate scoped grants; execution authority)
backend/api/product/approval_routes.py (modified: the execution check; scope on the decision)
backend/api/product/approval_queue.py  (modified: can_approve / can_execute projections)
backend/api/product/schemas.py         (modified)
```

`[DECISION]` **No new route, no new table, no migration, no new authority, no
new capability.** The product's non-GET routes stay exactly the three from
Phase 10.3.

### Frontend

```
frontend/components/investigator/ApprovalQueue.tsx (modified)
frontend/components/investigator/RemediationPanel.tsx (modified: execute control)
frontend/lib/investigator/types.ts                 (modified)
frontend/tests/investigator/queue.test.tsx         (modified)
```

`[DECISION]` The Execute control is rendered from a **server-projected**
`can_execute`. An approval existing is no longer sufficient to show it.

### Harness

```
scripts/phase107_scoped_authority_harness.py
```

---

## 7. Order of checks

**Decision** — authenticate → tenant → approver authority (live) → **scope for
this approval** → load → separation of duties → state → the existing approval
authority.

**Execution** — authenticate → tenant → load approval → approval is granted →
**executor authority + scope** → the existing `GovernedCapabilityWriter`.

`[DECISION]` Precedence continues to follow `CapabilityPolicy.evaluate`:
authorization before separation of duties before state.

---

## 8. Invariants this phase must not break

1. One approval authority, one execution authority, one governance authority.
2. `requester != approver` stays enforced and does **not** become
   `requester != executor`.
3. Scope comes from stored state; nothing about it is client-supplied.
4. No digest changes.
5. Revocation and expiration stay fail-closed; the bare grant fails closed too.
6. Provider writes stay at 0 for every negative case.
7. `rollout_restart` remains the only commissioned write.
8. At-least-once; exactly-once is not claimed.
