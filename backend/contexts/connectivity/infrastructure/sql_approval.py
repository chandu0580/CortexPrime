"""The durable approval store — Phase 10.3 (ADR-096).

What this is, and what it deliberately is not
---------------------------------------------
CortexPrime has had an approval **contract** (``ApprovalFacts``), an approval
**port** (``ApprovalLookup``), and a gateway that re-checks approvals against the
action digest, since Phase 9. What it has never had is anywhere to keep one: the
only implementations of the port were ``NoApprovals``, which fails closed, and an
in-memory dictionary defined inside a harness.

That was survivable while approvals only ever existed inside a single harness
process. It is not survivable for a product, where a human approves in one HTTP
request and the execution reads that approval back in another.

So this module supplies **storage and a request/decide workflow**. It supplies no
judgement:

* whether an approval covers a request is still decided by
  ``ApprovalFacts.is_valid_for`` -- outcome, expiry, tenant, operation, digest;
* whether it covers *this exact action* is still decided by the gateway's
  comparison against the canonical approval digest (ADR-090).

Neither is reimplemented here, and this module must never grow a second opinion
about either. It reads rows and writes rows.

Where the digest comes from
---------------------------
``approval_digest`` is computed by the caller using the platform's own
``canonical_approval_digest``, from values the platform reconstructed. It is
never accepted from a client, and ``grant`` takes it as a **required argument**
rather than leaving it to be patched in afterwards -- Phase 9.9C had to reach
into a private attribute to bind one, which is exactly the kind of gap that hides
a defect until a real approval meets a real gateway.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import sqlalchemy as sa

from backend.contracts.approval import ApprovalOutcome
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import DurableStore
from backend.database.durable.tables import approval_table as T

__all__ = ["SqlApprovalRepository", "ApprovalPersistenceError", "ApprovalRecord"]

SCHEMA_VERSION = 1


class ApprovalPersistenceError(RuntimeError):
    """An approval could not be persisted (a genuine store failure)."""


class ApprovalRecord:
    """One stored approval, as the product presents it.

    A thin read model. It carries no method that decides anything -- the one
    piece of logic it has, :meth:`is_expired_at`, is a comparison the caller
    could do itself and is here only so the expiry field is not silently
    ignored by a projection that forgot about it.
    """

    __slots__ = (
        "approval_id", "tenant_id", "capability_ref", "capability_digest",
        "operation", "authorization_operation", "environment", "principal_id",
        "payload", "approval_digest",
        "outcome", "requested_by", "decided_by", "justification", "expires_at",
        "requested_at", "decided_at", "consumed_by_execution", "investigation_ref",
    )

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    def is_expired_at(self, moment: datetime) -> bool:
        return self.expires_at is not None and moment >= self.expires_at


def _aware(value: Any) -> Optional[datetime]:
    """Timestamps come back from some drivers without a zone. Treat a naive
    value as UTC rather than comparing it against an aware one and raising."""
    if not isinstance(value, datetime):
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class SqlApprovalRepository:
    """``ApprovalLookup`` over ``cp_approval``, plus the grant/deny workflow.

    ``find`` is the method authorization calls. Everything else exists so a
    human-facing product can create and decide approvals through one code path
    rather than several.
    """

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise ApprovalPersistenceError(
                "the approval repository requires a DurableStore")
        self._store = store

    # -- the port authorization depends on ---------------------------------

    def find(self, context: Any, artifact_id: str) -> Optional[Any]:
        """The ``ApprovalLookup`` port.

        Returns ``ApprovalFacts`` -- the existing contract -- so authorization
        is unchanged by the existence of this store. A row that cannot be read,
        or an id that does not exist, yields ``None``, which authorization
        already treats as "no approval", which refuses.

        Note what is NOT filtered here: the tenant. ``ApprovalFacts`` carries
        ``scope_tenant_id`` and ``is_valid_for`` refuses a mismatch, so filtering
        again in SQL would move a security decision out of the contract that
        owns it. The tenant is still enforced -- by the layer that is supposed
        to enforce it.
        """
        from backend.contexts.connectivity.application.authorization import (
            ApprovalFacts,
        )

        if not isinstance(artifact_id, str) or not artifact_id.strip():
            return None
        try:
            with self._store.atomic() as work:
                row = work.execute(
                    sa.select(
                        T.c.approval_id, T.c.outcome, T.c.capability_digest,
                        T.c.tenant_id, T.c.approval_digest,
                        T.c.authorization_operation, T.c.expires_at,
                        T.c.decided_by, T.c.consumed_by_execution,
                    ).where(T.c.approval_id == artifact_id)
                ).fetchone()
        except Exception:  # noqa: BLE001 - an unreadable store must not authorize
            return None
        if row is None:
            return None
        try:
            outcome = ApprovalOutcome(row[1])
        except ValueError:
            # An unrecognised outcome is not a grant. Fail closed rather than
            # guessing what a future value was supposed to mean.
            return None
        return ApprovalFacts(
            artifact_id=row[0],
            outcome=outcome,
            bound_digest=row[2],
            scope_tenant_id=row[3],
            bound_action_digest=row[4],
            # The AUTHORIZATION verb, which is what is_valid_for compares
            # against ``request.operation.value``. Returning the provider
            # operation here made every legitimate approval invalid.
            operation=row[5],
            expires_at=_aware(row[6]),
            # Phase 11.4 (ADR-124): who concluded it. Authorization uses this to
            # accept a delegated (policy-decided) approval only for a
            # compensable capability; the store still decides nothing.
            decided_by=row[7],
            # Phase 11.4 run 10: single use is now enforced by is_valid_for.
            consumed_by_execution=row[8],
        )

    # -- the workflow ------------------------------------------------------

    def request(
        self, *, approval_id: str, identity_digest: str, tenant_id: str,
        capability_ref: str, capability_digest: str, operation: str,
        authorization_operation: str, environment: str, principal_id: str,
        payload: dict,
        approval_digest: str, requested_by: str, expires_at: datetime,
        requested_at: datetime, investigation_ref: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> bool:
        """Record a PENDING approval request. Returns False if it already exists.

        ``requested_by`` must be a namespaced identity reference. The check is
        here as well as at the API boundary because this is the last place
        before the row is written, and an approval attributed to a bare username
        is an approval nobody can be held to.
        """
        if ":" not in (requested_by or ""):
            raise ApprovalPersistenceError(
                "an approval requester must be a namespaced identity reference")
        if not approval_digest:
            raise ApprovalPersistenceError(
                "an approval with no bound action digest would authorize "
                "anything this capability can do")
        try:
            with self._store.atomic() as work:
                work.execute(sa.insert(T).values(
                    approval_id=approval_id,
                    identity_digest=identity_digest,
                    tenant_id=tenant_id,
                    capability_ref=capability_ref,
                    capability_digest=capability_digest,
                    operation=operation,
                    authorization_operation=authorization_operation,
                    environment=environment,
                    principal_id=principal_id,
                    payload=dict(payload),
                    approval_digest=approval_digest,
                    # PENDING is not an ApprovalOutcome member, deliberately:
                    # the contract's members all describe a CONCLUDED request.
                    # A pending row must never look like a grant, and this
                    # string is not one any ApprovalOutcome parse accepts, so
                    # `find` returns None for it -- fail closed by construction.
                    outcome="pending",
                    requested_by=requested_by,
                    decided_by=None,
                    justification=justification,
                    expires_at=expires_at,
                    requested_at=requested_at,
                    decided_at=None,
                    consumed_by_execution=None,
                    investigation_ref=investigation_ref,
                    schema_version=SCHEMA_VERSION,
                ))
            return True
        except ConstraintConflict:
            return False
        except Exception as exc:  # a real store failure
            raise ApprovalPersistenceError(
                f"approval {approval_id} was not persisted: "
                f"{type(exc).__name__}") from exc

    def decide(
        self, *, approval_id: str, tenant_id: str, outcome: ApprovalOutcome,
        decided_by: str, decided_at: datetime,
        justification: Optional[str] = None,
    ) -> bool:
        """Grant or deny a PENDING request. Returns False if it was not pending.

        Tenant-scoped in SQL, and conditioned on ``outcome = 'pending'`` in the
        same statement. That condition is what makes a second decision on an
        already-decided approval a no-op rather than a race: two approvers
        clicking at once produce one decision, not a last-writer-wins overwrite
        of somebody else's judgement.
        """
        if ":" not in (decided_by or ""):
            raise ApprovalPersistenceError(
                "an approver must be a namespaced identity reference")
        if not isinstance(outcome, ApprovalOutcome):
            raise ApprovalPersistenceError("outcome must be an ApprovalOutcome")
        try:
            with self._store.atomic() as work:
                result = work.execute(
                    sa.update(T).where(
                        T.c.approval_id == approval_id,
                        T.c.tenant_id == tenant_id,
                        T.c.outcome == "pending",
                    ).values(
                        outcome=outcome.value,
                        decided_by=decided_by,
                        decided_at=decided_at,
                        justification=justification,
                    )
                )
            return bool(result.rowcount)
        except Exception as exc:  # noqa: BLE001
            raise ApprovalPersistenceError(
                f"approval {approval_id} was not decided: "
                f"{type(exc).__name__}") from exc

    def withdraw(self, *, approval_id: str, tenant_id: str,
                 decided_by: str, decided_at: datetime) -> bool:
        """Withdraw a granted approval. A revocation, through the same contract."""
        try:
            with self._store.atomic() as work:
                result = work.execute(
                    sa.update(T).where(
                        T.c.approval_id == approval_id,
                        T.c.tenant_id == tenant_id,
                    ).values(
                        outcome=ApprovalOutcome.WITHDRAWN.value,
                        decided_by=decided_by, decided_at=decided_at)
                )
            return bool(result.rowcount)
        except Exception as exc:  # noqa: BLE001
            raise ApprovalPersistenceError(
                f"approval {approval_id} was not withdrawn: "
                f"{type(exc).__name__}") from exc

    def mark_consumed(self, *, approval_id: str, tenant_id: str,
                      execution_ref: str) -> None:
        """Record which execution used this approval.

        Deliberately NOT a guard. Recording that an approval has been used makes
        a second use visible to an auditor; refusing the second use here would
        be this module inventing exactly-once, which the platform does not
        claim and this table does not get to decide.
        """
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.update(T).where(
                        T.c.approval_id == approval_id,
                        T.c.tenant_id == tenant_id,
                        T.c.consumed_by_execution.is_(None),
                    ).values(consumed_by_execution=execution_ref)
                )
        except Exception:  # noqa: BLE001 - an audit note must not fail a write
            return

    # -- reads -------------------------------------------------------------

    def get(self, *, tenant_id: str, approval_id: str) -> Optional[ApprovalRecord]:
        """One approval, only if it belongs to this tenant. Fails closed."""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(
                    T.c.approval_id == approval_id, T.c.tenant_id == tenant_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def get_by_identity(self, *, tenant_id: str,
                        identity_digest: str) -> Optional[ApprovalRecord]:
        """The approval a duplicate request collided with.

        The unique constraint that rejects a re-submitted request is on
        ``identity_digest``, so this is the only lookup that can be relied on to
        return *that* row. Matching on the approval digest instead would match
        any approval for the same action -- which, as this phase found the hard
        way, can be a different approval entirely with a different outcome.
        """
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(
                    T.c.identity_digest == identity_digest,
                    T.c.tenant_id == tenant_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def list_for_tenant(
        self, *, tenant_id: str, limit: int = 50,
        investigation_ref: Optional[str] = None,
        outcomes: Optional[tuple] = None,
        capability_ref: Optional[str] = None,
        operation: Optional[str] = None,
        requested_before: Optional[datetime] = None,
        requested_after: Optional[datetime] = None,
    ) -> tuple:
        """Approvals for one tenant, with server-side filters.

        The tenant predicate is applied FIRST and unconditionally; every filter
        below narrows that set and none can widen it. That ordering is the whole
        security property of a filtered list: a filter that could be evaluated
        before the tenant scope is a filter that can escape it.

        Filters are keyword-only and typed. There is no free-text predicate and
        no caller-supplied SQL fragment -- a queue that accepted one would be a
        query surface, not a projection.
        """
        with self._store.atomic() as work:
            stmt = sa.select(T).where(T.c.tenant_id == tenant_id)
            if investigation_ref:
                stmt = stmt.where(T.c.investigation_ref == investigation_ref)
            if outcomes:
                stmt = stmt.where(T.c.outcome.in_(tuple(outcomes)))
            if capability_ref:
                stmt = stmt.where(T.c.capability_ref == capability_ref)
            if operation:
                stmt = stmt.where(T.c.operation == operation)
            if requested_before is not None:
                stmt = stmt.where(T.c.requested_at <= requested_before)
            if requested_after is not None:
                stmt = stmt.where(T.c.requested_at >= requested_after)
            rows = work.execute(
                stmt.order_by(T.c.requested_at.desc()).limit(limit)
            ).mappings().fetchall()
        return tuple(self._record(r) for r in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar_one())

    @staticmethod
    def _record(row) -> ApprovalRecord:
        return ApprovalRecord(
            approval_id=row["approval_id"], tenant_id=row["tenant_id"],
            capability_ref=row["capability_ref"],
            capability_digest=row["capability_digest"],
            operation=row["operation"],
            authorization_operation=row["authorization_operation"],
            environment=row["environment"],
            principal_id=row["principal_id"], payload=row["payload"],
            approval_digest=row["approval_digest"], outcome=row["outcome"],
            requested_by=row["requested_by"], decided_by=row["decided_by"],
            justification=row["justification"],
            expires_at=_aware(row["expires_at"]),
            requested_at=_aware(row["requested_at"]),
            decided_at=_aware(row["decided_at"]),
            consumed_by_execution=row["consumed_by_execution"],
            investigation_ref=row["investigation_ref"],
        )
