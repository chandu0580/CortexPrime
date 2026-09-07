# Phase 10.16 — Restore the missing `missions` ORM mapping
## Implementation Map

**Written before any code, as this phase family requires.**

**First attempt: STOPPED at implementation rule 5** — migration `0001` and
`infra/postgres/init.sql` defined different `missions` tables and `init.sql` was
still mounted, so no model could be correct for both (ADR-108). Sections 3-5
below record that stop and remain as written.

**Resumed after Phase 10.18** (`1e0f29a`, ADR-110) removed the competing
authority: `init.sql` is unmounted, Alembic owns the application schema, and a
Compose-bootstrapped database now produces the `0001` shape. The model in §6 was
then implemented as specified, with the one correction noted there.

- **Parents:** `df4f046` (10.15 discovery) → `183a34c` (10.17) → `1e0f29a` (10.18)
- **Status:** §6 **implemented**; see `docs/PHASE_10_16_VERIFICATION_REPORT.md`
- **Migrations added:** none
- **Schema changed:** no

---

## 1. What this phase was going to do

Add exactly one SQLAlchemy ORM model mapping the existing `missions` table, so
that `Base.metadata` becomes closed under its own foreign keys and
`sorted_tables` can succeed — restoring `create_all`, `alembic check` and
`alembic revision --autogenerate`.

Planned change set, in full:

| File | Change |
|---|---|
| `backend/database/models/mission.py` | **new** — one model, `MissionRecord`, `__tablename__ = "missions"`, copied column for column from migration `0001` |
| `backend/database/models/__init__.py` | one import + one `__all__` entry, using the existing eager-import registration mechanism |

Nothing else. No migration, no repository, no routes, no change to
`reflection_history`, `runtime_analytics`, `missions_bc`, Mission Runtime, or
anything on the governed path.

## 2. Registration mechanism to be used

`backend/database/models/__init__.py` already imports eleven models eagerly at
package import (lines 1-12); that is what puts `reflection_history` and
`runtime_analytics` on `Base.metadata`. `missions` would join by the same
mechanism.

**Not** `_ensure_bc_models()` — that is the lazy path for bounded-context
models, and using it would leave `missions` unregistered for every consumer
that imports `backend.database.models` without calling it, which is the
majority. The two tables that reference `missions` are registered eagerly, so
their referent must be too.

Rule 12 is satisfied: **no repository is required.** Registration is by import
of the model module; `BaseRepository` plays no part in metadata registration.

## 3. Rule 1 — the exact DDL in migration `0001` [VERIFIED]

`backend/database/migrations/versions/0001_initial_schema.py:31-49`

| Column | Type | Null | Server default |
|---|---|---|---|
| `id` | `sa.UUID(as_uuid=True)` PK | no | `gen_random_uuid()` |
| `title` | `sa.Text` | no | — |
| `objective` | `sa.Text` | no | — |
| `status` | `sa.String(32)` | no | `pending` |
| `priority` | `sa.Integer` | yes | `5` |
| `result` | `sa.Text` | yes | — |
| `metadata` | `JSONB` | yes | `{}` |
| `started_at` | `TIMESTAMP(timezone=True)` | yes | — |
| `completed_at` | `TIMESTAMP(timezone=True)` | yes | — |
| `created_at` | `TIMESTAMP(timezone=True)` | **no** | `NOW()` |
| `updated_at` | `TIMESTAMP(timezone=True)` | **no** | `NOW()` |

Constraint: `CheckConstraint("status IN ('pending','active','completed','failed','cancelled')", name="ck_missions_status")`
Index: `idx_missions_status` on `(status, created_at)`

## 4. Rule 2 — the exact definition in `infra/postgres/init.sql` [VERIFIED]

`infra/postgres/init.sql:79-98`

| Column | Type | Null | Default |
|---|---|---|---|
| `id` | `UUID` PK | no | `uuid_generate_v4()` |
| `title` | `TEXT` | no | — |
| `objective` | `TEXT` | no | — |
| `status` | `TEXT` | no | `'pending'` |
| `priority` | `INT` | yes | `5` |
| `result` | `TEXT` | yes | — |
| `metadata` | `JSONB` | yes | `'{}'` |
| `started_at` | `TIMESTAMPTZ` | yes | — |
| `completed_at` | `TIMESTAMPTZ` | yes | — |
| `created_at` | `TIMESTAMPTZ` | **yes** | `NOW()` |
| `updated_at` | `TIMESTAMPTZ` | **yes** | `NOW()` |

Constraint: `CONSTRAINT missions_status_check CHECK (...)`
Index: `idx_missions_status` on `(status, created_at DESC)`

## 5. Rule 3 — the comparison, and the stop

**They disagree in six ways.** See
`docs/PHASE_10_16_VERIFICATION_REPORT.md` §2 for the evidence and §4 for the
proof that both shapes are really produced by this project's own tooling.

Rule 5 is unambiguous:

> *If migration 0001 and init.sql disagree: STOP. Do not choose one silently.
> Report the discrepancy.*

and stop condition 1 repeats it. **The first attempt stopped here.** No model
file was created then. Phase 10.18 removed the disagreement by unmounting
`init.sql`, after which `0001` is the only authority and §6 became
unambiguous.

## 6. The model that is ready to be written, once the discrepancy is decided

Recorded so the decision phase inherits it rather than re-deriving it. This
reproduces migration `0001`, which is what every *migratable* database actually
contains. **It is now written to disk** as
`backend/database/models/mission.py`, with the correction noted at the end of
this section.

```python
class MissionRecord(Base):
    """Maps the existing `missions` table. Copied from migration 0001."""

    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True,
        server_default=sa.text("gen_random_uuid()"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="pending")
    priority: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, server_default="5")
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, server_default="{}")
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','completed','failed','cancelled')",
            name="ck_missions_status"),
        Index("idx_missions_status", "status", "created_at"),
    )
```

Two deliberate choices worth recording:

- **It does not use `UUIDPrimaryKeyMixin` or `TimestampMixin.`** Both sibling
  models use them, and it would be the natural-looking thing to do — but the
  mixins impose their own column definitions, and this table's `id` default and
  timestamp nullability must come from `0001`, not from a convention. Rule 7
  forbids reinterpreting fields, and a mixin is a reinterpretation.
- **`metadata` is mapped as the attribute `meta`**, exactly as
  `reflection_history` does, because `metadata` is reserved on a declarative
  class. Proven, not assumed: declaring the attribute raises
  `InvalidRequestError: Attribute name 'metadata' is reserved when using the
  Declarative API`, while `mapped_column("metadata", ...)` yields a column
  genuinely named `metadata`.

**Corrected during Phase 10.16 implementation.** This section originally wrote
the primary key as `sa.Uuid()`. Migration `0001` uses `sa.UUID(as_uuid=True)`,
and this model must represent `0001` exactly, so the shipped model uses the
latter. Both render as `UUID` on PostgreSQL — the correction is about
fidelity to the source of truth, not about behaviour. The shipped class also
carries a note about the unrelated `MissionRecord` dataclass in
`backend/services/enterprise_executive_runtime.py:90`, which shares the name
and nothing else.

## 7. What was verified before the stop

| Rule | Status |
|---|---|
| 1 — exact DDL in `0001` | [VERIFIED] §3 |
| 2 — exact definition in `init.sql` | [VERIFIED] §4 |
| 3 — compare both | [VERIFIED] — they disagree |
| 4 — reflect a real migrated database | [VERIFIED] — report §3 |
| 5 — stop if they disagree | **FIRED** |
| 6-12 — define, register, restrict | **NOT REACHED** |

Mandatory verification A–I was **not run**, because there is no change to
verify. The report is explicit about which sections were executed as *stop
evidence* and which were never reached.
