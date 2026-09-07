# ADR-110 — Schema ownership implemented: Alembic owns it, and the entrypoint stops guessing

- **Status:** ACCEPTED
- **Date:** 2026-09-07
- **Phase:** 10.18
- **Parent:** `183a34c` — Phase 10.17 discovery (ADR-109, GO)
- **Evidence:** `docs/PHASE_10_18_VERIFICATION_REPORT.md`,
  `docs/PHASE_10_18_IMPLEMENTATION_MAP.md`
- **Unblocks:** Phase 10.16 (the `missions` ORM model), which stopped because
  two schema authorities disagreed (ADR-108)

> **Numbering.** Next available is **110**. ADR-107 is used **twice** (Phases
> 10.14 and 10.15); 108 is Phase 10.16; 109 is Phase 10.17. Nothing existing was
> overwritten. The 107 duplicate is still outstanding and is a documentation
> matter.

## Context

ADR-109 established that Alembic is the canonical application-schema owner and
that `infra/postgres/init.sql` owns nothing anything still needs. It returned GO
with two preconditions: fix the entrypoint pre-stamp **before or alongside**
unmounting `init.sql`, and recreate existing dev/staging volumes rather than
stamping them.

This phase implements that. Three files changed. No migration, no ORM model, no
schema change, no test modified.

## Decision

**1. The entrypoint stops guessing.** The block that wrote
`alembic_version = '0008'` whenever that table was empty is deleted. It is
replaced by *nothing* — not by a better heuristic.

An empty version table carries **no information**: it is equally consistent with
a brand-new database and a restored one. There is no safe discriminator, so the
correct behaviour is to stop classifying. Every state now resolves through
Alembic's own documented semantics, and the two genuinely ambiguous ones fail
closed:

| State | Behaviour | Verified |
|---|---|---|
| empty database | migrations run from `0001` | 23 ran, head, 55 tables |
| `alembic_version` present but empty | identical to absent; runs from `0001` | same |
| valid revision recorded | upgrade continues from it | at-head DB unchanged, md5-identical |
| **invalid revision recorded** | **exit 1** | `UndefinedObjectError`, 1 table |
| **tables present, no version row** | **exit 1** | `DuplicateTableError` |

**2. Recovery becomes an explicit operator signal.** `ALEMBIC_STAMP_REVISION`,
executed through `alembic stamp`. The discriminator is a human naming a
revision, never an inference from database state. Alembic validates it: a bare
prefix resolves to the **full canonical id**, and an unknown revision is refused
with a non-zero exit. The old code wrote the literal `'0008'` — an id that does
not exist in the lineage — and only "worked" by accident of prefix matching,
which is exactly what made the skip silent.

**3. `init.sql` is unmounted from `docker-compose.yml` and
`docker-compose.staging.yml`, and retained on disk.** `postgresql.conf` — a
different file in the same directory, named by each service's `command:` as
`config_file` — stays mounted.

## What changed the risk assessment

ADR-109 said an operator following the administrator guide **arms** the
pre-stamp by setting `DATABASE_URL`. **That was incomplete.** There is a second
gate, proven here by execution:

```
psql ABSENT in base
psql ABSENT after libpq-dev
```

`backend/Dockerfile` installs `libpq-dev` — the client *library* — not
`postgresql-client`, which provides the `psql` binary. Every `psql` call in the
entrypoint is `|| true`. **The pre-stamp was unreachable from any image this
repository builds.**

That makes the removal zero-risk rather than urgent. It does not make it
optional: adding `postgresql-client` for `pg_dump` or debugging is an ordinary
change that would arm the defect instantly and silently. **The trap is removed
while it is provably inert** — which is the cheapest moment to remove one.

The same finding carries a cost that is reported, not repaired: the advisory
migration lock uses that absent `psql` too, so it has **never been acquired in a
container**, and multi-replica deployments race unserialised. Fixing it means
either adding `postgresql-client` — which would arm the defect in the same
change — or moving migrations into a dedicated Job, which ADR-109 already
deferred.

## Consequences

**Dev and staging can start from a fresh volume again.** Both were verified on
genuinely empty volumes: 0 tables before Alembic, then `0001`→`0023`, 55 tables,
exit 0. The Compose-bootstrapped `missions` is now byte-for-byte the `0001`
shape — `VARCHAR(32)`, both timestamps `NOT NULL`, `ck_missions_status`,
ascending index — so **all six historical discrepancies are gone**.

**No existing data is at risk.** `/docker-entrypoint-initdb.d` runs only on the
first initialisation of a fresh volume, so unmounting changes only future
initialisations. A database already at head was fingerprinted before and after:
identical md5, revision unchanged, nothing re-created.

**Migration history is untouched**, verified by `git diff --quiet` over
`backend/database/migrations/`. No revision invented, no baseline created.

**Governance is unchanged.** All seven prior harnesses re-run at their full
historical counts: 10.7 155/155, 10.8 118/118, 10.9 107/107, 10.10 107/107,
10.11 68/68, 10.13 60/60, 10.14 52/52. Architecture gate 155 passed. 0 provider
writes.

**One state this phase prevents but cannot repair:** a database already stamped
`'0008'` by the old entrypoint stays broken, and there is no honest revision to
re-stamp it at. None exists on this machine.

**`alembic check` is still blocked**, by design, by the absent `missions` ORM
model. That is Phase 10.16's job and is reported as a failure, not a pass.

## What the verification cost, and what it caught

Five defects, all in my own verification rather than the change — the pattern
every phase in this family has produced.

The two worth recording:

**A silently smaller total is not a pass.** The 10.14 harness reported
**47/47 VERIFIED** where its history is 52/52. Comparing check-by-check showed
section C had *deferred itself* — I had exported `CORTEX_DURABLE_URL` with a
`+psycopg2` scheme, and the harness derives its migration DSN from it, so
`env.py` could not build an async engine. Re-run with a plain scheme: 52/52 with
section C intact. `47/47` and `52/52` are both "VERIFIED"; only the count
distinguishes a full run from a degraded one.

**The baseline comparison caught a CRLF corruption I introduced.** To prove the
regression's 75 failures were pre-existing, the tree was reverted with
`git stash` and the identical command re-run — the counts came back
byte-identical, which settles it. But with `core.autocrlf=true` and no
`.gitattributes`, the stash/pop round-trip rewrote `backend/entrypoint.sh` to
**CRLF**. A `#!/bin/sh` script with CRLF fails in a Linux container, and both the
Docker build context and the dev bind-mount use the working-tree file. It was
caught only because a byte-copy had been taken before stashing and was diffed
after. Restored to LF and re-verified.

A separate, honest finding: Phases 10.13 and 10.14 reported *"2852 passed"* for
the full backend regression, but `pytest tests/` — matching `testpaths` in
`pyproject.toml` — collects **6968** tests. The earlier figure came from a
narrower invocation that could not be reconstructed, and the 75 pre-existing
failures it exposes were outside the scope those reports covered.

## Next

Phase 10.16 resumes: add the `missions` ORM model copied from `0001`, already
fully specified in `docs/PHASE_10_16_IMPLEMENTATION_MAP.md` §6. Its
`alembic check` verification is now meaningful, because there is no longer a
competing authority for the model to be wrong about.
