# ADR-046 — Governed Delegation and the First Concrete Execution Path

**Status:** Accepted
**Date:** 2026-08-08
**Phase:** 5.3
**Supersedes:** nothing. **Amends:** ADR-040 (delegation refusal), ADR-036 (worker lifecycle), ADR-044 (durable state).

---

## Context

After Phase 5.2 the platform had durable state, distributed coordination, a
provider adapter fabric and a production connectivity path — and could not
actually perform a single real provider operation. Two things stood in the way,
and both were deliberate.

**Delegation was refused outright.** ADR-040 identified that nothing could
answer "may this actor act for that principal", and Phase 4.4 chose absence over
a guess: every on-behalf-of invocation refused. Phase 5.1 gave the grant a
durable table with no way to write to it.

**No worker was ever enabled.** `build_github_connector` returns a `WorkerEntry`
at `REGISTERED`/`UNVERIFIED`/`UNAVAILABLE`, and nothing moved it, because moving
it as a side effect of assembling a graph is how a wiring change becomes an
authority change.

Both gaps were correct as gaps. Neither was a place to stop.

## Decision

### 1. Delegation is four steps, and the fourth is not "trust the workflow"

    request   somebody asks. The row is evidence of an ask, not authority.
    approve   somebody *else* decides, against the digest they were shown.
    issue     the grant appears, and only against an approval that exists.
    revoke    the grant stops working, immediately and attributably.

The enforcement is **one layer below the workflow**.
`SqlDelegationRepository.issue` takes `request_id`, `approval_artifact_id` and
`approved_by` as keyword arguments with no defaults. `DelegationWorkflow` is the
only thing that can assemble a matching set, so routing around it does not yield
an unapproved grant — it yields a `TypeError`. A gate that lives in the same
place as the thing it gates is a convention; this is a signature.

Issuance and the request transition happen in **one unit of work**, and the
transition is conditional on the request still being approved-and-unissued. Two
concurrent issuances therefore produce one grant and one refusal, verified
across two real processes.

### 2. Approval binds to a digest, and reuses the existing vocabulary

Reused from `backend/contracts/approval.py`: `ApprovalOutcome`, `PayloadDigest`,
`HashAlgorithm`, and the `can_approve` rule `ApprovalDecision` enforces. There is
no second approval engine.

**Not** reused: `ApprovalArtifact`. Its contract binds an `ExecutionContract` —
it proves a human approved *the run that will happen*. A delegation is not a run.
Manufacturing an empty `ExecutionContract` to fit would produce an artifact whose
digest covers a fiction, and a fictional binding is worse than an honest absence.
The delegation approval binds to `request_digest`, which covers the real thing:
the pair, the tenant, the scope, the validity and the requester.

`approve()` takes the digest the approver was **shown** and compares it, in
constant time through `PayloadDigest.matches`. A scope widened after review no
longer matches and the approval is refused. That is the defence against the
attack that actually defeats human review: show a human one thing, execute
another.

### 3. Privilege separation exists; an approver *model* does not. Stated, not implied.

`SeparationOfDutyPolicy` refuses when the approver is the actor gaining
authority, the principal being borrowed, the requester, or not human. It enforces
**no entitlement model**, because this codebase has none: `approval_center` has
workflow machinery and `PrincipalRef.can_approve` states the human-only rule, but
nothing answers "is this person entitled to approve a delegation of *this* scope
in *this* tenant".

So `ApproverPolicy` is a port that fails closed, the default is named after what
it actually enforces rather than `DefaultApproverPolicy`, and **the gap is
recorded here rather than papered over**. A deployment with an approver directory
supplies its own policy.

### 4. Revocation is immediate because nothing is cached

`DurableDelegationAuthority` reads the table on every check. There is no memo, no
TTL and no cache to invalidate — a revoked delegation stops working on the next
check, and "revoked, effective in thirty seconds" is not revocation. The cost is
one indexed read per delegated invocation.

Revocation touches **one row**. It does not reach into `cp_execution`,
`cp_authorization` or `cp_outbox`: a run admitted under a grant was genuinely
admitted under it, and rewriting that would make revocation a way to erase
history. Revocation changes what happens next and nothing else. An invocation
already running keeps running — stopping it is cancellation, a different
mechanism with different evidence.

### 5. The first governed operation is `github.repository.get_repository`

A `READ`, against a declared path template, with a bounded response.
`ConnectorAdapter` runs in-process, which ADR-005 calls `AMBIENT`, and `AMBIENT`
is sufficient for `READ` — so this operation is permitted **by the existing rule
rather than by an exception carved for it**.

The catalog's two `IRREVERSIBLE_WRITE` operations stay refused with
`isolation_insufficient`, and `assert_write_refusal_intact` is a check rather
than a comment: if a future change gives the connector a tier that would permit
them, commissioning raises and names what changed. Making the first operation a
read is what lets that refusal stay in place instead of becoming the thing
standing between the platform and a demo.

`first_governed_operation.py` **invokes nothing**. There is exactly one execution
path — `SecureCapabilityInvocationGateway.invoke` — and a second, however
convenient, would be two places deciding whether a provider call may happen.

### 6. Commissioning is three recorded decisions, and validation is honest about what it checked

`WorkerCommissioning` drives `REGISTERED → VALIDATED → ENABLED` and refuses every
shortcut: enabling before validating, trusting before validating, enabling a
validated-but-untrusted worker. Trust is a separate call with a stated reason and
`enable` has no argument that would grant it on the way past.

One correction worth recording, because the first version of this was wrong.
`WorkerEntry.worker_digest` is a property returning `implementation.digest`,
itself computed on access — so "recompute the digest and compare it to
`worker_digest`" compares a value to itself and passes unconditionally. That is
worse than no check: it reads like tamper detection and detects nothing.

`validate()` therefore takes `expected_digest` — what the validator actually
reviewed. Supplied, it is a real two-source comparison. Omitted, the step
**pins** the digest and reports `digest_verified: False`, because pinning is not
checking and the record must not imply otherwise.

### 7. Connector configuration holds references, never material

`cp_connector_config` is keyed `(tenant_id, provider_id, environment)` — tenant
first, so a configuration cannot exist without one. This replaces the V1
`POST /api/connectors/{id}/connect` body (`credentials: Dict[str, str]` into an
untenanted process-wide store), gated off in Phase 4.4.

`credential_ref` holds `cred://<tenant>/<id>`. `_refuse_secret_material` refuses
fields *named* like secrets and values *shaped* like them — known provider
prefixes, and anything long and dense enough to be a bearer token. Neither is a
complete defence and neither is claimed to be; what they buy is that a secret
cannot arrive here *accidentally*, which is how secrets actually arrive in
configuration tables. Refusal messages quote the field name and never the value.

### 8. `init_db` is refused outside development

`init_db` created tables with `create_all`, and `main.py` called it **as the
fallback when migration failed** — so a production deployment with a broken
migration would build its schema from the current models, start cleanly, and log
a warning. The result is a database no migration authored: `alembic_version`
stuck at the last revision that worked, columns present that no revision added,
and the next migration running against a schema it cannot reason about.

`init_db` now raises `SchemaBootstrapRefused` unless the caller passes
`allow_non_production=True` **and** the environment is non-production — the flag
permits, it does not override. An unset environment counts as production, because
refusing on a laptop prints an error while permitting in production silently
forks the schema. `main.py` no longer catches the refusal: a process that cannot
establish its schema through migrations does not start.

### 9. Fake observability removed rather than documented

`NodeCompensationStarted` declared that "a compensating action was dispatched"
and required a `compensating_node_id`. Nothing in this platform dispatches one —
`Execution.compensate` marks a node `COMPENSATED` — so the event could never be
constructed truthfully, and never was. An operator subscribing to
`execution.runtime.compensation_started` would have waited forever while
believing they had compensation observability. It is **removed**.

`NodeCompensationConcluded` is now emitted from `ExecutionService.compensate`
with `outcome_known=False` and `change_remains=True`, which is the truth: somebody
asserted a compensation and the platform cannot confirm it.

## Consequences

**Gained.** A governed way to grant identity-borrowing authority, with a request,
a distinct human approver, a digest binding, one-grant-per-approval enforced by
the database, and immediate revocation. A worker that can be commissioned to
executable through checked transitions. Tenant-scoped connector configuration
that refuses secrets. A schema that only Alembic can author.

**Accepted.** One indexed read per delegated invocation, on purpose. A
`SeparationOfDutyPolicy` that checks four identities and no entitlements, on
purpose and recorded. Migration 0012 is additive; its downgrade deletes approval
evidence while leaving the grants issued under it, which is stated in the
migration.

**Not claimed.**

* **PostgreSQL is NOT VERIFIED.** `scripts/postgres_durability_harness.py` was
  run and reported `NOT VERIFIED` (exit 2): no server reachable, Docker unusable.
  SQLite was not substituted. Serialization-failure and deadlock classification,
  `BIGSERIAL` allocation, pool exhaustion, connection loss during `COMMIT`,
  JSONB behaviour and concurrent election under real MVCC remain unverified.
* **No real provider was contacted.** The first governed operation is verified as
  far as commissioning. Whether GitHub answers is untested and unclaimed.

## Deferred, and recorded so the deferral can be checked

`backend/api/deferred_capability_inventory.py` holds these as data, with
`assert_deferrals_intact()` asserting nothing has quietly grown an
implementation:

* **MCP over SSE** — the kind is vocabulary and absent from
  `PRODUCTION_TRANSPORT_KINDS`; a streaming reader needs a `TransportOutcome`
  shape that can express a stream. Proposed 5.4.
* **Sandboxed stdio workers** — no worker launches a subprocess. Claiming
  `CONTAINED` on a bare `subprocess.Popen` would be the most dangerous lie
  available here: it would unlock the write refusals without providing the
  containment they were refused for. Proposed 5.4.
* **Tenant fairness in the queue** — `claim_batch` is fair between items and
  silent about tenants; `tenant_depths()` makes the starvation observable and
  nothing acts on it. Needs a policy decision, not an `ORDER BY`. Proposed 5.4.
