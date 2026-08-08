# Storage Boundary

`backend/platform/storage/` — the point where tenant identity becomes a query
predicate. See [ADR-018](../adr/ADR-018-storage-boundary-tenant-guard.md).

## What it is for

Constitution **I6**: *every tenant-scoped read and write carries tenant identity
to the storage layer.* ADR-017 made the identity travel; this makes storage
refuse to act without it.

Three rules the guard exists to make unbreakable:

| Rule | Enforced by |
|---|---|
| A storage operation without an `ExecutionContext` is refused, not defaulted | `MissingExecutionContext` |
| Tenant identity is derived from the context, never accepted as a parameter | no tenant parameter exists on the API |
| Platform-internal access is opt-in per record type | `StorageBinding.platform_internal_allowed` |

## Using it

```python
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.platform.storage import RepositoryGuard

guard = RepositoryGuard(
    StorageBinding(record_type="MissionModel", scope_column="tenant_id")
)

access = guard.authorize(StorageOperation.READ, context)   # who is asking
column, value = guard.scope_filter(access)                 # narrow the query
guard.assert_in_scope(row, access)                         # check what came back
```

`authorize` and `assert_in_scope` are separate on purpose. The first establishes
who is asking *before* any query runs; the second checks what the query actually
returned. A guard doing only the first would authorise correctly and still hand
over the wrong row.

### From SQLAlchemy

`TenantScopedRepository` wires all of this up:

```python
class MissionRepository(TenantScopedRepository[MissionModel]):
    __scope_column__ = "tenant_id"

    def __init__(self, session):
        super().__init__(MissionModel, session)

await repo.list(context)              # only this tenant's rows
await repo.get(context, pk)           # raises on another tenant's row
await repo.create(context, mission)   # stamps the tenant
```

Bespoke queries go through `_execute_scoped` so they inherit the predicate:

```python
async def by_status(self, context, status):
    result = await self._execute_scoped(
        context,
        select(MissionModel).where(MissionModel.status == status),
        StorageOperation.READ,
    )
    return list(result.scalars().all())
```

Both the missing `__scope_column__` and a column absent from the model raise at
**construction**, not on first query.

## Behaviour worth knowing

**`get` raises, `list` filters.** A pk lookup means the caller already knows the
id, so returning `None` for another tenant's row would be indistinguishable from
"no such row" and would hide the attempt. `list` answers an open-ended question,
so a narrowed answer is honest.

**A miss is not a violation.** `assert_in_scope(None, access)` passes — a query
that found nothing leaked nothing.

**An unstamped row *is* a violation.** A row whose tenant column is `NULL` is
unattributed, not ownerless. Treating it as belonging to whoever asked is how one
tenant inherits another's orphaned data.

**Writes are refused, never restamped.** Passing a record already carrying a
different tenant raises rather than overwriting — overwriting would turn an
attempted cross-tenant write into a successful same-tenant one and destroy the
evidence.

**`TenantScopedRepository` is not a `BaseRepository`.** Deliberately not
substitutable: their signatures differ, and inheritance would let
`repo.get(some_uuid)` bind a uuid to `context`.

## The architecture rule

`TENANT-REPOSITORY-CONTEXT` (`platform/architecture/tenancy_rules.py`) statically
flags repository methods that take no context, and — more severely — ones that
accept a `tenant_id` parameter.

`GRANDFATHERED_REPOSITORIES` holds the 42 repositories that predate the guard.
They warn; anything else errors and blocks the merge.

**The list may only shrink.** Adding an entry adds a known cross-tenant hazard,
and it must appear as a one-line diff to a frozenset so it cannot be waved
through. Run `stale_grandfather_entries(graph)` to find entries no live
repository still uses.

## Current state

I6 is **PARTIAL**, not ENFORCED — deliberately.

The guard is real and blocking for new code, but no model carries a tenant column
yet, so the 42 pre-existing repositories cannot adopt it. Marking the invariant
ENFORCED while a cross-tenant read is one `MissionRepository.get()` away would be
a false claim. Promotion needs the schema work in PR-11.

Also unguarded today: Redis (`infrastructure/redis/keys.py`, which still reads
the `database/tenancy.py` `ContextVar`), the six Neo4j repositories, and the JSONL
stores. The guard is persistence-agnostic so they can adopt it; none has.
