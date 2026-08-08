"""The tenant-scoped repository, against a real database.

SQLite over ``aiosqlite``, with a real declarative model, real sessions and real
SQL. Not a mock: the claim being tested is that a cross-tenant read *returns
nothing*, and only a real query engine can demonstrate that a predicate was
actually applied rather than merely constructed.

The model registers against its own ``DeclarativeBase`` rather than the
application's, so creating and dropping it cannot disturb the app metadata that
other tests share.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.contracts.storage import StorageOperation
from backend.database.repositories.tenant_scoped import TenantScopedRepository
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext
from backend.platform.storage import (
    CrossTenantAccess,
    MissingExecutionContext,
    PlatformInternalDenied,
    UnscopedRecordType,
)


class ModelBase(DeclarativeBase):
    """Isolated metadata, so these tables never touch the app's."""


class WidgetModel(ModelBase):
    __tablename__ = "widgets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class UnownedModel(ModelBase):
    """A model with no tenant column, for the construction-time refusal."""

    __tablename__ = "unowned"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128))


class WidgetRepository(TenantScopedRepository[WidgetModel]):
    __scope_column__ = "tenant_id"

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WidgetModel, session)

    async def by_name(self, context, name: str):
        """A bespoke query routed through the scoped helper."""
        result = await self._execute_scoped(
            context, select(WidgetModel).where(WidgetModel.name == name), StorageOperation.READ
        )
        return list(result.scalars().all())


class SweepRepository(TenantScopedRepository[WidgetModel]):
    """Same table, but explicitly permits platform-internal access."""

    __scope_column__ = "tenant_id"
    __platform_internal_allowed__ = True

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WidgetModel, session)


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _context(tenant_id: str) -> ExecutionContext:
    return ExecutionContext.for_tenant(
        tenant_id=tenant_id,
        identity=IdentityContext.platform("repo-tests"),
        source="test",
    )


@pytest.fixture
def alice() -> ExecutionContext:
    return _context("tenant-alice")


@pytest.fixture
def bob() -> ExecutionContext:
    return _context("tenant-bob")


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(ModelBase.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as active:
        yield active

    await engine.dispose()


@pytest_asyncio.fixture
async def seeded(session, alice, bob):
    """One widget for each of two tenants, written through the guard."""
    repo = WidgetRepository(session)
    await repo.create(alice, WidgetModel(name="alice-widget"))
    await repo.create(bob, WidgetModel(name="bob-widget"))
    await session.commit()
    return repo


# ----------------------------------------------------------------------
# Missing context
# ----------------------------------------------------------------------


async def test_every_method_refuses_a_missing_context(session):
    repo = WidgetRepository(session)
    pk = uuid.uuid4()

    with pytest.raises(MissingExecutionContext):
        await repo.get(None, pk)
    with pytest.raises(MissingExecutionContext):
        await repo.list(None)
    with pytest.raises(MissingExecutionContext):
        await repo.count(None)
    with pytest.raises(MissingExecutionContext):
        await repo.create(None, WidgetModel(name="x"))
    with pytest.raises(MissingExecutionContext):
        await repo.update(None, WidgetModel(name="x"))
    with pytest.raises(MissingExecutionContext):
        await repo.delete(None, pk)


async def test_refusal_happens_before_any_row_is_written(session, alice):
    """A refused create must leave the table exactly as it was."""
    repo = WidgetRepository(session)
    before = await repo.count(alice)

    with pytest.raises(MissingExecutionContext):
        await repo.create(None, WidgetModel(name="ghost"))

    assert await repo.count(alice) == before


# ----------------------------------------------------------------------
# Cross-tenant reads return nothing
# ----------------------------------------------------------------------


async def test_list_returns_only_the_contexts_own_rows(seeded, alice, bob):
    alice_rows = await seeded.list(alice)
    bob_rows = await seeded.list(bob)

    assert [r.name for r in alice_rows] == ["alice-widget"]
    assert [r.name for r in bob_rows] == ["bob-widget"]


async def test_count_is_scoped(seeded, alice, bob):
    assert await seeded.count(alice) == 1
    assert await seeded.count(bob) == 1


async def test_bespoke_query_is_scoped_too(seeded, alice, bob):
    """A subclass query routed through _execute_scoped inherits the predicate."""
    assert [r.name for r in await seeded.by_name(alice, "bob-widget")] == []
    assert [r.name for r in await seeded.by_name(bob, "bob-widget")] == ["bob-widget"]


async def test_get_by_primary_key_refuses_another_tenants_row(seeded, alice, bob):
    """A direct pk lookup must raise rather than quietly return the row.

    Distinct from ``list``, which filters. Here the caller already knows the id,
    so returning ``None`` would be indistinguishable from "no such row" and would
    hide an attempted cross-tenant read.
    """
    (bob_widget,) = await seeded.list(bob)

    with pytest.raises(CrossTenantAccess) as caught:
        await seeded.get(alice, bob_widget.id)

    assert caught.value.context_tenant == "tenant-alice"
    assert caught.value.record_tenant == "tenant-bob"


async def test_get_of_own_row_succeeds(seeded, alice):
    (widget,) = await seeded.list(alice)
    fetched = await seeded.get(alice, widget.id)
    assert fetched is not None and fetched.name == "alice-widget"


async def test_get_of_a_nonexistent_row_is_a_plain_miss(seeded, alice):
    assert await seeded.get(alice, uuid.uuid4()) is None


# ----------------------------------------------------------------------
# Cross-tenant writes are rejected
# ----------------------------------------------------------------------


async def test_create_stamps_the_context_tenant(session, alice):
    repo = WidgetRepository(session)
    widget = await repo.create(alice, WidgetModel(name="fresh"))
    assert widget.tenant_id == "tenant-alice"


async def test_create_into_another_tenant_is_refused(session, alice):
    repo = WidgetRepository(session)
    smuggled = WidgetModel(name="smuggled", tenant_id="tenant-bob")

    with pytest.raises(CrossTenantAccess):
        await repo.create(alice, smuggled)


async def test_refused_create_writes_no_row(session, alice, bob):
    repo = WidgetRepository(session)
    with pytest.raises(CrossTenantAccess):
        await repo.create(alice, WidgetModel(name="smuggled", tenant_id="tenant-bob"))

    session.expunge_all()
    assert await repo.count(bob) == 0
    assert await repo.count(alice) == 0


async def test_update_of_another_tenants_row_is_refused(seeded, alice, bob):
    (bob_widget,) = await seeded.list(bob)
    bob_widget.name = "hijacked"

    with pytest.raises(CrossTenantAccess):
        await seeded.update(alice, bob_widget)


async def test_delete_of_another_tenants_row_is_refused(seeded, alice, bob):
    (bob_widget,) = await seeded.list(bob)

    with pytest.raises(CrossTenantAccess):
        await seeded.delete(alice, bob_widget.id)

    # And the row survives.
    assert await seeded.count(bob) == 1


async def test_delete_of_own_row_succeeds(seeded, alice):
    (widget,) = await seeded.list(alice)
    assert await seeded.delete(alice, widget.id) is True
    assert await seeded.count(alice) == 0


async def test_delete_of_a_missing_row_reports_false(seeded, alice):
    assert await seeded.delete(alice, uuid.uuid4()) is False


# ----------------------------------------------------------------------
# Platform-internal access
# ----------------------------------------------------------------------


async def test_platform_internal_refused_where_not_declared(session):
    repo = WidgetRepository(session)
    context = ExecutionContext.platform_internal(
        reason="sweep", component="audit", source="scheduler"
    )
    with pytest.raises(PlatformInternalDenied):
        await repo.list(context)


async def test_platform_internal_sees_every_tenant_where_declared(seeded, session):
    sweep = SweepRepository(session)
    context = ExecutionContext.platform_internal(
        reason="integrity-sweep", component="audit", source="scheduler"
    )
    rows = await sweep.list(context)
    assert sorted(r.name for r in rows) == ["alice-widget", "bob-widget"]


async def test_platform_internal_is_opt_in_per_repository(seeded, session):
    """Same table, two repositories, opposite answers.

    Proves the permission attaches to the declaration rather than leaking from
    the table or the context.
    """
    context = ExecutionContext.platform_internal(
        reason="sweep", component="audit", source="scheduler"
    )
    assert len(await SweepRepository(session).list(context)) == 2
    with pytest.raises(PlatformInternalDenied):
        await WidgetRepository(session).list(context)


# ----------------------------------------------------------------------
# Construction-time refusals
# ----------------------------------------------------------------------


async def test_repository_without_a_scope_column_cannot_be_built(session):
    class Undeclared(TenantScopedRepository[WidgetModel]):
        pass

    with pytest.raises(UnscopedRecordType):
        Undeclared(WidgetModel, session)


async def test_scope_column_absent_from_the_model_is_caught_at_construction(session):
    """A typo'd column must fail now, not on the first production read."""

    class Typo(TenantScopedRepository[UnownedModel]):
        __scope_column__ = "tenat_id"

    with pytest.raises(UnscopedRecordType) as caught:
        Typo(UnownedModel, session)
    assert "tenat_id" in str(caught.value)


async def test_model_with_no_tenant_column_cannot_be_scoped(session):
    class Impossible(TenantScopedRepository[UnownedModel]):
        __scope_column__ = "tenant_id"

    with pytest.raises(UnscopedRecordType):
        Impossible(UnownedModel, session)


# ----------------------------------------------------------------------
# Existing behaviour preserved
# ----------------------------------------------------------------------


async def test_unscoped_base_repository_is_untouched(session):
    """``BaseRepository`` keeps its original context-free signature.

    PR-10 adds a boundary; it does not change the one 35 repositories already
    use. If this fails, the migration became a rewrite.
    """
    import inspect

    from backend.database.repositories.base import BaseRepository

    assert list(inspect.signature(BaseRepository.get).parameters) == ["self", "pk"]
    assert list(inspect.signature(BaseRepository.list).parameters) == [
        "self", "limit", "offset"
    ]
    assert list(inspect.signature(BaseRepository.create).parameters) == ["self", "obj"]


async def test_scoped_repository_is_not_a_base_repository():
    """Deliberately not substitutable -- the signatures are incompatible.

    If someone makes ``TenantScopedRepository`` inherit ``BaseRepository`` for
    convenience, a caller holding a ``BaseRepository[T]`` could call ``get(pk)``
    and have the pk silently bound to ``context``.
    """
    from backend.database.repositories.base import BaseRepository

    assert not issubclass(TenantScopedRepository, BaseRepository)
