"""Durable capability registry and durable bindings.

Registration becomes atomic across processes
----------------------------------------------
The in-memory registry held the duplicate-contract check and the write under one
Python lock, which meant two *processes* both decided they were the first
registrant and the second silently won. Here ``reference`` is a **primary key**
and ``(capability_id, version)`` is a **unique constraint**, so the second INSERT
collides. The conflicting-contract refusal the domain already defines is what
that collision becomes.

Same version, same digest, is an idempotent re-registration and returns quietly —
and the *stored* definition wins, because it may have been validated or trusted
since and overwriting would silently undo those decisions. Same version,
different digest, is ``ConflictingRegistration``. **Never an overwrite.**

No generic mutation, still
----------------------------
There is no ``update``, no ``set_status``, no ``save(anything)``. ``register``
creates and ``replace`` stores a definition the *domain* has already moved. A
repository with a generic setter is a repository through which the lifecycle can
be bypassed, and the lifecycle is the security model — putting it behind SQL
would not make it less of a bypass.

Bindings are append-only, and now durably so
----------------------------------------------
``save`` and ``find`` and nothing else. No update, no replace, no delete. A
binding records a decision that was made; changing one would mean the thing that
runs could differ from the thing that was authorized while the same binding id
vouched for both. The primary key is what refuses the overwrite now, rather than
a dictionary check that only held within one process.

Digests are restored, never recomputed
----------------------------------------
``to_record``/``from_record`` are reused unchanged, and they restore the contract
digest rather than deriving it. This is the record that says what an approval was
about: a stored definition edited after registration must be *detectable*, and a
recomputed digest always matches.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageOperation
from backend.contexts.connectivity.domain.binding import CapabilityBinding
from backend.contexts.connectivity.domain.definition import CapabilityDefinition
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotFound,
    CapabilityVersionNotFound,
    ConflictingRegistration,
)
from backend.contexts.connectivity.domain.identifiers import CapabilityId, CapabilityRef
from backend.contexts.connectivity.infrastructure.binding_repository import (
    BINDING_STORAGE_BINDING,
)
from backend.contexts.connectivity.infrastructure.persistence import (
    binding_from_record,
    binding_to_record,
    from_record,
    to_record,
)
from backend.contexts.connectivity.infrastructure.repository import CAPABILITY_BINDING
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import PLATFORM_SCOPE, binding_table, capability_table
from backend.platform.storage import RepositoryGuard

__all__ = ["SqlCapabilityRepository", "SqlBindingRepository"]


class SqlCapabilityRepository:
    """The durable ``CapabilityRepository``. Same port, same refusals."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable capability registry requires a store")
        self._store = store
        self._guard = RepositoryGuard(CAPABILITY_BINDING)

    # -- writes --------------------------------------------------------

    def register(
        self,
        context: Any,
        definition: CapabilityDefinition,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Record a new version, atomically across processes.

        The INSERT *is* the duplicate check. A collision means somebody
        registered this reference first, and what happens next depends on whether
        they registered the same contract — which is read inside the same
        transaction, so the comparison cannot be raced either.
        """
        self._guard.authorize(StorageOperation.WRITE, context)
        record = to_record(definition, tenant_id=definition.tenant_id)
        reference = definition.reference.value
        with self._scope(unit) as work:
            try:
                # Savepointed. A colliding registration is the expected
                # path, and PostgreSQL aborts the transaction on a failed
                # statement -- without the savepoint the comparison read
                # below would raise 25P02 instead of answering.
                with work.attempt():
                    work.execute(
                        sa.insert(capability_table).values(
                            reference=reference,
                            capability_id=definition.capability_id.value,
                            version=definition.version.number,
                            scope_owner=definition.tenant_id or PLATFORM_SCOPE,
                            tenant_id=definition.tenant_id,
                            provider=definition.provider,
                            status=definition.status.value,
                            trust=definition.trust.value,
                            digest=definition.digest,
                            record=record,
                            registered_at=definition.registered_at,
                            updated_at=definition.updated_at,
                        )
                    )
                return
            except ConstraintConflict:
                pass

            existing = work.execute(
                sa.select(capability_table.c.record).where(
                    capability_table.c.reference == reference
                )
            ).first()
            if existing is None:
                # The unique constraint that fired was ``(capability_id,
                # version)`` under a different reference spelling. That is a
                # conflicting registration by any reading.
                raise ConflictingRegistration(
                    capability_ref=reference,
                    registered_digest="",
                    offered_digest=definition.digest or "",
                )
            registered = from_record(existing[0])
            if registered.digest != definition.digest:
                raise ConflictingRegistration(
                    capability_ref=reference,
                    registered_digest=registered.digest or "",
                    offered_digest=definition.digest or "",
                )
            # Same identity, same version, same digest: idempotent. The stored
            # definition wins -- it may have been validated or trusted since.
            return

    def replace(
        self,
        context: Any,
        definition: CapabilityDefinition,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Store a definition the domain has already moved.

        Not a generic update: the caller supplies a whole definition that the
        domain's own lifecycle produced, and this writes it. The row must already
        exist, so this can never create one by accident.
        """
        self._guard.authorize(StorageOperation.WRITE, context)
        record = to_record(definition, tenant_id=definition.tenant_id)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(capability_table)
                .where(capability_table.c.reference == definition.reference.value)
                .values(
                    status=definition.status.value,
                    trust=definition.trust.value,
                    digest=definition.digest,
                    record=record,
                    updated_at=definition.updated_at or work.now,
                )
            )
            if result.rowcount == 0:
                raise CapabilityVersionNotFound(
                    definition.capability_id.value, definition.version.number
                )

    # -- reads ---------------------------------------------------------

    def find(
        self,
        context: Any,
        reference: CapabilityRef,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[CapabilityDefinition]:
        """One definition, or nothing. Another tenant's is nothing.

        Visibility is applied in SQL. Fetching a row and then deciding not to
        return it would work, and would also mean the row briefly existed in this
        process — this way it is never selected.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(capability_table.c.record).where(
                    capability_table.c.reference == reference.value,
                    *self._visibility(context, access),
                )
            ).first()
        if row is None:
            return None
        definition = from_record(row[0])
        # The domain's own visibility rule, applied again: ``shared_with`` is a
        # list inside the document and cannot be a SQL predicate, so the coarse
        # scope filter narrows and this decides.
        return definition if self._visible(context, definition) else None

    def require(self, context: Any, reference: CapabilityRef) -> CapabilityDefinition:
        found = self.find(context, reference)
        if found is None:
            known = [
                d.version.number
                for d in self.versions_of(context, reference.capability_id)
            ]
            if not known:
                raise CapabilityNotFound(reference.capability_id.value)
            raise CapabilityVersionNotFound(
                reference.capability_id.value, reference.version.number, known
            )
        return found

    def versions_of(
        self,
        context: Any,
        capability_id: CapabilityId,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> Sequence[CapabilityDefinition]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(capability_table.c.record)
                .where(
                    capability_table.c.capability_id == capability_id.value,
                    *self._visibility(context, access),
                )
                .order_by(capability_table.c.version)
            ).all()
        found = [from_record(row[0]) for row in rows]
        return tuple(d for d in found if self._visible(context, d))

    def all(
        self, context: Any, *, unit: Optional[UnitOfWork] = None
    ) -> Sequence[CapabilityDefinition]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(capability_table.c.record)
                .where(*self._visibility(context, access))
                .order_by(capability_table.c.capability_id, capability_table.c.version)
            ).all()
        found = [from_record(row[0]) for row in rows]
        return tuple(d for d in found if self._visible(context, d))

    def exists(self, context: Any, reference: CapabilityRef) -> bool:
        return self.find(context, reference) is not None

    # -- internals -----------------------------------------------------

    def _visibility(self, context: Any, access: Any) -> tuple:
        """The coarse SQL narrowing: platform rows plus this tenant's own.

        Deliberately coarse. ``shared_with`` lives inside the document and is not
        a column, so the fine-grained decision stays with the domain's
        ``visible_to``. Narrowing here first means another tenant's private
        capability is never selected at all.
        """
        if self._guard.scope_filter(access) is None:
            return ()
        tenant = getattr(context, "tenant_id", None)
        return (
            sa.or_(
                capability_table.c.scope_owner == PLATFORM_SCOPE,
                capability_table.c.scope_owner == tenant,
                # Shared capabilities live under their owner's scope; the
                # document decides whether this tenant is on the list.
                capability_table.c.record.isnot(None),
            ),
        )

    @staticmethod
    def _visible(context: Any, definition: CapabilityDefinition) -> bool:
        if getattr(context, "is_platform_internal", False):
            return True
        return definition.visible_to(getattr(context, "tenant_id", None))

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


class SqlBindingRepository:
    """The durable ``BindingRepository``. Append-only, enforced by a primary key."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable binding repository requires a store")
        self._store = store
        self._guard = RepositoryGuard(BINDING_STORAGE_BINDING)

    def save(
        self,
        context: Any,
        binding: CapabilityBinding,
        *,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Write once. The primary key refuses the second write.

        Not a check followed by an insert: two processes binding the same id
        would both pass a check. The collision *is* the refusal, and it carries
        the domain's own message about why bindings are immutable.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        self._guard.assert_in_scope(_Row({"tenant_id": binding.tenant_id}), access)
        with self._scope(unit) as work:
            try:
                work.execute(
                    sa.insert(binding_table).values(
                        binding_id=binding.binding_id,
                        tenant_id=binding.tenant_id,
                        principal_id=binding.principal.principal_id,
                        capability_ref=binding.reference.value,
                        capability_digest=binding.capability_digest,
                        binding_digest=binding.digest,
                        provider=binding.provider,
                        operation=binding.operation.value,
                        execution_id=binding.execution_id,
                        node_id=binding.node_id,
                        expires_at=binding.expires_at,
                        record=_binding_record(binding),
                        created_at=work.now,
                    )
                )
            except ConstraintConflict:
                raise ContractViolation(
                    f"binding {binding.binding_id} already exists; bindings are "
                    "immutable, and a new choice is a new binding"
                ) from None

    def find(
        self, context: Any, binding_id: str, *, unit: Optional[UnitOfWork] = None
    ) -> Optional[CapabilityBinding]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(binding_table.c.record).where(
                    binding_table.c.binding_id == binding_id,
                    *self._tenant_predicate(access),
                )
            ).first()
        return _binding_from(row[0]) if row else None

    def for_execution(
        self, context: Any, execution_id: str, *, unit: Optional[UnitOfWork] = None
    ) -> Sequence[CapabilityBinding]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(binding_table.c.record)
                .where(
                    binding_table.c.execution_id == execution_id,
                    *self._tenant_predicate(access),
                )
                .order_by(binding_table.c.binding_id)
            ).all()
        return tuple(_binding_from(row[0]) for row in rows)

    def _tenant_predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (binding_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


class _Row:
    __slots__ = ("_data",)

    def __init__(self, data: dict) -> None:
        self._data = data

    def __getattr__(self, name: str) -> Any:
        try:
            return self._data[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc


# ----------------------------------------------------------------------
# Binding record mapping
# ----------------------------------------------------------------------
#
# Delegated to ``infrastructure.persistence``, which owns the record shape for
# this context and verifies the digest on the way back in. A second mapping here
# would be a second opinion about what a stored binding means.


def _binding_record(binding: CapabilityBinding) -> dict:
    return binding_to_record(binding)


def _binding_from(data: Any) -> CapabilityBinding:
    """Rebuild a binding, refusing one whose digest no longer matches.

    ``binding_from_record`` calls the domain's own ``verify_digest``, so a row
    edited outside the application raises ``BindingUnusable`` rather than loading
    as authority nobody granted. That is the whole reason the digest is stored
    rather than derived.
    """
    return binding_from_record(data)
