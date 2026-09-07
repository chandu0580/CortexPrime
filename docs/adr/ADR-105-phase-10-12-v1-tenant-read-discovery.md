# ADR-105 — The V1 tenant read surface: findings and a recommendation

- **Status:** PROPOSED — discovery only, awaiting a decision
- **Date:** 2026-09-07
- **Phase:** 10.12 (discovery)
- **Changes:** none. No production code, no migration, no deletion.

## Context

Phase 10.11 retired `TenantManager`, shrank `GRANDFATHERED_STORES` for the
first time, and closed with a recommendation: *retire the V1 tenant read
surface*. Three `GET` routes remained, projecting durable rows into a legacy
shape that omits `domain`, `plan`, `settings` and `permissions`.

A recommendation is not a finding. This phase asked whether those routes still
have a legitimate consumer, and whether the surrounding legacy artifacts —
`iam_users`, the JSON files, the frozen inventory — are what earlier phases
assumed. Full evidence is in `docs/PHASE_10_12_DISCOVERY.md`.

## What discovery established

**The three reads have no production consumer.** Not in the backend, and not in
the frontend. The frontend evidence is deliberately not a source scan: the
compiled 334 MB Next.js bundle — 3 998 JavaScript files, what a browser
actually loads — contains **no reference to `/api/tenants`**, while the control
path `/api/v1/investigations` matches in it. The only callers anywhere are two
harnesses that exist to prove these routes *refuse*.

**They are safe.** Reads leak nothing (database state byte-identical across
repeated calls), scope correctly (foreign tenant 404, forged query/header/body
inert, no-claim 403, anonymous 401), depend on no legacy module (all three
return 200 in a child process where `backend.auth.tenant` cannot be imported),
and import nothing that could execute a provider, invoke a worker or create
authority.

**All four V1 writes are refusals**, with database state unchanged. The two
silent no-ops Phase 10.11 found are closed and no new one has appeared.

**`iam_users` is dead**, on a chain checked link by link: the repository is
instantiated only by `RepositoryFactory.user_repo`, `.user_repo` is never
called, the one class that would query it is imported by nothing outside
`backend/identity/`, `register_identity_services()` registers nine services and
none of them is a user repository, and the table does not exist in any governed
database.

### The finding that changes the recommendation

Phase 10.11 framed the problem as *fields omitted*. That is half of it. The V1
tenant shape is simultaneously **wider and narrower** than the truth:

- three fields have **no authoritative source** and are returned empty —
  `domain: null`, `plan: ""`, `settings: {}`;
- **four real columns are dropped** — `created_by`, `source`, `updated_by`,
  `updated_at`, which is precisely the provenance Phases 10.9–10.11 added;
- `permissions` is `[]` **by construction**, so a client reading it concludes
  the member holds nothing — which is not what that field used to mean;
- and `user_id` **silently changed meaning**. It now carries a membership id
  (`mbr-…`), not a user id. The field name did not change; a client holding an
  older value holds one that no longer resolves.

A shape that reports absence honestly is defensible. A shape whose identifier
quietly means something else is not, and it is the strongest argument for
retirement rather than for filling the gaps in.

## Decision

**None yet — this is discovery.** No stop condition fired, so implementation is
not blocked; it is simply not this phase's to do.

What the evidence supports, for a later phase to accept or reject:

1. **The three read routes can be deleted**, together with `TenantResponse` and
   `TenantUserResponse`. Nothing reaches them, and their shape actively
   misleads about `user_id` and `permissions`.
2. **The four refusals should be kept.** They are load-bearing documentation:
   each names where the governed operation moved, and deleting them would turn
   an informative 403 into a 404 that explains nothing to an operator following
   an old runbook.
3. **`repositories/iam.py`, `iam_users` and `iam_roles` can go**, on the
   seven-check chain above. Dropping the tables is a migration and therefore a
   decision with a blast radius; the dead Python can go without one.
4. **The JSON files must stay for now.** Their one purpose — read-only
   bootstrap import — is real until an operator decides no installation will
   ever import again. That is not a call a phase should make unilaterally.
5. **`CortexSidebar.tsx` links to `/settings/tenants`, a page that does not
   exist.** Unrelated to retirement, found while looking, and a real 404 in the
   product navigation.

## What was deliberately not established

The 74 remaining `GRANDFATHERED_STORES` entries were **not** individually
classified as runtime, bootstrap-only or dead. They belong to the wider V1
surface this phase family has not touched, and a guess recorded as a finding
would be worse than the gap. **[NOT VERIFIED — out of scope, stated rather than
estimated.]**

A **live browser session was not driven**. The compiled-bundle grep is stronger
than source inspection and weaker than a network capture, and is labelled that
way rather than presented as equivalent.

## Consequences

Retiring the reads changes nothing about authentication, membership, authority,
approvals, execution, the workspace or the approval queue — established by
dependency analysis without modifying any of them.

The performance numbers in the discovery document are a **baseline, not a
comparison**: the V1 list returns one tenant row while the governed member
listing returns every membership and its authority note, so the two are not
doing the same job and the faster number means nothing on its own.

## Recommended next phase

**Phase 10.13 — delete the V1 tenant read surface and the dead IAM module.**
Small, bounded, and entirely deletion: three routes, two response models, one
repository module, two unused tables, and one dead navigation link. Keep the
four refusals, keep the read-only importer, keep the JSON.

The one judgement call it inherits is whether dropping `iam_users` and
`iam_roles` warrants a migration, given they exist in exactly one non-governed
database. That is worth deciding explicitly rather than by default.
