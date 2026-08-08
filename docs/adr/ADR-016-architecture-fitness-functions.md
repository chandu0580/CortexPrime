# ADR-016 — Architecture Fitness Functions

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-07)
- **Related:** all prior ADRs; this one enforces them

## Context

The Constitution states: *"Violation of any invariant is a defect, regardless of
tests passing."* That sentence has been true and unenforceable since Phase 0.

Six PRs have built real enforcement — I2 has two independent checks, I3 has a
durable chained audit — but nothing fails when an invariant is violated.
Documentation and good intentions do not prevent architectural drift. Three
mechanisms do, and all three are mechanical: CI blocks the merge, the rule is
executable, and the rule itself is tested.

The Phase 1 guide identified this as the work that "locks in everything PRs
01–06 built."

## Decision

Build `backend/platform/architecture` — the Constitution as executable fitness
functions, run by CI on every commit.

### Two kinds of check, and the difference matters

**Structural rules** analyse the import graph, parsed with `ast` rather than
imported. Nothing executes application code, so the gate runs without
application dependencies and cannot be broken by an import side effect.

**Invariant probes** actively construct a violating state and assert the system
refuses it.

The distinction is load-bearing. A structural check confirms a guard is
*present*; a probe confirms it *works*. If someone deleted the digest comparison
in the dispatcher, a structural check would still see the module and pass. The
I2 probe would not — it forges a payload and asserts refusal.

### Rules operate on a graph, never on hard-coded paths

Every rule takes a `ModuleGraph` built from a root directory. That is what makes
a rule testable *in both directions*: a test synthesizes a tree that violates the
rule and asserts the rule catches it.

A rule that can only run against the real repository can only ever be shown to
pass, which proves nothing about whether it would catch a regression. Half of
PR-07's test suite is exactly this — twenty tests that break a rule on purpose.

### Three outcomes, deliberately distinguished

| Outcome | Blocks merge | Meaning |
|---|---|---|
| **Blocking** | Yes | An enforced rule or invariant is violated |
| **Warning** | No | A rule the codebase is migrating toward |
| **Skip** | No | Nothing to check yet, or no enforcement point |

**A skip is never reported as a pass.** `RuleResult.passed` returns `False` when
skipped, because a skip counted as a pass is precisely how an unenforced
invariant comes to look enforced. Four invariants are currently skipped and each
names the PR that will enforce it.

The warning category exists because without it the suite would be permanently
red — the existing `backend/api` violates interface purity widely — and a
permanently red suite is one people learn to ignore.

### The suite holds itself to its own rules

Writing this exposed a real violation **in the harness itself**: the I2 probe
imports `backend.services`, which Constitution S10 forbids `platform/` from
doing. The gate caught it on first run.

The cheap fix was an exemption for `invariant_tests.py`. That was rejected: an
exemption granted to the module that enforces the rules is the first step in the
erosion this suite exists to prevent.

Instead, probes are injectable. Service-level probes live in
`tests/architecture/probes.py` and are passed in via
`constitutional_invariants(probes=...)`. An invariant whose probe is not
supplied reports as **skipped**, naming what is missing, so an unregistered
probe cannot be mistaken for a pass.

### Reports locate the breach

Three formats — text, markdown, JSON — each naming the rule, module, line, and
offending import.

This is not cosmetic. When a fitness function fails, the fastest route to green
is deleting the rule. A report that says "there is a boundary violation
somewhere in 746 modules" makes that the rational choice. One that says
`backend.contracts.approval:12 imports requests` does not.

The dependency graph is included because drift is usually visible in the shape
of dependencies before any single rule fails.

## Current status

| | Invariant | Status |
|---|---|---|
| ⏳ | **I1** — policy decision before execution | Not enforced — PR-29/30 |
| ✅ | **I2** — approved payload is executed payload | Enforced, two layers |
| ✅ | **I3** — audit append-only and verifiable | Enforced |
| ⏳ | **I4** — findings cite evidence | Not enforced — no finding context yet |
| ⏳ | **I5** — credentials expire with execution | Not enforced — brokering unbuilt |
| ✅ | **I6** — tenant identity travels | Partial — contracts + storage boundary (ADR-018); ENFORCED needs PR-11's tenant column |
| ✅ | **I7** — memory may not authorize | Enforced |
| ⏳ | **I8** — no duplicated authoritative state | Not enforced — PR-31; 12 Mission definitions |
| ✅ | **SELF-AUTH** — platform never authorizes itself | Enforced |
| ✅ | **IMMUTABLE** — contracts are frozen | Enforced |

Six enforced, one partial, four pending. Against the real repository: **12
passed, 0 failed, 8 skipped, 36 warnings across 746 modules.**

## Alternatives Considered

**An off-the-shelf tool (import-linter, pytest-archon).** Would cover the
dependency rules with less code. Rejected as insufficient rather than wrong: no
existing tool expresses constitutional invariants like "memory may propose but
never authorize", and half the value here is the probes. Adopting one for the
structural half and this for the rest would mean two report formats and two
places to look — worse than one.

**Keep the ad-hoc checks in `tests/*/test_dependency_isolation.py`.** They work.
Rejected: they cannot be run outside pytest, they produce no report, they are
duplicated across two files that must be kept consistent by hand, and they
cannot be tested against a violating tree.

**Fail the build on warnings too.** Rejected. `backend/api` violates interface
purity throughout; blocking on it would make the gate permanently red on day
one, and a gate nobody can turn green teaches people to route around it.

**Put probes in `platform/` and exempt the module.** Rejected — see above.

## Consequences

**Positive**

- The Constitution is executable. Drift fails a build instead of a review.
- Every rule is proven to catch its violation, not merely to pass today.
- Unenforced invariants are visible with their tracking PR, rather than absent.
- The gate found a real violation in its own first run.

**Negative**

- Another suite to maintain. Mitigated by the rules being data.
- The warning category could become a dumping ground. Each warning-severity rule
  carries a comment stating when it becomes an error.
- `ast`-based analysis cannot see dynamic imports (`importlib.import_module`
  with a computed name). A determined violation can evade it; a careless one
  cannot, and careless is the common case.

## Remaining Risks

1. **Dynamic imports are invisible** to static analysis. Accepted.
2. **Probes only cover what they probe.** I2's probe exercises the two digest
   comparisons; it does not prove the dispatcher calls them. That gap closes
   when the dispatcher moves into a bounded context with its own journey test.
3. **The `skipped ≠ passed` rule depends on nobody "fixing" it.** A future
   contributor could make skips count as passes to turn the report green. The
   test `test_unenforced_invariants_report_as_skipped_not_passed` exists to
   prevent that.
4. **Warnings may be ignored indefinitely.** 36 exist today, all interface
   purity. They are tracked, not silent.

## Compliance

Enforced by `tests/architecture/` (140 tests) and the `Architecture Gate`
workflow. The workflow has two jobs on purpose: one proves the architecture
holds, the other proves the gate would notice if it stopped holding.

---

# Amendment 1 (PR-08) — File-Based State Guard

- **Status:** Accepted
- **Date:** 2026-08-04
- **Adds:** rule `STATE-NO-NEW-FILE-STORES`

## Why this rule exists

The Phase 1 compliance report names file-based state as the most expensive
defect in the codebase (V3). It has already caused one total outage: a ~200ms
synchronous JSON rewrite firing on every Docker daemon event starved the single
event loop until `/api/auth/login` hung indefinitely. That bug was invisible to
unit tests and to type checking; it was found only by running the real app.

PR-11 migrates the security-critical stores to PostgreSQL. This rule exists for
the interval before that, because **nothing today prevents a forty-fourth JSON
store appearing**, and every one added between now and then is another thing to
migrate — and another candidate for the same failure mode.

The rule converts the migration from a cleanup somebody must remember into a
ratchet that cannot slip backwards.

## Why the grandfather list exists

The brief specified an allowlist of three stores with everything else failing
CI. Applied literally to this repository that produces roughly eighty-four
blocking violations on the first run: 81 modules already write state files,
across 76 distinct filenames.

A gate that is red on the day it ships is a gate people learn to route around —
the exact failure ADR-016 rejected when it introduced the warning severity. So
the rule has three tiers rather than two:

| Tier | Contents | Severity |
|---|---|---|
| **Approved** | The three the brief names | Warning — migrating in PR-11 |
| **Grandfathered** | 76 stores that already existed | Warning — frozen inventory |
| **Anything else** | | **Error** — blocks the merge |

The approved three are kept in their own set rather than folded into the
inventory, so the security-critical stores stay visible instead of buried among
seventy-six others.

## When entries may be removed

**The inventory may only shrink.** Removing an entry — because the store was
migrated to PostgreSQL or deleted — is ordinary work needing no ceremony.

**Adding an entry requires an ADR** explaining why the transactional store was
insufficient for that data. Without that asymmetry the list becomes a place to
put things to make the build green, which is how a ratchet turns into a
formality.

`test_the_inventory_covers_what_exists` fails if a detected store is in neither
set, so the inventory cannot silently drift out of date.

## How PR-11 eliminates the remaining warnings

PR-11 migrates `pending_approval_actions.json`, `approval_decisions.json`, and
`integrity_audit.jsonl` to PostgreSQL together. On completion:

1. Those three come out of `APPROVED_STORES`, which becomes empty.
2. Their warnings disappear from the gate.
3. The 76 grandfathered warnings remain, and are the visible backlog for the
   general state migration.

The three move together rather than individually because splitting
security-critical state across two persistence models mid-migration is worse
than either endpoint.

## Detection is a heuristic, stated plainly

A module is flagged when it both performs a write operation *and* mentions a
state-file literal. Correlating the two is what avoids flagging the many modules
that only *read* configuration.

Known limits:

- A filename assembled at runtime is invisible. Literals containing `{}` are
  skipped rather than recorded as a store called `{}.json`.
- In a module doing several things, a filename may be attributed to the wrong
  write. The module is still correctly identified.
- Configuration filenames are excluded by name. Several appear in this codebase
  as literals a connector *looks for* — the repository-analysis service names
  `Cargo.toml` and `.gitlab-ci.yml` to detect them in a customer repo, it does
  not write them. Detecting those would fill the inventory with entries nobody
  can act on.

The bias is deliberately toward false positives: one costs a line in the
inventory and a moment's thought, whereas a false negative is a store nobody
notices until PR-11 has to migrate it.

## Consequences

Gate status after this rule: **13 passed, 0 failed, 8 skipped, 119 warnings
across 747 modules.** The warning count rose from 36 to 119 — 83 of them are
file-state stores that were always there and are now counted.

That number is the point. It is the size of the state-migration backlog, and it
was previously invisible.

---

# Amendment 2 (PR-10) — Storage Boundary Tenant Guard

- **Status:** Accepted
- **Date:** 2026-08-05
- **Adds:** rule `TENANT-REPOSITORY-CONTEXT`
- **See:** [ADR-018](ADR-018-storage-boundary-tenant-guard.md)

## Why this rule exists

ADR-017 gave every operation an `ExecutionContext` carrying tenant identity.
Nothing compelled a repository to ask for one, and none of the 42 that existed
did. The identity travelled as far as the storage layer and stopped there.

`backend/platform/storage/` is the runtime enforcement point. This rule is the
static one: a guard only protects the repositories that use it, and nothing in
the type system makes a *new* repository use it.

## What it checks

For every class ending in `Repository` under a persistence path, each public
method must accept a parameter that could carry an execution context. A method
that accepts `tenant_id` directly is a stronger violation — the caller is
choosing the isolation boundary, which is the anti-pattern I6 names.

Subclasses of `TenantScopedRepository` are exempt from method-level checking:
the base threads the context through by construction.

## The ratchet

`GRANDFATHERED_REPOSITORIES` records the 42 repositories that predate the guard.
They report as warnings so the gate stays green while they migrate; anything not
on the list errors and blocks the merge.

Same one-way ratchet as `STATE-NO-NEW-FILE-STORES`, same rule: **the list may
only shrink.** An addition is a known cross-tenant hazard, and it must show up as
a one-line diff to a frozenset.

The gate went from 13 rules to 14 and from 119 warnings to 297. The 178 new
warnings are the grandfathered repository methods — previously invisible, now
counted. That number is the migration backlog.

## I6 is still PARTIAL

Deliberately. The guard is real, tested and blocking, but no model carries a
tenant column, so the grandfathered repositories cannot adopt it. Marking the
invariant ENFORCED while a cross-tenant read is one `MissionRepository.get()`
away would put a false claim in a compliance artifact. Promotion needs PR-11.
