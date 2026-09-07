# Phase 10.18 — Implement Schema Ownership
## Verification Report

**STATUS: COMPLETE.** All stop conditions clear.

Every claim below was produced by running something. Where a check was not run,
or was run and degraded, it says so.

---

## 1. Section results

| § | Verification | Result |
|---|---|---|
| A | Fresh Compose database | **VERIFIED** |
| B | Staging Compose database | **VERIFIED** |
| C | Pre-existing Alembic database at head | **VERIFIED** |
| D | Empty / invalid `alembic_version` | **VERIFIED** — fails closed in both ambiguous states |
| E | Recovery behaviour | **VERIFIED** — explicit operator signal only |
| F | `init.sql` residual responsibility | **VERIFIED** — nothing KEEP, nothing MOVE |
| G | Compose no longer collides | **VERIFIED** |
| H | Migration commands | **VERIFIED**; `alembic check` **still blocked**, reported honestly |
| I | Regression, architecture, 7 harnesses | **VERIFIED** — pre-existing failures proven pre-existing |
| J | Database safety | **VERIFIED** |

**Changed files: 3.** `backend/entrypoint.sh`, `docker-compose.yml`,
`docker-compose.staging.yml`. No migration, no ORM, no schema, no test.

---

## 2. A correction to Phase 10.17 [VERIFIED]

Phase 10.17 concluded that an operator following `ADMINISTRATOR_GUIDE.md:265`
and setting `DATABASE_URL` **arms** the `'0008'` pre-stamp. **That was not the
whole picture, and this phase corrects it.**

```
$ docker run --rm python:3.11-slim sh -c 'command -v psql ...'
psql ABSENT in base
$ ... after apt-get install libpq-dev ...
psql ABSENT after libpq-dev
```

`backend/Dockerfile` installs **`libpq-dev`** (the client *library* for
asyncpg/psycopg2), **not `postgresql-client`** (which provides the `psql`
binary). Every `psql` call in `entrypoint.sh` is `|| true`, so in a container
they all fail silently.

**The pre-stamp was therefore unreachable from any image this repository
builds**, even with `DATABASE_URL` set. Removal is **zero-risk**, not urgent.

It remains correct to remove: adding `postgresql-client` for `pg_dump` or
debugging is an ordinary operational change and would arm the defect instantly
and silently. **The trap is removed while provably inert.**

**Adjacent consequence, reported not repaired:** the advisory migration lock
(`pg_advisory_lock(2024071801)`) uses the same absent `psql`, so it has **never
been acquired in a container**. Multi-replica deployments race on
`alembic upgrade head` unserialised. Repairing it means either adding
`postgresql-client` — which would arm the very defect this phase removes if done
in the same change — or moving migrations to a dedicated Job, which ADR-109
already deferred. Outside objectives 1–12.

---

## 3. § A — Fresh Compose database [VERIFIED]

Isolated project `p1018dev`, **fresh volume**, `docker-compose.yml`,
`cortex-postgres` only.

**Before Alembic:**

```
tables_in_public=0
missions_present=0
alembic_version_present=0
extensions=plpgsql
```

`init.sql` did not run — the mount is gone. Not even the three extensions were
pre-created, confirming nothing from that file executed.

**`alembic upgrade head`:** completed, `0001` → `0023_retire_iam`.
`alembic current` = `0023_retire_iam (head)`; `alembic heads` = same, single head.

**`missions` on the Compose-bootstrapped database:**

```
 id           uuid                     NO   gen_random_uuid()
 status       character varying   32   NO   'pending'::character varying
 created_at   timestamp with time zone NO   now()
 updated_at   timestamp with time zone NO   now()
constraints = ck_missions_status, missions_pkey
index       = btree (status, created_at)          -- ascending
total_tables = 55
```

**All six historical discrepancies now resolve to migration `0001`**, and the
table count matches the reference Alembic-built databases exactly.

---

## 4. § B — Staging Compose database [VERIFIED]

Isolated project `p1018stg`, fresh volume, `docker-compose.staging.yml`.

Before Alembic: `tables_in_public=0`, `missions_present=0`,
`alembic_version_present=0`.

```
ALEMBIC EXIT CODE: 0      # pipefail set; no failure swallowed
revision=0023_retire_iam
total_tables=55
missions_status=character varying(32) null=NO
created_at_null=NO
```

Exit status was captured explicitly with `pipefail` precisely so a failure could
not be hidden by a pipeline.

---

## 5. § C — Pre-existing database already at head [VERIFIED]

Target: `cortex_p1014_fresh`, at `0023_retire_iam`. A fingerprint was taken
before and after — full table list, plus an md5 over every
`table.column:type:nullable:default` in `public`, plus the revision.

```
BEFORE  md5 = e1d7ece2cadebb43e690ada90bbb5ed8
AFTER   md5 = e1d7ece2cadebb43e690ada90bbb5ed8
diff    -> IDENTICAL
```

No migration ran, no downgrade, no re-creation, no schema mutation, revision
unchanged.

---

## 6. § D — the dangerous states, constructed deliberately [VERIFIED]

| Case | Setup | Result |
|---|---|---|
| **D1** | `alembic_version` **exists but is empty**, database otherwise empty | **23 migrations ran**, `revision=0023_retire_iam`, `tables=55` |
| **D2** | `alembic_version` holds `'0008'` | **EXIT 1** — `UndefinedObjectError: index "idx_connector_activity_status" does not exist`; database left at 1 table |
| **D3** | 8 application tables present, **no** `alembic_version` (the old `init.sql` state) | **EXIT 1** — `DuplicateTableError: relation "missions" already exists` |

**D1 is the case the old code broke.** That exact state used to be stamped
`'0008'`, causing `0001`–`0008` to be skipped. It now builds the full schema
correctly, because nothing guesses any more.

**D2 and D3 fail closed**, non-zero exit, no silent revision chosen. Under
staging/prod (`BLOCK_ON_MIGRATION_FAILURE=true`) start-up aborts; under dev it
continues past the entrypoint but `main.py` then raises because `_migration_ok`
is false.

**Honest note on D2's diagnostic.** It fails closed and exits non-zero, but the
message names the *failing DDL statement*, not the root cause ("your recorded
revision does not describe this database"). It is explicit that something failed
and where, not why. **D2 is also the residue of the old bug: a database already
stamped `'0008'` by the previous entrypoint stays broken.** This phase prevents
new occurrences; it does not repair existing ones. No such database exists on
this machine (§11).

---

## 7. § E — recovery behaviour [VERIFIED]

The automatic stamp is gone. Recovery is now an explicit operator signal,
`ALEMBIC_STAMP_REVISION`, executed through `alembic stamp`.

| Test | Result |
|---|---|
| `alembic stamp 0008_add_connector_status` on a fresh DB | recorded `0008_add_connector_status`; **`alembic_version.version_num` created as `VARCHAR(128)`** |
| `alembic stamp 0008` (bare prefix) | accepted, and **wrote the full canonical id** `0008_add_connector_status` |
| `alembic stamp not_a_revision` | **refused**, non-zero exit, `Can't locate revision identified by 'not_a_revision'` |

Three improvements over the removed code, each measured:

1. **The discriminator is an operator naming a revision**, never an inference
   from database state. Unset — every current deployment — means nothing runs.
2. **Alembic validates the revision.** The old code wrote the literal `'0008'`,
   an id that does not exist in the lineage. `alembic stamp` resolves a prefix
   to the **full canonical id** and refuses an unknown one.
3. **The `VARCHAR(32)` defect is gone with the hand-rolled `CREATE TABLE`.**
   Alembic creates the column at 128, wide enough for the real 35-character
   revision ids.

---

## 8. § F — `init.sql` residual responsibility inventory [VERIFIED]

| Object | Classification | Reason |
|---|---|---|
| `CREATE EXTENSION vector` / `"uuid-ossp"` / `pg_trgm` | **DELETE-LATER** | `0001:24-26` creates all three `IF NOT EXISTS`; §3 shows only `plpgsql` present before Alembic and the migration then succeeded |
| `episodic_memory`, `semantic_memory`, `missions`, `reflection_history`, `runtime_analytics`, `embedding_cache` | **DELETE-LATER** | duplicated by `0001` in a *different* shape |
| `cognition_events`, `agent_sessions` | **DELETE-LATER** | no consumer in any Python; no ORM model |
| `set_updated_at()` | **DELETE-LATER** | created by `0001:89` |
| `trg_episodic_updated_at`, `trg_semantic_updated_at` | **DELETE-LATER** | created by `0001` |
| 4 exclusive triggers (`missions`, `reflection_history`, `runtime_analytics`, `embedding_cache`) | **DELETE-LATER** | no code `UPDATE`s those tables; `TimestampMixin` maintains `updated_at` via `onupdate` |
| 3 `GRANT`s to `cortex` | **DELETE-LATER** | grantee is the database owner |
| **`infra/postgres/postgresql.conf`** | **KEEP** | a **different file**, still mounted in both compose files; each `command:` names it as `config_file`. Untouched |

**Nothing is KEEP. Nothing needs to MOVE.** The file itself is **DELETE-LATER**,
retained per objective 7 — `.github/workflows/test.yml:248` still starts
`cortex-postgres` from `docker-compose.yml`, and the file is the only written
record of `cognition_events`/`agent_sessions`. Deleting it in the same phase that
unmounts it would conflate two changes.

**No executable reference to `init.sql` remains** — every surviving mention is a
comment in `0001`, `0003`, two model files, the two compose files, and phase
docs.

---

## 9. § G — Compose can no longer collide [VERIFIED]

- Neither compose file mounts `init.sql`; both parse (`docker compose config`).
- Both fresh volumes produced **0 tables** before Alembic (§3, §4).
- Both then reached head with **exit 0** and 55 tables.
- `DuplicateTableError` is now reproducible **only** by deliberately replaying
  `init.sql` by hand (§6 D3) — it can no longer arise from either compose file.

Schema-vs-migration divergence is gone: the Compose-bootstrapped `missions` is
now byte-for-byte the `0001` shape (§3).

---

## 10. § H — migration commands [VERIFIED, with one honest failure]

| Command | Result |
|---|---|
| `alembic upgrade head` | completes from base on a fresh Compose DB |
| `alembic current` | `0023_retire_iam (head)` |
| `alembic heads` | `0023_retire_iam (head)` — single head |
| **`alembic check`** | **EXIT 1 — still blocked**: `NoReferencedTableError: Foreign key associated with column 'reflection_history.mission_id' could not find table 'missions'` |

`alembic check` remaining blocked is **expected and correct**: the `missions` ORM
model is intentionally still absent (objective 10). It is **not** a pass and is
not counted as one. `autogenerate` was not run as a success criterion, per the
brief. Phase 10.16 closes this.

---

## 11. § I — regression [VERIFIED]

| Gate | Result |
|---|---|
| `tests/architecture` | **155 passed** |
| Phase 10.7 harness | **155/155 VERIFIED** |
| Phase 10.8 harness | **118/118 VERIFIED** |
| Phase 10.9 harness | **107/107 VERIFIED** |
| Phase 10.10 harness | **107/107 VERIFIED** |
| Phase 10.11 harness | **68/68 VERIFIED** |
| Phase 10.13 harness | **60/60 VERIFIED** |
| Phase 10.14 harness | **52/52 VERIFIED** |
| Full backend regression | 75 failed, 6775 passed, 36 skipped, 58 xfailed, **24 errors** |

### 11.1 The regression failures are pre-existing — proven, not asserted

The brief says any failure must be investigated, not deleted. `pytest tests/`
reported 75 failures and 24 errors. Rather than argue that three non-Python
files cannot break Python tests, the tree was **reverted and the identical
command re-run**:

```
with Phase 10.18 changes : 75 failed, 6775 passed, 36 skipped, 58 xfailed, 24 errors
reverted (git stash)     : 75 failed, 6775 passed, 36 skipped, 58 xfailed, 24 errors
```

**Byte-identical.** None of it is attributable to this phase.

Where they live: **57** in loose `tests/*.py` (V1 legacy), **17** in
`tests/benchmarks/`, **1** in `tests/platform/test_dependency_isolation.py`.
`tests/architecture` is clean at 155/155.

### 11.2 A reporting-scope discrepancy in earlier phases [VERIFIED]

Phases 10.13 and 10.14 recorded *"2852 passed"* for the full backend regression.
`pytest tests/` — which matches `testpaths = ["tests"]` in `pyproject.toml` —
**collects 6968 tests** (6905 under the repo venv). Neither interpreter
reproduces 2852.

So the earlier "full backend regression" figure was produced by a **narrower
invocation whose exact form could not be reconstructed**. This phase reports the
broader number, and the 75 pre-existing failures it exposes were **outside the
scope those earlier reports covered**. That is a reporting-scope finding about
prior phases, not a regression here — and it is recorded rather than smoothed
over.

---

## 12. § J — database safety [VERIFIED]

| Requirement | Evidence |
|---|---|
| No existing application data deleted | Nothing added a `DROP`. `/docker-entrypoint-initdb.d` runs only on a **fresh volume**, so unmounting changes only future initialisations. §5 shows an at-head database byte-identical after |
| No migration history rewritten | `git diff --quiet -- backend/database/migrations/` → **no changes** |
| No migration revision changed | same; `alembic heads` still the single `0023_retire_iam` |
| No new table introduced | fresh Compose DB = **55 tables**, identical to the reference Alembic-built databases |
| No provider writes | **0.** No harness in §11 reported a non-zero `provider_writes`; this phase touches no execution path |
| Governance behaviour unchanged | 10.7/10.8/10.9/10.10/10.11/10.13/10.14 all VERIFIED at their full historical counts; `DURABLE_METADATA` untouched |
| `infra/postgres/init.sql` unmodified | `git diff --quiet -- infra/postgres/init.sql` → **no changes** |

---

## 13. Stop conditions

| # | Condition | Result |
|---|---|---|
| 1 | Fresh Compose still creates application tables before Alembic | **No** — 0 tables (§3, §4) |
| 2 | Alembic still collides with pre-created tables | **No** — §9 |
| 3 | Entrypoint cannot distinguish recovery from fresh initialisation | **Cleared by not needing to.** It no longer classifies; it stops guessing, and recovery is an explicit operator signal (§7) |
| 4 | Requires rewriting migration history | **No** — §12 |
| 5 | Requires inventing a baseline revision | **No** — none invented; `alembic stamp` only accepts real revisions (§7) |
| 6 | Existing production data could be altered or deleted | **No** — §12 |
| 7 | `init.sql` has a required production responsibility not relocated | **No** — §8; nothing KEEP, nothing MOVE |
| 8 | Governance/authority behaviour changes | **No** — §12 |
| 9 | Prior phase regression | **No** — all seven harnesses at full historical counts; regression identical to baseline (§11.1) |
| 10 | Correct behaviour depends on an undocumented assumption | **No** — the removed code depended on one ("an empty version table means restored"); the replacement depends on Alembic's documented semantics and an explicit variable |

**None fired.**

---

## 14. Defects in my own verification, found and fixed

Consistent with every phase in this family, the errors were in the verification,
not the change.

1. **Four harness filenames were wrong** in my runner
   (`phase108_governed_grant_harness.py` etc.). The runner printed
   `SCRIPT NOT FOUND` rather than skipping silently — which is why it was caught
   in one pass instead of being reported as a pass.
2. **A vacuous `fails=0`.** The first harness chain reported `fails=0` with
   **empty** pass/total counts. Inspecting the output showed
   `HTTPError: HTTP Error 401` — the k3d ServiceAccount token had expired at
   17:56. Tokens were re-minted (6h) and the chain re-run. A `fails=0` with no
   totals is not a pass.
3. **The 10.11 harness needs `CORTEX_P1011_SCRATCH`**, which I had not set; it
   raised `KeyError` and produced no counts. Set, re-run, 68/68.
4. **The 10.14 harness reported 47/47 instead of its historical 52/52.**
   Comparing check-by-check against the original run showed **all of section C
   missing** — it had **deferred itself**: *"alembic could not be driven
   programmatically in this environment"*. Cause: I exported
   `CORTEX_DURABLE_URL` with a `+psycopg2` scheme, and `_recreate` derives the
   migration DSN from it, so `env.py` could not build an async engine. Re-run
   with a plain `postgresql://` scheme: **52/52 with section C intact.** A
   silently smaller total is a degraded result, not a pass.
5. **The stash/pop round-trip rewrote `backend/entrypoint.sh` to CRLF.** With
   `core.autocrlf=true` and no `.gitattributes`, restoring the baseline
   comparison converted 123 lines to CRLF. **A `#!/bin/sh` script with CRLF
   fails in a Linux container** ("bad interpreter"), and both the Docker build
   context and the dev bind-mount use the working-tree file. Caught by diffing
   against a byte-copy taken before stashing; restored to LF-only and
   re-verified with `file` and `sh -n`. HEAD's committed copy was, and remains,
   LF.

---

## 15. Known limitations

1. **No full Compose stack was started.** Verification A and B brought up
   `cortex-postgres` only, on genuinely fresh volumes, and drove Alembic against
   it directly — which is the step that was broken. The backend container,
   `entrypoint.sh` executing *inside* an image, and the multi-service
   orchestration were **not** exercised.
2. **`entrypoint.sh` was not executed.** It was syntax-checked (`sh -n`) and its
   behaviour verified by running the same `alembic` commands it runs, in the
   same order, against real databases. The script itself running as PID 1 in a
   container was not observed.
3. **The `ALEMBIC_STAMP_REVISION` path was verified at the `alembic stamp`
   level**, not through the entrypoint.
4. **No production or staging deployment was inspected** — none is available.
   Production and air-gapped compose never mounted `init.sql`, so they are
   unaffected by construction, but that rests on reading their configuration.
5. **A database already stamped `'0008'` by the old entrypoint remains broken**
   (§6). This phase prevents the state; it does not repair it. None exists here.
6. **The advisory migration lock is still a no-op** (§2), reported not repaired.
7. **`alembic check` is still blocked** (§10) — by design, until Phase 10.16.
8. **The regression's 75 failures and 24 errors are pre-existing and unfixed.**
   Proven not mine (§11.1); triaging them is not this phase's scope.
