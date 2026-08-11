"""Durable authorization evidence, and the delegation persistence seam.

Authorization records are evidence, not an engine
---------------------------------------------------
``CapabilityAuthorizationService`` decides. This writes down what it decided.
There is no ``authorize`` here, no policy evaluation, no effect derivation and no
method that returns a permission — a second place that could answer "may this
happen" is the one thing this phase must not create.

What that buys is the thing an in-memory decision could not provide: after a
restart, an audit can still answer *which* decision a running execution was
admitted under, with the policy version, the action digest and the decision
digest that were current at the time. Those are facts about the past, and facts
about the past are exactly what must survive a process.

The record is append-only. A decision that was made cannot be edited into a
different decision, because the row that vouches for an execution would then
vouch for something else while keeping its id.

Delegation is a seam, and stays one
-------------------------------------
Phase 4.4 closed the ADR-040 gap by refusing **every** on-behalf-of invocation:
``AuthorizationRequest`` has no delegation concept, so nothing authoritative
could answer "may this actor act for that principal", and absence is not
permission.

This gives that answer somewhere durable to live. It does **not** implement the
workflow — there is no issuing endpoint, no approval flow, no revocation
command, and ``DelegationAuthority`` is still unwired at the composition root.
Building the workflow is Phase 5.2; building the table now is what stops Phase
5.2 from inventing a shape under time pressure.

**The default remains safe.** An empty table means no delegation exists, and
``SqlDelegationRepository.grant_for`` returns ``None``, which
``_check_delegation`` turns into ``DELEGATION_NOT_AUTHORIZED``. Nothing about
having a table makes delegation work.

Why the fields are what they are
----------------------------------
    actor + delegated principal   the pair being authorized, kept distinct
    tenant                        delegation never crosses one
    scope                         what may be done *as* the other principal
    validity window               a delegation that never expires is a
                                  permanent identity transfer
    issuer                        who granted it — an unattributed delegation
                                  is one nobody can be asked about
    revocation state              withdrawn without deleting, so the evidence
                                  that it existed survives
    digest                        so an edited grant is detectable

An empty ``scope`` is refused at write time rather than stored: a delegation of
nothing reads as a delegation of everything to the first query that treats a
missing list as unconstrained.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.contracts.storage import StorageBinding, StorageOperation
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import (
    authorization_table,
    delegation_request_table,
    delegation_table,
)
from backend.platform.hashing import compute_digest
from backend.platform.storage import RepositoryGuard

__all__ = [
    "delegation_digest_payload",
    "request_digest_payload",
    "SqlDelegationRequestRepository",
    "DelegationRequestRecord",
    "DELEGATION_REQUEST_BINDING",
    "SqlAuthorizationRecordRepository",
    "SqlDelegationRepository",
    "DelegationGrantRecord",
    "AUTHORIZATION_BINDING",
    "DELEGATION_BINDING",
]

AUTHORIZATION_BINDING = StorageBinding(
    record_type="AuthorizationDecision",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)
DELEGATION_BINDING = StorageBinding(
    record_type="DelegationGrant",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)
DELEGATION_REQUEST_BINDING = StorageBinding(
    record_type="DelegationRequest",
    scope_column="tenant_id",
    platform_internal_allowed=True,
)


def request_digest_payload(
    *,
    request_id: str,
    tenant_id: str,
    actor_principal_id: str,
    delegated_principal_id: str,
    scope: Any,
    reason: str,
    requested_by: str,
    requested_at: Any,
    validity_seconds: int,
) -> dict:
    """The exact bytes a delegation *request* is digested over. One definition.

    An approval binds to this value, so it must cover everything that changes
    what the eventual grant can do: the pair, the tenant, the scope and how long
    it lasts. Widen the scope after approval and the digest moves, the approval
    stops matching, and issuance refuses — which is the entire mechanism, and
    the reason ``requested_by`` is in here too (an approval is for *this*
    person's request, not for the shape of it).
    """
    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "actor_principal_id": actor_principal_id,
        "delegated_principal_id": delegated_principal_id,
        "scope": scope,
        "reason": reason,
        "requested_by": requested_by,
        "requested_at": _iso(requested_at),
        "validity_seconds": int(validity_seconds),
    }


def delegation_digest_payload(
    *,
    delegation_id: str,
    tenant_id: str,
    actor_principal_id: str,
    delegated_principal_id: str,
    scope: Any,
    issued_by: str,
    issued_at: Any,
    expires_at: Any,
) -> dict:
    """The exact bytes a delegation grant is digested over. **One definition.**

    Written once and used at issue *and* at verification, because the digest is
    what makes an edited grant detectable and a digest computed over two slightly
    different payloads can never match.

    The timestamps are normalised through ``_aware`` before formatting. That is
    not cosmetic: SQLite has no timezone type, so a value written as
    ``...+00:00`` comes back naive and would format differently — which would
    make every stored grant fail its own digest check, and the check would look
    like tamper detection working rather than a round-trip bug.
    """
    return {
        "delegation_id": delegation_id,
        "tenant_id": tenant_id,
        "actor_principal_id": actor_principal_id,
        "delegated_principal_id": delegated_principal_id,
        "scope": scope,
        "issued_by": issued_by,
        "issued_at": _iso(issued_at),
        "expires_at": _iso(expires_at),
    }


class SqlAuthorizationRecordRepository:
    """Writes down decisions. **Never makes one.**"""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable authorization record store requires a store")
        self._store = store
        self._guard = RepositoryGuard(AUTHORIZATION_BINDING)

    def record(
        self,
        context: Any,
        *,
        decision_id: str,
        principal_id: str,
        capability_ref: str,
        operation: str,
        policy_version: str,
        effect: str,
        risk: str,
        decision_digest: str,
        expires_at: datetime,
        action_digest: Optional[str] = None,
        delegated_principal_id: Optional[str] = None,
        approval_artifact_id: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> None:
        """Append one decision. Recording the same one twice is not an error.

        A command replayed after an unknown commit outcome legitimately arrives
        here again with the same ``decision_id``; the primary key refuses the
        duplicate and this returns quietly. Raising would push a caller towards
        inventing a new id for a decision that already exists, which is how one
        decision becomes two rows that disagree.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            try:
                # Savepointed. This handler **swallows** the conflict and lets the
                # caller carry on, and the caller is frequently inside a larger
                # transaction -- the outbox write shares one with the state change
                # that produced the event, by design. On PostgreSQL a failed
                # statement aborts that whole transaction, so swallowing the error
                # without a savepoint would leave the caller committing into a
                # transaction the database had already abandoned.
                with work.attempt():
                    work.execute(
                        sa.insert(authorization_table).values(
                            decision_id=decision_id,
                            tenant_id=access.tenant_id,
                            principal_id=principal_id,
                            delegated_principal_id=delegated_principal_id,
                            capability_ref=capability_ref,
                            operation=operation,
                            action_digest=action_digest,
                            policy_version=policy_version,
                            effect=effect,
                            risk=risk,
                            approval_artifact_id=approval_artifact_id,
                            # Stored exactly as the decision computed it. Never
                            # recomputed here -- this layer has no policy engine to
                            # recompute it with, which is the point.
                            decision_digest=decision_digest,
                            expires_at=expires_at,
                            recorded_at=work.now,
                            record=dict(detail or {}),
                        )
                    )
            except ConstraintConflict:
                return

    def find(
        self, context: Any, decision_id: str, *, unit: Optional[UnitOfWork] = None
    ) -> Optional[dict]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(authorization_table).where(
                    authorization_table.c.decision_id == decision_id,
                    *self._predicate(access),
                )
            ).mappings().first()
        return dict(row) if row else None

    def for_action(
        self,
        context: Any,
        action_digest: str,
        *,
        limit: int = 20,
        unit: Optional[UnitOfWork] = None,
    ) -> Sequence[dict]:
        """Every decision recorded against one action. What an audit asks."""
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(authorization_table)
                .where(
                    authorization_table.c.action_digest == action_digest,
                    *self._predicate(access),
                )
                .order_by(authorization_table.c.recorded_at.desc())
                .limit(limit)
            ).mappings().all()
        return tuple(dict(row) for row in rows)

    def _predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (authorization_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


class DelegationGrantRecord:
    """One durable delegation grant, as read back. Data, never a permission.

    Deliberately not a domain object and deliberately not named ``Delegation``:
    the domain has no delegation type yet, and creating one here would put the
    model in the persistence layer where the policy that uses it cannot see it.
    """

    __slots__ = (
        "delegation_id",
        "tenant_id",
        "actor_principal_id",
        "delegated_principal_id",
        "scope",
        "issued_by",
        "issued_at",
        "expires_at",
        "revoked_at",
        "digest",
        "request_id",
        "approval_artifact_id",
        "approved_by",
        "revoked_by",
    )

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    def is_live_at(self, moment: datetime) -> bool:
        """Not revoked, and not expired. Both, or neither matters."""
        if self.revoked_at is not None:
            return False
        expires = _aware(self.expires_at)
        return expires is not None and moment < expires

    def permits(self, capability_ref: str, operation: str) -> bool:
        """Whether this grant covers that operation. **Never a wildcard.**

        An empty scope is refused at write time, so there is no state here that
        reads as "everything". A grant that does not list the operation does not
        permit it, and there is no branch that treats an unrecognised scope shape
        as permissive.
        """
        entries = self.scope if isinstance(self.scope, list) else []
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            if entry.get("capability_ref") != capability_ref:
                continue
            operations = entry.get("operations")
            if isinstance(operations, list) and operation in operations:
                return True
        return False

    def to_dict(self) -> dict:
        return {
            "delegation_id": self.delegation_id,
            "tenant_id": self.tenant_id,
            "actor_principal_id": self.actor_principal_id,
            "delegated_principal_id": self.delegated_principal_id,
            "scope": self.scope,
            "issued_by": self.issued_by,
            "issued_at": _iso(self.issued_at),
            "expires_at": _iso(self.expires_at),
            "revoked_at": _iso(self.revoked_at),
            "digest": self.digest,
            "request_id": self.request_id,
            "approval_artifact_id": self.approval_artifact_id,
            "approved_by": self.approved_by,
            "revoked_by": self.revoked_by,
        }


class SqlDelegationRepository:
    """The delegation persistence seam. **No workflow, and no default grant.**"""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable delegation store requires a store")
        self._store = store
        self._guard = RepositoryGuard(DELEGATION_BINDING)

    def issue(
        self,
        context: Any,
        *,
        delegation_id: str,
        actor_principal_id: str,
        delegated_principal_id: str,
        scope: Sequence[Mapping[str, Any]],
        issued_by: str,
        expires_at: datetime,
        request_id: str,
        approval_artifact_id: str,
        approved_by: str,
        unit: Optional[UnitOfWork] = None,
    ) -> DelegationGrantRecord:
        """Write a grant, **only against an approval that already exists**.

        The three evidence arguments are keyword-required and have no defaults,
        which is the enforcement: there is no call to this method that produces
        an unapproved grant, so ``DelegationWorkflow`` is not a gate that could
        be bypassed by finding a second way in. It is the only assembler of the
        evidence, not the only guard over it.

        This method does not *check* the approval — checking is the workflow's,
        which holds the request row and can compare digests. What it refuses is
        the shape: a grant with nothing to point at.
        """
        for name, value in (
            ("request_id", request_id),
            ("approval_artifact_id", approval_artifact_id),
            ("approved_by", approved_by),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"a delegation grant requires {name}; an unattributed grant "
                    "is authority nobody can be asked about"
                )
        if approved_by == issued_by and approved_by == actor_principal_id:
            raise ContractViolation(
                "the actor cannot be the approver of its own delegation; a "
                "self-approved grant is the system authorizing itself"
            )
        if actor_principal_id == delegated_principal_id:
            raise ContractViolation(
                "an actor cannot be delegated its own identity; a self-delegation "
                "is a grant that says nothing and would read as permission"
            )
        entries = [dict(entry) for entry in scope]
        if not entries:
            raise ContractViolation(
                "a delegation must state what it covers; an empty scope is a "
                "delegation of everything to the first query that treats a "
                "missing list as unconstrained"
            )
        for entry in entries:
            if not entry.get("capability_ref") or not entry.get("operations"):
                raise ContractViolation(
                    "each delegation scope entry must name a capability and at "
                    "least one operation"
                )
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            if expires_at <= work.now:
                raise ContractViolation(
                    "a delegation must expire in the future; one that is already "
                    "expired is a row that only confuses an audit"
                )
            digest = compute_digest(
                delegation_digest_payload(
                    delegation_id=delegation_id,
                    tenant_id=access.tenant_id,
                    actor_principal_id=actor_principal_id,
                    delegated_principal_id=delegated_principal_id,
                    scope=entries,
                    issued_by=issued_by,
                    issued_at=work.now,
                    expires_at=expires_at,
                )
            ).value
            try:
                work.execute(
                    sa.insert(delegation_table).values(
                        delegation_id=delegation_id,
                        tenant_id=access.tenant_id,
                        actor_principal_id=actor_principal_id,
                        delegated_principal_id=delegated_principal_id,
                        scope=entries,
                        issued_by=issued_by,
                        issued_at=work.now,
                        expires_at=expires_at,
                        digest=digest,
                        request_id=request_id,
                        approval_artifact_id=approval_artifact_id,
                        approved_by=approved_by,
                    )
                )
            except ConstraintConflict:
                raise ContractViolation(
                    f"delegation {delegation_id} already exists; a grant is "
                    "issued once, and changing one would let the same id vouch "
                    "for different authority"
                ) from None
            return DelegationGrantRecord(
                delegation_id=delegation_id,
                tenant_id=access.tenant_id,
                actor_principal_id=actor_principal_id,
                delegated_principal_id=delegated_principal_id,
                scope=entries,
                issued_by=issued_by,
                issued_at=work.now,
                expires_at=expires_at,
                revoked_at=None,
                digest=digest,
            )

    def revoke(
        self,
        context: Any,
        *,
        delegation_id: str,
        reason: str,
        revoked_by: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Withdraw a grant. The row stays — the evidence it existed matters.

        Revocation touches **this row only**. It does not reach into
        ``cp_execution``, ``cp_authorization`` or ``cp_outbox``: a run that was
        admitted under this grant was genuinely admitted under it, and rewriting
        that would turn revocation into a way to erase history. What revocation
        changes is what happens *next*, and nothing else.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("revoking a delegation requires a stated reason")
        if not isinstance(revoked_by, str) or not revoked_by.strip():
            raise ContractViolation(
                "revoking a delegation requires an attributable revoker; an "
                "anonymous revocation is one nobody can be asked about"
            )
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(delegation_table)
                .where(
                    delegation_table.c.delegation_id == delegation_id,
                    delegation_table.c.revoked_at.is_(None),
                    *self._predicate(access),
                )
                .values(
                    revoked_at=work.now,
                    revocation_reason=reason[:512],
                    revoked_by=revoked_by,
                )
            )
            return result.rowcount == 1

    def grant_for(
        self,
        context: Any,
        *,
        actor_principal_id: str,
        delegated_principal_id: str,
        now: Optional[datetime] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[DelegationGrantRecord]:
        """The live grant for this pair, or ``None``.

        ``None`` is the answer in an empty database, which is the answer that
        keeps every on-behalf-of invocation refused. That is the default and it
        is meant to be reached.
        """
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            moment = now or work.now
            row = work.execute(
                sa.select(delegation_table)
                .where(
                    delegation_table.c.actor_principal_id == actor_principal_id,
                    delegation_table.c.delegated_principal_id == delegated_principal_id,
                    delegation_table.c.revoked_at.is_(None),
                    *self._predicate(access),
                )
                .order_by(delegation_table.c.issued_at.desc())
                .limit(1)
            ).mappings().first()
        if row is None:
            return None
        grant = DelegationGrantRecord(**{k: row[k] for k in DelegationGrantRecord.__slots__})
        return grant if grant.is_live_at(moment) else None

    def _predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (delegation_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


class DelegationRequestRecord:
    """One durable delegation request, as read back. **A request, not authority.**

    Nothing on this object grants anything. ``status`` says where the request got
    to; even ``issued`` only records that a grant was produced, and the grant is
    the row in ``cp_delegation`` that ``grant_for`` reads.
    """

    __slots__ = (
        "request_id",
        "tenant_id",
        "requested_by",
        "actor_principal_id",
        "delegated_principal_id",
        "scope",
        "reason",
        "requested_validity_seconds",
        "requested_at",
        "expires_at",
        "request_digest",
        "status",
        "approved_by",
        "approved_at",
        "approval_artifact_id",
        "approval_digest",
        "decision_reason",
        "issued_delegation_id",
    )

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    def is_expired_at(self, moment: datetime) -> bool:
        expires = _aware(self.expires_at)
        return expires is None or moment >= expires

    def to_dict(self) -> dict:
        return {
            name: (
                _iso(getattr(self, name))
                if name.endswith("_at")
                else getattr(self, name)
            )
            for name in self.__slots__
        }


class SqlDelegationRequestRepository:
    """Durable delegation requests and the approval evidence recorded on them.

    Two writes and no decisions. ``open`` records that somebody asked; ``decide``
    records what an approver concluded. Whether that approver was *allowed* to
    conclude it is ``DelegationWorkflow``'s question, because answering it needs
    the approver policy and this layer has none - putting the check here would be
    a second authorization engine living in the persistence layer.

    What this layer does enforce is that a decision lands **once**. The update is
    conditional on the row still being pending, so two approvers racing produce
    one decision and one refusal rather than a last-writer-wins overwrite of an
    approval by a denial.
    """

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("a durable delegation request store requires a store")
        self._store = store
        self._guard = RepositoryGuard(DELEGATION_REQUEST_BINDING)

    def open(
        self,
        context: Any,
        *,
        request_id: str,
        requested_by: str,
        actor_principal_id: str,
        delegated_principal_id: str,
        scope: Sequence[Mapping[str, Any]],
        reason: str,
        validity_seconds: int,
        expires_at: datetime,
        unit: Optional[UnitOfWork] = None,
    ) -> DelegationRequestRecord:
        """Record that somebody asked. Grants nothing, and never has."""
        entries = [dict(entry) for entry in scope]
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            digest = compute_digest(
                request_digest_payload(
                    request_id=request_id,
                    tenant_id=access.tenant_id,
                    actor_principal_id=actor_principal_id,
                    delegated_principal_id=delegated_principal_id,
                    scope=entries,
                    reason=reason,
                    requested_by=requested_by,
                    requested_at=work.now,
                    validity_seconds=validity_seconds,
                )
            ).value
            values = dict(
                request_id=request_id,
                tenant_id=access.tenant_id,
                requested_by=requested_by,
                actor_principal_id=actor_principal_id,
                delegated_principal_id=delegated_principal_id,
                scope=entries,
                reason=reason[:1024],
                requested_validity_seconds=int(validity_seconds),
                requested_at=work.now,
                expires_at=expires_at,
                request_digest=digest,
                status="pending",
            )
            try:
                work.execute(sa.insert(delegation_request_table).values(**values))
            except ConstraintConflict:
                raise ContractViolation(
                    f"delegation request {request_id} already exists; reusing an "
                    "id would let an approval granted for one ask authorize "
                    "another"
                ) from None
            return DelegationRequestRecord(**values)

    def decide(
        self,
        context: Any,
        *,
        request_id: str,
        outcome: str,
        decided_by: str,
        approval_artifact_id: Optional[str] = None,
        approval_digest: Optional[str] = None,
        reason: Optional[str] = None,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Record one decision, once. ``False`` means somebody decided first.

        The pending predicate is the whole concurrency story: two approvers
        deciding at the same moment cannot both land, and the loser is told it
        lost rather than silently overwriting.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(delegation_request_table)
                .where(
                    delegation_request_table.c.request_id == request_id,
                    delegation_request_table.c.status == "pending",
                    *self._predicate(access),
                )
                .values(
                    status=outcome,
                    approved_by=decided_by,
                    approved_at=work.now,
                    approval_artifact_id=approval_artifact_id,
                    approval_digest=approval_digest,
                    decision_reason=(reason or "")[:1024] or None,
                )
            )
            return result.rowcount == 1

    def mark_issued(
        self,
        context: Any,
        *,
        request_id: str,
        delegation_id: str,
        unit: Optional[UnitOfWork] = None,
    ) -> bool:
        """Bind the grant back to the request it came from. Approved rows only.

        Conditional on the row still being approved and unissued, so a request
        cannot be issued twice: the second attempt finds it already issued and
        gets ``False``. Combined with the workflow doing this in the **same unit
        of work** as the grant insert, one approval produces at most one grant.
        """
        access = self._guard.authorize(StorageOperation.WRITE, context)
        with self._scope(unit) as work:
            result = work.execute(
                sa.update(delegation_request_table)
                .where(
                    delegation_request_table.c.request_id == request_id,
                    delegation_request_table.c.status == "approved",
                    delegation_request_table.c.issued_delegation_id.is_(None),
                    *self._predicate(access),
                )
                .values(status="issued", issued_delegation_id=delegation_id)
            )
            return result.rowcount == 1

    def find(
        self, context: Any, request_id: str, *, unit: Optional[UnitOfWork] = None
    ) -> Optional[DelegationRequestRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            row = work.execute(
                sa.select(delegation_request_table).where(
                    delegation_request_table.c.request_id == request_id,
                    *self._predicate(access),
                )
            ).mappings().first()
        if row is None:
            return None
        return DelegationRequestRecord(
            **{k: row[k] for k in DelegationRequestRecord.__slots__}
        )

    def pending(
        self, context: Any, *, limit: int = 50, unit: Optional[UnitOfWork] = None
    ) -> Sequence[DelegationRequestRecord]:
        access = self._guard.authorize(StorageOperation.READ, context)
        with self._scope(unit) as work:
            rows = work.execute(
                sa.select(delegation_request_table)
                .where(
                    delegation_request_table.c.status == "pending",
                    *self._predicate(access),
                )
                .order_by(delegation_request_table.c.requested_at)
                .limit(limit)
            ).mappings().all()
        return tuple(
            DelegationRequestRecord(
                **{k: row[k] for k in DelegationRequestRecord.__slots__}
            )
            for row in rows
        )

    def _predicate(self, access: Any) -> tuple:
        scope = self._guard.scope_filter(access)
        if scope is None:
            return ()
        column, value = scope
        return (delegation_request_table.c[column] == value,)

    def _scope(self, unit: Optional[UnitOfWork]):
        return enlisted(self._store, unit)


def _aware(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _iso(value: Any) -> Optional[str]:
    moment = _aware(value)
    return moment.isoformat() if moment else None
