"""The storage boundary guard.

One object, owned by a repository, that turns an execution context into an
authorisation and a tenant predicate. It knows nothing about SQL, sessions, or
any particular database -- it deals in a column *name* and a tenant *value*, and
leaves building a predicate out of them to whatever persistence layer holds it.

That is what keeps it here in ``platform/`` at all: Constitution S10 forbids
``platform/`` from importing ``backend.database``, and a guard that knew how to
build a SQLAlchemy ``where`` clause would have to live below the layer that
every other storage mechanism -- Redis, Neo4j, JSONL -- also needs.

Usage from a repository::

    guard = RepositoryGuard(
        StorageBinding(record_type="MissionModel", scope_column="tenant_id")
    )

    async def get(self, context, pk):
        access = guard.authorize(StorageOperation.READ, context)
        row = await session.get(Model, pk)
        guard.assert_in_scope(row, access)      # refuses another tenant's row
        return row

The two calls are separate on purpose. ``authorize`` establishes *who is asking*
before any query runs; ``assert_in_scope`` checks *what came back*. A guard that
only did the first would authorise correctly and still hand over the wrong row.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.contracts.storage import StorageAccess, StorageBinding, StorageOperation
from backend.platform.storage.errors import UnattributedWrite, UnscopedRecordType
from backend.platform.storage.validation import validate_access, validate_record_scope

__all__ = ["RepositoryGuard"]


class RepositoryGuard:
    """Enforces tenant scoping for one record type.

    Immutable after construction and free of per-call state, so a repository can
    hold one on the class rather than rebuilding it per request, and two
    concurrent operations cannot observe each other's tenant.
    """

    __slots__ = ("_binding",)

    def __init__(self, binding: StorageBinding) -> None:
        if not isinstance(binding, StorageBinding):
            raise UnscopedRecordType(repr(binding))
        self._binding = binding

    # ------------------------------------------------------------------
    # Declaration
    # ------------------------------------------------------------------

    @property
    def binding(self) -> StorageBinding:
        return self._binding

    @property
    def scope_column(self) -> str:
        return self._binding.scope_column

    @property
    def record_type(self) -> str:
        return self._binding.record_type

    # ------------------------------------------------------------------
    # Authorisation
    # ------------------------------------------------------------------

    def authorize(self, operation: StorageOperation, context: Any) -> StorageAccess:
        """Establish who this operation acts for, or refuse it.

        Raises :class:`~backend.platform.storage.errors.MissingExecutionContext`
        when no usable context was supplied and
        :class:`~backend.platform.storage.errors.PlatformInternalDenied` when an
        untenanted context reached a record type that never opted in.
        """
        return validate_access(context, operation=operation, binding=self._binding)

    # ------------------------------------------------------------------
    # Predicate material
    # ------------------------------------------------------------------

    def scope_filter(self, access: StorageAccess) -> Optional[tuple[str, str]]:
        """The ``(column, value)`` a read must be narrowed by.

        ``None`` for a platform-internal access, which is exactly the case where
        no narrowing applies. Callers must treat ``None`` as "this access was
        authorised to see everything", never as "no filter was needed" -- the
        difference is the whole point of making platform-internal opt-in.
        """
        if access.platform_internal:
            return None
        return (access.scope_column, access.tenant_id)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def assert_in_scope(self, record: Any, access: StorageAccess) -> None:
        """Refuse a record belonging to a tenant other than the authorised one.

        ``None`` -- a miss -- is not a violation: a query that found nothing has
        leaked nothing. A row that exists but belongs elsewhere is.
        """
        if record is None:
            return
        validate_record_scope(getattr(record, access.scope_column, None), access=access)

    def stamp(self, record: Any, access: StorageAccess) -> Any:
        """Write the authorised tenant onto a record about to be persisted.

        If the record already carries a *different* tenant this refuses rather
        than overwriting. Silently restamping would turn an attempt to write into
        another tenant's space into a successful write into your own, which
        destroys the evidence that the attempt happened at all.

        A platform-internal write must arrive with its tenant already set. There
        is no tenant to derive -- that is what platform-internal means -- and
        stamping nothing would persist a row with a null owner. ``assert_in_scope``
        treats such a row as a violation on the way back out, so allowing one to
        be written here would mean creating data the boundary can never return.
        """
        current = getattr(record, access.scope_column, None)
        if current is not None:
            validate_record_scope(current, access=access)
            return record

        if access.platform_internal:
            raise UnattributedWrite(
                operation=access.operation.value,
                record_type=access.binding.record_type,
                scope_column=access.scope_column,
            )

        setattr(record, access.scope_column, access.tenant_id)
        return record

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return (
            f"RepositoryGuard(record_type={self.record_type!r}, "
            f"scope_column={self.scope_column!r})"
        )
