"""Tenant-scoped async repository base.

Every method takes an ``ExecutionContext`` as its first argument, derives the
tenant from it, and narrows or stamps accordingly. A call without one is refused
before any SQL is built.

Why this does not extend ``BaseRepository``
-------------------------------------------
It would be shorter to inherit and override, and it would be wrong. The two
classes have deliberately incompatible signatures -- ``BaseRepository.get(pk)``
versus ``TenantScopedRepository.get(context, pk)`` -- so inheritance would make a
scoped repository substitutable for an unscoped one wherever the base type is
annotated. A caller holding a ``BaseRepository[T]`` reference could then write
``repo.get(some_uuid)`` and have the uuid silently bound to ``context``, where
:func:`is_repository_context` rejects it as malformed.

That last part is the tell: the failure would be *caught*, but only at runtime,
in a code path a type checker had already declared safe. Refusing the
inheritance relationship makes it a type error at the call site instead.

Declaring a scope
-----------------
A subclass names the column carrying tenant identity::

    class MissionRepository(TenantScopedRepository[MissionModel]):
        __scope_column__ = "tenant_id"

        def __init__(self, session):
            super().__init__(MissionModel, session)

The column must exist on the model. Both the missing declaration and the missing
column raise at construction rather than on first query -- discovering that a
"scoped" repository was never scoped during a production read is far too late.

Platform-internal access is opt-in per repository via
``__platform_internal_allowed__``. It is off by default because it erases the
isolation boundary, and an escape hatch that is on by default is not an escape
hatch, it is the door.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Generic, List, Optional, Type, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.database.base import Base
from backend.platform.storage import RepositoryGuard, UnscopedRecordType

T = TypeVar("T", bound=Base)

__all__ = ["TenantScopedRepository"]


class TenantScopedRepository(Generic[T]):
    """Async CRUD that cannot execute without an execution context.

    Mirrors ``BaseRepository``'s surface -- ``get``, ``list``, ``count``,
    ``create``, ``update``, ``delete`` -- with a context argument threaded through
    every one and a tenant predicate applied to every statement.
    """

    __scope_column__: ClassVar[Optional[str]] = None
    __platform_internal_allowed__: ClassVar[bool] = False

    def __init__(self, model: Type[T], session: AsyncSession) -> None:
        column = type(self).__scope_column__
        if not isinstance(column, str) or not column.strip():
            raise UnscopedRecordType(type(self).__name__)

        # The column must exist on the model, not merely be named. A typo'd
        # scope column would otherwise build a guard that stamps an attribute
        # SQLAlchemy never persists, producing rows with no owner at all.
        if not hasattr(model, column):
            raise UnscopedRecordType(
                f"{type(self).__name__} (model {model.__name__} has no attribute {column!r})"
            )

        self._model = model
        self._session = session
        self._guard = RepositoryGuard(
            StorageBinding(
                record_type=model.__name__,
                scope_column=column,
                platform_internal_allowed=type(self).__platform_internal_allowed__,
            )
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def guard(self) -> RepositoryGuard:
        return self._guard

    def _scoped(self, stmt: Any, access: Any) -> Any:
        """Narrow a statement to the authorised tenant.

        A platform-internal access yields no filter, which is the one case where
        seeing every tenant's rows is the intent rather than a bug.
        """
        scope = self._guard.scope_filter(access)
        if scope is None:
            return stmt
        column, value = scope
        return stmt.where(getattr(self._model, column) == value)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get(self, context: Any, pk: uuid.UUID) -> Optional[T]:
        """Fetch by primary key, refusing a row owned by another tenant.

        The row is fetched and then checked rather than fetched with a predicate:
        a primary-key lookup that returned someone else's row is a fact worth
        raising on, and narrowing the query first would turn it into an
        indistinguishable miss.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        row = await self._session.get(self._model, pk)
        self._guard.assert_in_scope(row, access)
        return row

    async def list(self, context: Any, limit: int = 50, offset: int = 0) -> List[T]:
        access = self._guard.authorize(StorageOperation.READ, context)
        stmt = self._scoped(select(self._model), access)

        # Newest-first where the model records a creation time. ``BaseRepository``
        # assumes every model has one and raises AttributeError where that does
        # not hold; a scoped repository over a model without timestamps should
        # return rows, not explode, so the ordering is applied only if available.
        created_at = getattr(self._model, "created_at", None)
        if created_at is not None:
            stmt = stmt.order_by(created_at.desc())

        result = await self._session.execute(stmt.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def count(self, context: Any) -> int:
        access = self._guard.authorize(StorageOperation.READ, context)
        stmt = self._scoped(select(func.count()).select_from(self._model), access)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def create(self, context: Any, obj: T) -> T:
        """Insert, stamping the authorised tenant onto the row.

        An object arriving with a *different* tenant already set is refused, not
        restamped -- see ``RepositoryGuard.stamp``.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.stamp(obj, access)
        self._session.add(obj)
        await self._session.flush()
        await self._session.refresh(obj)
        return obj

    async def update(self, context: Any, obj: T) -> T:
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.assert_in_scope(obj, access)
        merged = await self._session.merge(obj)
        await self._session.flush()
        await self._session.refresh(merged)
        return merged

    async def delete(self, context: Any, pk: uuid.UUID) -> bool:
        access = self._guard.authorize(StorageOperation.DELETE, context)
        row = await self._session.get(self._model, pk)
        if row is None:
            return False
        self._guard.assert_in_scope(row, access)
        await self._session.delete(row)
        await self._session.flush()
        return True

    # ------------------------------------------------------------------
    # Helpers for subclasses
    # ------------------------------------------------------------------

    async def _execute_scoped(self, context: Any, stmt: Any, operation: StorageOperation):
        """Run a subclass-built statement with the tenant predicate applied.

        Subclasses with bespoke queries must route them through here rather than
        touching ``self._session`` directly; the architecture rule in
        ``platform/architecture/tenancy_rules.py`` flags a scoped repository that
        reaches for the session on its own.
        """
        access = self._guard.authorize(operation, context)
        return await self._session.execute(self._scoped(stmt, access))
