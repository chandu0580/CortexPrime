# ADR-018 — Storage Boundary Tenant Guard

- **Status:** Accepted
- **Date:** 2026-08-05
- **Phase:** 1 (PR-10)
- **Related:** ADR-010 (contracts), ADR-016 (fitness functions), ADR-017 (request context)

## Context

ADR-017 built `ExecutionContext` and threaded it through operations. It closed
the question of *how* tenant identity travels and left open the one that matters
at the boundary: **nothing compelled a repository to ask for it.**

A repository could — and every one of the 42 that predate this PR does — accept a
primary key and return whatever row matches, with no notion of who was asking.
The context existed; the storage layer simply never looked at it.

ADR-017 named this precisely in its own Remaining Risks:

> I6 is still PARTIAL, not ENFORCED. The context exists and carries tenancy, but
> no storage-layer check rejects a query missing it.

This ADR is that check.

### What we found before building

Two facts, established by reading the codebase, shaped the whole design:

**No model carries a tenant column.** `grep tenant_id backend/database/models/`
returns nothing. Three models carry `organization_id`, and
`backend/contracts/tenant.py` explicitly forbids using it as a substitute:

> Organizations subdivide a tenant for ownership and routing. They are *not* an
> isolation boundary — isolation is the tenant's job alone. Treating an
> organization as a security boundary would violate I6.

So there is no column to filter on, and the obvious stand-in is ruled out by the
vocabulary itself.

**`platform/` may not import `backend.database`** (`DEP-PLATFORM-NO-CONTEXTS`).
Whatever enforces this cannot know about SQLAlchemy.

## Decision

Build the enforcement mechanism now, at a layer that does not depend on the
schema, and ratchet the existing repositories rather than rewriting them.

### The guard is persistence-agnostic

`backend/platform/storage/` deals in a scope **column name** and a tenant
**value**. It never builds SQL. `RepositoryGuard.scope_filter()` returns
`("tenant_id", "acme")` and leaves turning that into a predicate to whoever holds
it.

This is forced by S10, but it is also right on the merits: Redis
(`infrastructure/redis/keys.py`), Neo4j (six repositories) and the JSONL audit
store all need the same boundary, and a guard that spoke SQLAlchemy would have
stranded them outside it.

### Tenant identity is derived, never supplied

There is no `tenant_id` parameter anywhere in the guard's surface, and
`RepositoryContextRule` reports a repository method that accepts one as a
violation in its own right — a *stronger* finding than a missing context.

A repository whose caller passes the tenant is not isolating anything; it has
delegated the isolation boundary to the least trustworthy party in the call. The
test `test_guard_exposes_no_way_to_supply_a_tenant` asserts against the
signature rather than the behaviour, so adding such a parameter fails even if the
implementation would have ignored it.

### Platform-internal access is opt-in per record type

`StorageBinding.platform_internal_allowed` defaults to `False`. A record type
states for itself whether it tolerates an untenanted sweep.

Global would have been easier and useless: an escape hatch that is on by default
is not an escape hatch, it is the door. Per-type makes the exceptions countable,
and `tests/database/test_tenant_scoped_repository.py::test_platform_internal_is_opt_in_per_repository`
proves the permission attaches to the declaration rather than leaking from the
table or the context — two repositories over the same table, opposite answers.

### A cross-tenant write is refused, not restamped

`RepositoryGuard.stamp()` raises when a record already carries a different
tenant, rather than overwriting it with the authorised one.

Overwriting is the tempting behaviour and the wrong one: it converts an attempted
cross-tenant write into a *successful* same-tenant write, which destroys the only
evidence that the attempt happened. The test asserts the record is left unmutated
after the refusal.

### An unstamped row is a violation, not a pass

`validate_record_scope(None, ...)` raises. A row whose owner was never recorded
is not ownerless, it is unattributed — and treating "unknown owner" as "belongs
to whoever asked" is how one tenant inherits another's orphaned data after a
failed migration.

### `TenantScopedRepository` deliberately does not extend `BaseRepository`

Inheriting would have been shorter. It would also have made a scoped repository
substitutable for an unscoped one wherever the base type is annotated, so a
caller holding a `BaseRepository[T]` could write `repo.get(some_uuid)` and have
the uuid silently bound to `context`.

That call *would* be caught — `is_repository_context` rejects a `UUID` — but only
at runtime, in a path a type checker had already declared safe. Refusing the
inheritance relationship makes it a type error at the call site instead. A test
asserts `not issubclass(TenantScopedRepository, BaseRepository)` so a future
convenience refactor cannot quietly reintroduce it.

### A pk read raises where a list filters

`list()` and `count()` apply a predicate, so another tenant's rows are simply
absent. `get(pk)` fetches and then checks, raising `CrossTenantAccess`.

The asymmetry is deliberate. A caller of `get` already knows the id; returning
`None` would be indistinguishable from "no such row" and would silently swallow
evidence of an attempted cross-tenant read. A caller of `list` asked an
open-ended question and gets an honest, narrowed answer.

### The ratchet

`GRANDFATHERED_REPOSITORIES` lists the 42 repositories that predate the guard.
They report as **warnings**; anything not on the list is an **error** and blocks
the merge.

Same one-way ratchet as `state_rules.GRANDFATHERED_STORES`, same rule: **the list
may only shrink.** Adding an entry means adding a known cross-tenant hazard, and
forcing that to appear as a one-line diff to a frozenset makes it much harder to
wave through than a new file would be.

`stale_grandfather_entries()` reports names no live repository uses — a stale
entry silently widens the exemption, because a future repository reusing the name
inherits a pass it never earned.

## Alternatives Considered

**Retrofit `BaseRepository` to require a context.** Rejected. It would change the
signature of every method on the 42 existing repositories at once — the rewrite
the standing instruction rules out — and none of them could actually *use* the
context, because their models have no tenant column. The result would be a
mechanical churn of ~184 call sites that enforced nothing.

**Scope by `organization_id`.** Rejected, and not on pragmatic grounds:
`backend/contracts/tenant.py` states that treating an organization as a security
boundary is itself an I6 violation. Three models have the column; using it would
have produced a green gate over a broken invariant, which is worse than a red one.

**Use the existing schema-per-tenant machinery.** `backend/database/tenancy.py`
sets a PostgreSQL `search_path` per tenant. It is genuine isolation and it is
dead code — `set_session_tenant`, `ensure_tenant_schema` and
`TenantContextManager` have zero callers. Reviving it is a migration decision
that belongs to PR-11, and it would not have covered Redis or Neo4j.

**Enforce at runtime by wrapping the session.** Rejected. A session proxy that
injected a predicate would catch repositories that never asked for a context,
but only on paths that actually execute. Static analysis catches the ones nobody
runs in test.

## Consequences

- New repositories cannot silently bypass tenant scoping; the gate blocks them.
- Legacy repositories keep working unchanged. `BaseRepository` is untouched, and
  a test asserts its signatures.
- The gate grew from 13 rules to 14, and from 119 warnings to 297 — the 178 new
  ones are the grandfathered repository methods, now counted rather than
  invisible. That number is the migration backlog, and it is meant to shrink.
- The I6 probe moved from contract-level assertions to exercising the real guard,
  plus an injected probe (`tests/architecture/probes.py`) that drives a real
  `TenantScopedRepository` over a real SQLAlchemy engine.

## Remaining Risks

1. **I6 remains PARTIAL, not ENFORCED — and this PR could not honestly promote
   it.** The guard is real, tested and blocking for new code, but 42 repositories
   still read and write without it, and they *cannot* adopt it until their models
   carry a tenant column. Marking the invariant ENFORCED while a cross-tenant
   read is one `MissionRepository.get()` away would put a false claim into a
   compliance-facing artifact. ADR-017 already predicted this: promotion needs
   PR-11's schema.

2. **The rule matches on names, not types.** A repository class not ending in
   `Repository`, or one outside a recognised persistence path, is invisible to
   it. `test_every_real_repository_is_accounted_for` pins the current inventory
   so a rename cannot silently drop something, but a genuinely novel naming
   convention would slip through.

3. **`CONTEXT_PARAMETER_NAMES` accepts a parameter named `context` regardless of
   what it holds.** The rule cannot tell a real `ExecutionContext` from a
   dictionary that happens to share the name. Most of this codebase is
   unannotated, so requiring the annotation would have failed every existing
   repository for the wrong reason. The runtime guard catches the impostor;
   static analysis only confirms the parameter is there to be checked.

4. **Redis, Neo4j and the JSONL stores are unguarded.** The guard is
   persistence-agnostic by design so they *can* adopt it, but none has. The Redis
   key builder still derives its tenant prefix from the `database/tenancy.py`
   `ContextVar` — the ambient mechanism ADR-017 rejected — which means a
   background task inheriting a stale context variable still gets the wrong
   prefix.

5. **`_execute_scoped` is a convention, not a constraint.** A `TenantScopedRepository`
   subclass can reach `self._session` directly and issue an unscoped query. The
   architecture rule exempts subclasses of the scoped base from method-level
   checking precisely because the base threads the context — so a subclass that
   bypasses the base is the one hole the rule does not cover.
