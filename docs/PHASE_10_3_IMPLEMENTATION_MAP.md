# Phase 10.3 — Implementation Map

**Written before implementation.** Records what the audit found, what will be
reused, and the smallest integration that lets a human approve and initiate a
governed remediation without the product becoming a second authority.

Labels: `[FACT]` read from this repository or a live probe, `[DECISION]`, `[GAP]`.

---

## 1. Audit — what already exists and is reused unchanged

| Concern | Where it lives | Reused how |
|---|---|---|
| Execution entry | `GovernedCapabilityWriter.write(context, operation=, payload=, approval_artifact_id=)` — `backend/api/capability_execution_composition.py:1622` `[FACT]` | **The product calls exactly this.** It is a subclass of the read door precisely so there is one chain |
| Approval semantics | `ApprovalFacts.is_valid_for` — checks outcome, expiry, tenant scope, operation and capability digest `[FACT]` | Untouched. Still the decider |
| Action binding | `canonical_approval_digest(capability_ref, capability_digest, operation, tenant_id, principal_id, environment, payload)` — ADR-090, `domain/invocation.py:452` `[FACT]` | Computed **server-side only** |
| Gateway re-check | `SecureCapabilityInvocationGateway._check_approval` — refuses absent / invalid / expired / **unbound** / digest-mismatched approvals `[FACT]` | Untouched |
| Authorization seam | `build_authorization(registry, approvals=...)` — a declared parameter; `None` means every approval lookup fails closed `[FACT]` | The durable lookup is passed **here**, not patched in |
| Autonomy | `AutonomyPolicy.evaluate` — `backend/intelligence/application/autonomy.py:71` `[FACT]` | Displayed only. No product write path to it |
| Assurance | `SqlVerificationRepository` + Phase 9.10 verifier `[FACT]` | Displayed only |
| Revocation | `token_blacklist` over `backend/infrastructure/redis/connection.py`, `REVOCATION_FAIL_OPEN` `[FACT]` | The existing mechanism, given real Redis |
| Audit | `audit_chain_table` / `audit_record_table` `[FACT]` | Read for the chain assertion |
| Tenant identity | `product_context` from the verified JWT (Phase 10.1/10.2) `[FACT]` | Unchanged |

---

## 2. The blocking gap

`[GAP]` **There is no durable approval store. There never has been.**

- `ApprovalLookup` is a **port** `[FACT]`. The only implementations in the
  repository are `NoApprovals` (fail-closed) and `_Approvals`, an **in-memory
  dict defined inside the Phase 9.9B harness** `[FACT]`.
- `DURABLE_TABLES` contains no approval table `[FACT]`.
- Phase 9.9C had to reach into a private field —
  `approvals._facts[artifact_id] = dataclasses.replace(..., bound_action_digest=...)`
  `[FACT]` — because `grant()` had no way to bind an action digest at all.

So the first governed write was authorized by an approval that existed only in
one Python process's memory, granted through a private attribute. That is fine
for a harness and impossible for a product: the browser approves in the API
process, and the execution must read that approval back — across requests, and
after a restart.

`[DECISION]` **Implement the existing port durably.** A new table, a repository
that returns `ApprovalFacts`, and a service that grants and revokes. This is
**storage plus a request/decide workflow for the existing contract** — the
decision about whether an approval covers an action stays in
`ApprovalFacts.is_valid_for` and the gateway, both untouched. `grant` gains
`bound_action_digest` as a **first-class argument** so nothing has to reach into
a private field again.

`[DECISION]` It is wired through `build_authorization(approvals=...)` — the
declared seam — not by assigning `runtime.authorization._approvals`.

---

## 3. The other structural change: the product API stops being read-only

Phases 10.1 and 10.2 asserted `methods == {"GET"}`. Phase 10.3 is explicitly a
phase that adds an approval and an execution trigger, so that assertion must
change. `[DECISION]` It becomes an **exact allow-list**: the set of non-GET
routes must equal a named, enumerated set. A route that appears without being
named in that list fails the harness. Nothing is loosened to "some POSTs exist".

### The three POST routes, and what they will and will not accept

| Route | Body | Backend reconstructs |
|---|---|---|
| `POST /api/v1/investigations/{ref}/remediation/approval-request` | `{proposal_id, justification}` | tenant, capability, operation, payload, environment, principal, both digests, risk, autonomy — **everything security-critical** |
| `POST /api/v1/approvals/{approval_id}/decision` | `{decision, justification}` | approver identity from the session; digests already stored |
| `POST /api/v1/approvals/{approval_id}/execute` | *(empty)* | the whole action, re-derived from the stored request |

`[DECISION]` **The request bodies are Pydantic models with `extra="forbid"`.** A
request carrying `tenant_id`, `action_digest`, `risk`, `autonomy_level`,
`actor`, `capability` or any other authority field is **rejected 422** rather
than silently ignored. Ignoring is safe; rejecting is honest, and it means an
attempt to smuggle authority is visible in a log rather than invisible in a
success.

---

## 4. Remediation proposal and preview — derived, never invented

`[DECISION]` A **remediation catalog** maps an incident subject to a
*commissioned* capability. It contains no free text: the capability reference,
operation and payload shape come from the governed capability definition the
platform already registered, and the target namespace/workload are parsed from
the investigation's own `incident_ref`, which the platform wrote.

`[DECISION]` The preview is a **projection of backend facts**: side effect
class, code trust, isolation tier, reversibility and both digests come from the
capability contract and the platform's digest functions. The UI computes none of
them. If a value is not available from the backend it is reported as unavailable
rather than filled in.

`[DECISION]` **No remediation is proposed for a subject with no commissioned
write capability.** Phase 9 closed with exactly one (`rollout_restart`), and the
product says so rather than offering something that would be refused.

---

## 5. Frontend

`[DECISION]` One new panel and one new approval screen, in the existing
workspace. `product-api.ts` gains `productPost` — and the boundary test is
extended so the allowed POST paths are an **exact list**, not "POST is now fine".

`[DECISION]` The UI status vocabulary is its own: `PROPOSED`,
`AWAITING APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTING`, `OUTCOME ESTABLISHED`,
`VERIFIED`, `REFUSED`, `FAILED`, `INSUFFICIENT EVIDENCE`. **No green tick means
HTTP 200.** A stage is displayed only when backend evidence establishes it.

`[DECISION]` Approval requires explicit confirmation — the button is disabled
until the operator types the workload name, so an approval cannot be produced by
one stray click. No "approve all", no blanket approval, no auto-approval.

---

## 6. What will NOT be built

- No second executor, gateway, scheduler, approval decider or autonomy authority.
- No autonomy control of any kind in the UI or API.
- No product verification logic — Assurance is displayed, never computed.
- No RAG, no embeddings, no vector search.
- No exactly-once claim. Replay is measured and reported as it behaves.

---

## 7. Test plan

1. **Part B revocation** against real Redis with `REVOCATION_FAIL_OPEN=false`.
   `[FACT]` Already probed: `redis_connected: True`, `fail_open: False`,
   revoke → `is_revoked: True`. Not blocked.
2. **The 9.9C negative matrix re-run through the product path** — every case a
   real HTTP request to the product API, each asserting `provider_writes == 0`
   against **cluster generation as ground truth**, and each recording
   `stopped_by` (authentication / authorization / governance / worker /
   assurance) rather than collapsing to "blocked".
3. **Exactly one real provider write** on the disposable k3d cluster, with
   generation before/after, pod identity, image and replica count checked.
4. Replay, crash boundaries, audit chain, performance.

`[FACT]` Environment confirmed live: k3d `cortex-p99b` up 159m with
`payments-api`, `billing-api` and the contained worker all Running; service
account tokens re-minted (24h) and the API server answers 200; disposable Redis
on 55379; PostgreSQL on 55437.
