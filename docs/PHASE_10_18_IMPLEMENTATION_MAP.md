# Phase 10.18 — Implement Schema Ownership
## Implementation Map

**Written before any code, as this phase family requires.**

- **Parent:** `183a34c` — Phase 10.17 discovery (ADR-109, STATUS=GO)
- **Decision implemented:** Alembic is the canonical application-schema owner;
  `missions` is owned by migration `0001`; `init.sql` no longer owns application
  tables.
- **ADR for this phase:** ADR-110 (107 is used twice — Phases 10.14 and 10.15;
  108 is Phase 10.16; 109 is Phase 10.17)

---

## 1. A correction to Phase 10.17, established before writing anything

Phase 10.17 reported that the entrypoint pre-stamp is *"gated on `DATABASE_URL`,
which no compose file sets — but `ADMINISTRATOR_GUIDE.md:265` tells operators to
set it,"* and concluded an operator following the guide **arms** it.

**That is not sufficient, and this phase proves it.** There is a second gate:

```
$ docker run --rm python:3.11-slim sh -c 'command -v psql ...'
psql ABSENT in base
$ ... after installing libpq-dev ...
psql ABSENT after libpq-dev
```

`backend/Dockerfile` installs **`libpq-dev`** — the client *library* for
`asyncpg`/`psycopg2` — and **not `postgresql-client`**, which is the package that
provides the `psql` binary. Every `psql` invocation in `entrypoint.sh` is
suffixed `|| true` or `2>/dev/null || true`, so in a container they all fail
silently.

**Consequence:** the `'0008'` pre-stamp is **unreachable from any container
image this repository builds**, even with `DATABASE_URL` set. It is reachable
only if `entrypoint.sh` is executed outside the image on a host that has `psql`,
which is not a supported deployment path.

This makes the removal **zero-risk** rather than urgent — but it does **not**
make it optional. Adding `postgresql-client` to the image is an ordinary,
plausible operational change (for `pg_dump`, for debugging), and it would arm the
defect instantly and silently. The trap is removed while it is provably inert.

**A second consequence, reported not repaired:** the advisory migration lock
(`pg_advisory_lock(2024071801)`) uses the same absent `psql`, so it has **never
been acquired in a container**. Multi-replica deployments race on
`alembic upgrade head` with no serialisation. That is outside this brief's
objectives — see §7.

---

## 2. Changes to be made

| File | Change | Objective |
|---|---|---|
| `backend/entrypoint.sh` | delete the pre-stamp block; add an **explicit, opt-in** `ALEMBIC_STAMP_REVISION` path that uses `alembic stamp` | 1, 2, 3, 4 |
| `docker-compose.yml` | remove the `init.sql` mount; leave a comment recording why | 6 |
| `docker-compose.staging.yml` | same | 6 |

**Not touched:** `infra/postgres/init.sql` (objective 7 — retained, not deleted,
and not edited), migration `0001` (objective 8), the `missions` schema
(objective 9), the ORM (objective 10), `event_subscriber.py` (objective 11),
`init_db()` (objective 12), `docker-compose.prod.yml` and
`docker-compose.airgap.yml` (they never mounted `init.sql`), and the advisory
lock block (§7).

### 2.1 The entrypoint

**Removed** — the block that made an empty version table mean "stamp `'0008'`":

```sql
CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, ...);
INSERT INTO alembic_version (version_num)
SELECT '0008' WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
```

**Replacement behaviour — by removal, not by a new inference.** With the block
gone, every state resolves through Alembic's own semantics:

| Database state | What happens | Why it is correct |
|---|---|---|
| empty, no `alembic_version` | Alembic runs `0001`→`0023` | the genuinely fresh case |
| `alembic_version` present and empty | identical to "no table" for Alembic — runs from base | an empty version table carries **no information**; it is not evidence of a restore |
| `alembic_version` holds a valid revision | normal upgrade from there | unchanged |
| `alembic_version` holds an **invalid** revision | Alembic errors: *Can't locate revision* | **fails closed, explicit** |
| application tables exist, no `alembic_version` | `0001` hits `CREATE TABLE missions` → `DuplicateTableError` | **fails closed, explicit** — and after §2.2 this state can no longer be produced by Compose |

**No revision is ever chosen by inference.** Objectives 3 and 4 are satisfied by
*not deciding*, which is also what verification D demands: the ambiguous state
produces a loud, explicit failure rather than a silent guess.

**Recovery path (verification E), explicit and opt-in:**

```sh
if [ -n "${ALEMBIC_STAMP_REVISION:-}" ]; then
    alembic -c "$ALEMBIC_INI" stamp "$ALEMBIC_STAMP_REVISION"
fi
```

- The discriminator is **an operator setting a variable naming a revision** —
  never an inference from database state.
- It uses `alembic stamp`, so Alembic validates the revision id itself; an
  unknown one is refused rather than written.
- It uses `alembic`, which **is** in the image, unlike `psql`.
- Unset (the default, and every current deployment) ⇒ nothing happens.

This keeps the legitimate "restored from a pre-Alembic backup" capability the old
comment claimed, while removing the guessing that made it dangerous.

### 2.2 The two Compose files

Remove one line from each:

```
- ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01_init.sql:ro
```

`docker-compose.yml:251` and `docker-compose.staging.yml:185`. A comment replaces
it so the removal is not silently reverted.

**`./infra/postgres/postgresql.conf` stays mounted** in both — it is a separate
file, and each service's `command:` names it as `config_file`. Removing it would
break Postgres start-up. Only the `init.sql` mount goes.

---

## 3. Objective 6's precondition — proof that `init.sql` contributes nothing required

The brief permits removing the mount **only after** proving `init.sql`
contributes no required infrastructure, extension, role, schema, function, seed
or operational behaviour. Phase 10.17 established this; the load-bearing points,
with evidence:

| Category | Required from `init.sql`? | Evidence |
|---|---|---|
| Extensions (`vector`, `uuid-ossp`, `pg_trgm`) | **No** | migration `0001:24-26` creates all three with `IF NOT EXISTS`; the image is `pgvector/pgvector:pg16`, so `vector` is available |
| Roles / users | **No** | file contains no `CREATE ROLE`/`CREATE USER`; the role comes from `POSTGRES_USER` |
| Schemas | **No** | no `CREATE SCHEMA`; only `public` |
| Functions | **No** | `set_updated_at()` is created by `0001:89` |
| Seed data | **No** | no `INSERT` anywhere in the file |
| Application tables | **No** | 6 of 8 duplicate `0001` **in a different shape**; `cognition_events` and `agent_sessions` have **no consumer in any Python** |
| Triggers | **No** | 2 duplicate `0001`/`0002`; the 4 exclusive ones cover tables **no code ever `UPDATE`s**, and `TimestampMixin` maintains `updated_at` via `onupdate` |
| GRANTs | **No** | grantee `cortex` is `POSTGRES_USER`, i.e. the owner; they run before Alembic creates anything |
| **Operational config** | **Yes — but not from `init.sql`** | `postgresql.conf`, a **different file**, stays mounted |

Verification F re-checks this as an explicit KEEP/MOVE/DELETE-LATER inventory.

---

## 4. Why `init.sql` is retained rather than deleted

Objective 7 permits deletion only if the repository proves no remaining
legitimate purpose. Two reasons not to, in this phase:

1. `.github/workflows/test.yml:248` starts `cortex-postgres` from
   `docker-compose.yml`. Unmounting changes what that job produces; deleting the
   file as well would conflate two changes in one phase.
2. The file is the only written record of `cognition_events` and
   `agent_sessions`. They have no consumer today, but deleting their sole
   definition in the same phase that removes the mount would destroy evidence
   while the ownership change is still being proven.

It becomes **DELETE-LATER**, once this phase's change has been exercised.

---

## 5. Verification plan (A–J)

| § | Method |
|---|---|
| A | Bring up **only** `cortex-postgres` from `docker-compose.yml` in an isolated project with a **fresh volume**; assert no `missions`, no `alembic_version`, no application tables; then `alembic upgrade head`; assert head and that `missions` matches `0001` column for column |
| B | Repeat with `docker-compose.staging.yml`; assert no failure is swallowed |
| C | Against a database already at `0023_retire_iam`: capture the full schema, run `alembic upgrade head`, assert revision unchanged and schema byte-identical |
| D | Create the dangerous state deliberately — `alembic_version` present but empty, and separately holding an invalid revision — and record exactly what the corrected path does |
| E | Prove the `ALEMBIC_STAMP_REVISION` path against a disposable database, including that an unknown revision is refused |
| F | KEEP / MOVE / DELETE-LATER inventory of every `init.sql` object |
| G | Assert neither Compose file can now produce `DuplicateTableError` |
| H | `alembic upgrade head`, `alembic current`, `alembic heads`. **`alembic check` is expected to remain blocked** by the still-absent `missions` ORM model and will be reported as such, not as a pass |
| I | architecture gate, full backend regression, and the 10.7/10.8/10.9/10.10/10.11/10.13/10.14 harnesses |
| J | no data deleted, no migration file changed, no revision changed, no new table, 0 provider writes, governance unchanged |

Ports and project names are isolated (`-p`, `POSTGRES_PORT`) so nothing touches
the running phase infrastructure on `cortex-p99b-pg`.

---

## 6. Stop conditions to watch

Conditions 1, 2 and 7 are the ones this change is designed to clear; 3 is
answered by §2.1 (the entrypoint no longer needs to distinguish — it stops
guessing); 4, 5, 6 and 8 are structurally impossible here (no migration is
written, no revision invented, no `DROP` added, nothing on the governed path is
touched). 9 and 10 are what verification I and this map exist to catch.

---

## 7. Known adjacent defect, reported and NOT repaired

The advisory migration lock in `entrypoint.sh` calls `psql`, which is absent from
the image (§1), so it has **never been acquired**. Multi-replica deployments run
`alembic upgrade head` concurrently with no serialisation.

Repairing it means either adding `postgresql-client` to the image — which would
**arm** the very defect this phase removes, if done in the same change — or
moving migrations into a dedicated Job/initContainer, which ADR-109 already
deferred as its own decision. It is outside objectives 1–12 and is reported.
