# ADR-017 — Request Context Runtime

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-09)
- **Related:** ADR-010 (contracts), ADR-012 (events), ADR-015 (audit), ADR-016 (fitness functions)

## Context

Invariant **I6** — *every tenant-scoped read and write carries tenant identity to
the storage layer* — has reported **PARTIAL** since the architecture gate went
live. Contracts refuse to construct without a `TenantScope`, but nothing carries
identity through an operation, and the integrity audit wrote
`TenantRef("system")` as a placeholder because the legacy dispatch path had no
tenant.

That placeholder was wrong in two ways: it invented an owner, and it made a real
tenant named "system" indistinguishable from the absence of one.

Retrofitting tenancy is the migration that kills companies. Doing it across ten
tables is ordinary work; across ninety it is a rewrite. PR-11 is about to move
three stores to PostgreSQL, and migrating them without tenant columns would mean
migrating them twice.

## Decision

Create `backend/platform/context` — one immutable, explicitly-passed
`ExecutionContext` composing identity, tenancy, trace, correlation, request
metadata, and optional organization / workspace / mission / flags / locale.

### No ambient context, deliberately

`contextvars` would make propagation invisible and therefore effortless. That is
precisely the problem: an operation that can obtain a context *without being
given one* can also obtain the **wrong** one, and a cross-tenant read caused by
a stale context variable is easy to write and nearly invisible in review.

Explicit passing turns an untenanted or misattributed operation into a signature
change rather than a runtime surprise. It is more typing; that is the point.

Two tests enforce this: the package exposes no ambient accessor, and no module
imports `contextvars`, `threading`, or `_thread`. The second is checked by
import analysis rather than text search, because the docstrings *mention*
`ContextVar` to explain the decision.

`backend/database/tenancy.py` keeps its own `ContextVar` for the SQL
`search_path`. That is a **session** concern bound at the connection boundary,
not a request context, and it stays where it is.

### No default tenant, and no implicit one

`TenantContext` has no zero-argument form, no `DEFAULT_TENANT`, and no fallback.
An untenanted operation cannot be expressed.

### Platform-internal work is explicit, not disguised

Some work genuinely has no tenant: a scheduler tick, a startup check, the
approval dispatcher replaying an EventBus payload whose tenancy was never
captured.

`TenantContext.platform_internal(reason=...)` marks that absence rather than
inventing an owner. It demands a stated reason, reports `is_platform_internal`,
and uses the reserved id `__platform_internal__` — double-underscored so it
cannot collide with a real tenant and is trivially greppable. The reason reaches
every audit record, so a reviewer can tell a legitimate scheduler tick from a
missing plumbing job.

**This does not fully satisfy "no implicit system tenant" — it satisfies "no
*implicit* system tenant."** A distinguished value still exists; it is now
explicit, justified per use, and countable. Eliminating it entirely requires the
approval store to capture tenancy at write time, which is PR-11.

### Never partially populated

Identity, tenancy, trace, correlation, and request metadata are mandatory.
Optional members are optional because they are genuinely absent for some
operations, not because they may be filled in later.

There is deliberately **no builder** and no mutable staging object, so a
half-built context cannot exist to be passed by accident. A test asserts the
class exposes no `builder`, `new`, `empty`, or `blank`.

### Cross-tenant contexts are refused at construction

A context whose organization or workspace belongs to a different tenant raises.
Checking at construction rather than at each use means the leak cannot survive
one consumer forgetting to look at the right member.

### Three identifiers, not one

`trace_id` spans a distributed request. `correlation_id` spans a causal chain
that may outlive many requests. `causation_id` names the single operation that
directly caused this one.

The same distinction ADR-012 draws for events, applied to operations — so an
event emitted mid-operation inherits a causal position that already exists
rather than inventing one. `child_operation()` preserves correlation, advances
causation, and creates a child span, which is why building a chain by hand is
never necessary.

### Audit records attribution from one value

`AuditRuntime.record_in_context()` takes an `ExecutionContext` and derives
tenant, principal, correlation, causation, trace, and request identity from it.
An audit record therefore cannot carry a tenant from one operation and a
principal from another.

It is typed `Any` rather than importing `ExecutionContext`, because
`platform.audit` must not depend on `platform.context` — audit is the more
foundational of the two, and a cycle would make either impossible to test alone.

## Alternatives Considered

**`contextvars` for ambient propagation.** Far less plumbing; FastAPI and
asyncio make it idiomatic. Rejected — see above. The failure mode it enables is
exactly the one I6 exists to prevent.

**Extend `contracts.SecurityContext` instead of a new package.** It already
carries principal, scope, and capabilities. Rejected: it is *vocabulary* that
crosses a boundary, and adding trace ids, feature flags, and request metadata to
it would make every context boundary carry transport concerns. `ExecutionContext`
composes it and exposes `.security_context` for the boundary.

**Make context optional with a `None` default.** Would allow incremental
adoption without touching call sites. Rejected: an optional context is one
nobody passes, and I6 would stay PARTIAL indefinitely.

**Delete the placeholder and require a tenant everywhere now.** Rejected as
dishonest: the dispatch path genuinely has no tenant until PR-11 captures it.
Forcing a value would mean fabricating one, which is what this ADR is fixing.

## Consequences

**Positive**

- Tenant identity has a single carrier, ready for PR-11's schema.
- The `TenantRef("system")` fabrication is gone; the gap is explicit and counted.
- Audit records gained trace, span, request, and delegation attribution.
- Cross-tenant contexts are impossible to construct.
- Correlation survives arbitrary nesting.

**Negative**

- Every operation eventually needs a context parameter. Threaded so far through
  audit and the dispatch path; the rest arrives with each context migration.
- More verbose than ambient propagation, permanently.
- `ExecutionContext` has eleven members. Justified by "never partially
  populated" — a smaller context would push the rest into ad-hoc parameters.

## Remaining Risks

1. **I6 is still PARTIAL, not ENFORCED.** The context exists and carries tenancy,
   but no storage-layer check rejects a query missing it. Promoting the invariant
   needs PR-11's schema, where a probe can assert a cross-tenant read returns
   nothing.
2. **`__platform_internal__` remains.** One use site today, explicitly reasoned.
   The count is the size of the attribution gap.
3. **Threading is incomplete by design.** Approval, audit, and dispatch carry
   context; events, verification, and storage interfaces accept it but most
   callers do not yet supply one. Doing all of it in one PR would be a rewrite,
   which the standing instruction rules out.
4. **Nothing yet prevents a new untenanted call path.** A fitness rule requiring
   an `ExecutionContext` parameter on context entry points would close it; that
   belongs after the contexts exist (PR-40).
