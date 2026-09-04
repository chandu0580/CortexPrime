"""Leadership and fencing. Durable, monotonic, and enforced at the write.

What leadership is for, and what it is not
--------------------------------------------
It is for **singleton responsibilities**: the recovery sweep, the scheduler's
coordination, an outbox publisher that must not have twenty copies. One instance
holds the role, the others wait.

It is emphatically **not** a substitute for concurrency control. Ordinary work
dispatch scales horizontally on the durable queue, where a conditional claim
already makes exactly one instance the owner of each item. Electing a leader for
that would take a system that scales and make it a system with a bottleneck and a
failover gap.

The rule is: elect a leader where the work must happen *once*, and use the queue
where the work must happen *once per item*.

The fencing token, and why it is a counter
--------------------------------------------
The failure this exists to prevent:

    Instance A acquires the role, token 41
    A stalls -- GC pause, network partition, a suspended VM
    A's lease expires
    Instance B acquires the role, token 42
    A wakes up believing it is still the leader
    A writes

Without a fence, A's write lands and two leaders have both acted. The Python-side
check "am I still the leader?" cannot close this: A *was* the leader when it
checked, and the stall happens between the check and the write.

So the token is carried into the durable mutation and the **database** rejects
it: ``WHERE fencing_token = :token`` no longer matches once B has taken the role.
The gap between checking and writing stops mattering because there is no check —
there is one conditional write.

The token is a counter on a row that outlives every leader, incremented in place
on each acquisition. That is what makes it monotonic. A UUID has no order, so it
cannot answer "which of these two writers is newer"; a timestamp has an order two
machines disagree about, which is the same problem wearing a number.

Leadership expires, and a heartbeat does not renew authority indefinitely
--------------------------------------------------------------------------
``heartbeat`` extends ``expires_at`` by the *original* lease duration from the
current moment — a bounded extension, granted only to the instance that still
holds the token. It is not "keep going forever because you are still alive": a
leader that is alive but wedged stops heartbeating, and a leader that is
partitioned has its extension refused by the same fence that refuses its writes.

A dead leader therefore becomes replaceable after one lease period, without
anybody intervening.

Losing leadership is not losing execution authority
-----------------------------------------------------
See ``LeadershipHandle.lost``. A scheduler that loses the role stops *scheduling*.
It does not kill workers, rewrite execution state, conclude attempts or cancel
anything — active work is governed by its own execution lease, which this has no
opinion about. Leadership coordinates; it does not execute.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.contracts.errors import ContractViolation
from backend.database.durable.errors import ConstraintConflict
from backend.database.durable.session import (
    DurableStore,
    NoDurableStore,
    UnitOfWork,
    enlisted,
)
from backend.database.durable.tables import PLATFORM_SCOPE, leadership_table

__all__ = [
    "LeadershipRole",
    "LeadershipStatus",
    "LeadershipHandle",
    "LeadershipLost",
    "StaleFencingToken",
    "SqlLeadershipStore",
]

log = logging.getLogger(__name__)


class LeadershipRole(str, Enum):
    """The singleton responsibilities. Deliberately a closed list.

    Each one is here because it must happen *once*, not once per item. Anything
    that can be expressed as "once per item" belongs on the queue instead, and a
    role added here without that argument is a bottleneck somebody introduced by
    habit.
    """

    RECOVERY_SWEEP = "recovery_sweep"
    """Scanning every unfinished run after a restart. Twenty instances doing it
    concurrently would produce twenty recovery plans for one execution."""

    OUTBOX_PUBLISHER = "outbox_publisher"
    """Coordinating publication. The *claim* is already exclusive per entry, so
    this is not what makes publication safe -- it bounds how many publishers
    compete, which is an operational choice rather than a correctness one."""

    AUDIT_WRITER = "audit_writer"
    """Appending to the audit chain. A hash chain has exactly one tail, so two
    writers interleaving produce a chain that verifies as neither -- demonstrated
    in Phase 5.10, where two processes each believed they wrote 20 records and
    the result carried broken links, missing records and an orphan origin.

    Note what this role can and cannot do, because the difference matters: it
    designates **which runtime is admitted to write**. It does not fence the
    filesystem append itself. ``fenced_where`` composes a token check into a SQL
    statement, and a file append cannot join that predicate -- see ADR-054."""

    SCHEDULER = "scheduler"
    """Deciding when to look for work and enqueuing what is ready. Several
    instances enqueuing concurrently is harmless (the queue's primary key
    deduplicates) but wasteful, and the recovery-driven target list must be
    computed once."""

    WORLD_WATCH = "world_watch"
    """Advancing a provider observation stream — Phase 9.3 (ADR-083).

    Here because it is the "once", not the "once per item" case, and for a
    reason specific to what a stream is: the position is a *single* place in a
    provider's history, and two processes advancing it independently both read
    from the same point and both move it forward. Neither is wrong about any
    single window; together they produce a position that skips whatever the
    other one consumed. There is no per-item claim to express that as, because
    the item does not exist until the position is used to fetch it.

    Scoped to the tenant, like every tenant-scoped role. That is deliberately
    coarser than one holder per (tenant, provider, resource): the phase exposes
    one stream per tenant, and encoding a compound identity into ``scope`` would
    break the property that makes ``scope`` safe — that it is a tenant id or the
    platform sentinel, and nothing a caller can shape into either.

    Note what a lost lease does and does not mean, as with every other role: a
    watcher that loses it stops *advancing the stream*. Observations already
    recorded are immutable and stay; the successor resumes from the last
    position that was durably written, and re-reads whatever was in flight.
    That is at-least-once, which is what this system claims."""


class LeadershipStatus(str, Enum):
    HELD = "held"
    RELEASED = "released"
    VACANT = "vacant"
    """No instance has ever held it, or the row was created ahead of the first
    election. Distinct from ``RELEASED`` so "nobody has taken this yet" and
    "somebody gave it back" stay different facts."""


class LeadershipLost(ContractViolation):
    """This instance no longer holds the role, and its action was refused."""

    def __init__(self, *, role: str, instance_id: str) -> None:
        super().__init__(
            f"instance {instance_id} no longer holds {role}; the operation is "
            "refused rather than performed by a second leader"
        )
        self.role = role
        self.instance_id = instance_id


class StaleFencingToken(ContractViolation):
    """A write arrived carrying a token the durable record has moved past.

    The process that sent it believed it was the leader. It was, once. This is
    the refusal that makes that belief harmless.
    """

    def __init__(self, *, role: str, presented: int, current: int) -> None:
        super().__init__(
            f"fencing token {presented} for {role} is stale; the role is now at "
            f"{current}. The write is refused -- a stalled process that woke up "
            "believing it is still the leader must not be able to act"
        )
        self.role = role
        self.presented = presented
        self.current = current


@dataclass(frozen=True)
class LeadershipHandle:
    """Proof of leadership at a moment, and the token that makes it checkable.

    Frozen. A handle that could be mutated would be a handle whose token could be
    raised by the process holding it, which is the whole thing being prevented.
    """

    role: LeadershipRole
    scope: str
    instance_id: str
    fencing_token: int
    acquired_at: datetime
    expires_at: datetime

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "scope": self.scope,
            "instance_id": self.instance_id,
            "fencing_token": self.fencing_token,
            "acquired_at": self.acquired_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }


class SqlLeadershipStore:
    """Durable leader election with monotonic fencing. One row per role."""

    #: Counters, through the existing metrics port.
    METRICS = (
        "leader.acquired",
        "leader.lost",
        "leader.heartbeat",
        "leader.contended",
        "fencing.rejected",
    )

    def __init__(
        self,
        store: DurableStore,
        *,
        instance_id: str,
        metrics: Optional[Any] = None,
    ) -> None:
        if not isinstance(store, DurableStore):
            raise NoDurableStore("durable leadership requires a store")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ContractViolation(
                "an instance must identify itself to take a role; an anonymous "
                "leader cannot be told apart from its own restart"
            )
        self._store = store
        self._instance_id = instance_id.strip()
        self._metrics = metrics

    @property
    def instance_id(self) -> str:
        return self._instance_id

    # ------------------------------------------------------------------
    # Election
    # ------------------------------------------------------------------

    def acquire(
        self,
        *,
        role: LeadershipRole,
        lease_seconds: int,
        scope: str = PLATFORM_SCOPE,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[LeadershipHandle]:
        """Take the role if it is free, or return ``None``. Never blocks.

        ``None`` is the ordinary answer for a follower and must not be an
        exception: in a fleet of ten, nine get it every cycle.

        The election is one conditional ``UPDATE``. Two instances arriving
        together cannot both match ``status != held OR expires_at <= now``,
        because the first one's update makes the predicate false for the second.
        There is no read-then-write and therefore no window.
        """
        if lease_seconds < 1:
            raise ContractViolation("a leadership lease must last at least a second")
        with enlisted(self._store, unit) as work:
            now = work.now
            expires = now + timedelta(seconds=lease_seconds)
            self._ensure_row(work, role, scope)

            result = work.execute(
                sa.update(leadership_table)
                .where(
                    leadership_table.c.scope == scope,
                    leadership_table.c.role == role.value,
                    sa.or_(
                        leadership_table.c.status != LeadershipStatus.HELD.value,
                        leadership_table.c.expires_at.is_(None),
                        leadership_table.c.expires_at <= now,
                        # Re-acquiring a role this instance already holds is
                        # legitimate: it is how a leader that restarted quickly
                        # resumes, and it still advances the token so anything
                        # the previous incarnation had in flight is fenced out.
                        leadership_table.c.instance_id == self._instance_id,
                    ),
                )
                .values(
                    instance_id=self._instance_id,
                    # Monotonic, in place, on a row that outlives every leader.
                    fencing_token=leadership_table.c.fencing_token + 1,
                    acquired_at=now,
                    heartbeat_at=now,
                    expires_at=expires,
                    released_at=None,
                    status=LeadershipStatus.HELD.value,
                )
            )
            if result.rowcount != 1:
                self._count("leader.contended", role)
                return None

            token = work.execute(
                sa.select(leadership_table.c.fencing_token).where(
                    leadership_table.c.scope == scope,
                    leadership_table.c.role == role.value,
                )
            ).scalar()

        self._count("leader.acquired", role)
        log.info(
            "instance %s acquired %s with fencing token %s",
            self._instance_id,
            role.value,
            token,
        )
        return LeadershipHandle(
            role=role,
            scope=scope,
            instance_id=self._instance_id,
            fencing_token=int(token),
            acquired_at=now,
            expires_at=expires,
        )

    def heartbeat(
        self,
        handle: LeadershipHandle,
        *,
        lease_seconds: int,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[LeadershipHandle]:
        """Extend the lease by one bounded period, if still the holder.

        Fenced: the update matches on ``fencing_token``, so an instance whose
        role was taken while it was stalled cannot extend anything. ``None`` back
        means leadership was lost — the caller stops coordinating and does *not*
        touch running work.

        The extension is bounded and repeated rather than open-ended. A leader
        that is alive but wedged stops calling this and lapses; one that is
        partitioned has this refused by the same fence that refuses its writes.
        """
        with enlisted(self._store, unit) as work:
            now = work.now
            expires = now + timedelta(seconds=lease_seconds)
            result = work.execute(
                sa.update(leadership_table)
                .where(
                    leadership_table.c.scope == handle.scope,
                    leadership_table.c.role == handle.role.value,
                    leadership_table.c.instance_id == handle.instance_id,
                    leadership_table.c.fencing_token == handle.fencing_token,
                    leadership_table.c.status == LeadershipStatus.HELD.value,
                )
                .values(heartbeat_at=now, expires_at=expires)
            )
        if result.rowcount != 1:
            self._count("leader.lost", handle.role)
            log.warning(
                "instance %s lost %s; it stops coordinating and leaves running "
                "work to its own execution leases",
                handle.instance_id,
                handle.role.value,
            )
            return None
        self._count("leader.heartbeat", handle.role)
        from dataclasses import replace

        return replace(handle, expires_at=expires)

    def release(
        self, handle: LeadershipHandle, *, unit: Optional[UnitOfWork] = None
    ) -> bool:
        """Give the role back so a successor need not wait for the expiry.

        The token is **not** advanced here. Releasing is not an act that
        invalidates in-flight writes from this leader — it is this leader saying
        it has finished, and its own writes up to that point were legitimate. The
        next acquisition advances the token, which is where fencing belongs.
        """
        with enlisted(self._store, unit) as work:
            result = work.execute(
                sa.update(leadership_table)
                .where(
                    leadership_table.c.scope == handle.scope,
                    leadership_table.c.role == handle.role.value,
                    leadership_table.c.instance_id == handle.instance_id,
                    leadership_table.c.fencing_token == handle.fencing_token,
                )
                .values(
                    status=LeadershipStatus.RELEASED.value,
                    released_at=work.now,
                    expires_at=work.now,
                )
            )
        return result.rowcount == 1

    # ------------------------------------------------------------------
    # Fencing
    # ------------------------------------------------------------------

    def assert_current(
        self, handle: LeadershipHandle, *, unit: Optional[UnitOfWork] = None
    ) -> None:
        """Refuse if this handle is no longer the current leadership.

        **Advisory, and deliberately labelled as such.** It reads the row and
        compares; a stall between this call and a subsequent write is exactly the
        gap it cannot close. Real fencing is ``fenced_where`` below, carried into
        the write itself.

        It exists for the case where there is nothing to fence — deciding whether
        to *start* a sweep, say — and for producing a clear error early rather
        than a silent zero-rowcount later.
        """
        with enlisted(self._store, unit) as work:
            row = work.execute(
                sa.select(
                    leadership_table.c.instance_id,
                    leadership_table.c.fencing_token,
                    leadership_table.c.status,
                    leadership_table.c.expires_at,
                ).where(
                    leadership_table.c.scope == handle.scope,
                    leadership_table.c.role == handle.role.value,
                )
            ).mappings().first()
            now = work.now
        if row is None:
            raise LeadershipLost(role=handle.role.value, instance_id=handle.instance_id)
        if int(row["fencing_token"]) != handle.fencing_token:
            self._count("fencing.rejected", handle.role)
            raise StaleFencingToken(
                role=handle.role.value,
                presented=handle.fencing_token,
                current=int(row["fencing_token"]),
            )
        if (
            row["instance_id"] != handle.instance_id
            or row["status"] != LeadershipStatus.HELD.value
            or row["expires_at"] is None
            or _aware(row["expires_at"]) <= now
        ):
            raise LeadershipLost(role=handle.role.value, instance_id=handle.instance_id)

    @staticmethod
    def fenced_where(handle: LeadershipHandle) -> tuple:
        """The predicate a leader-only write must carry. **This is the fence.**

        Composed into the caller's own ``UPDATE`` so the token check and the
        mutation are one statement against one row set. A stalled instance's
        write finds no matching row and changes nothing — no Python check runs,
        so no Python check can be stale.

        Used with a correlated subquery so it composes with any table::

            stmt = sa.update(t).where(t.c.id == x, *fenced_subquery(handle))
        """
        return (
            leadership_table.c.scope == handle.scope,
            leadership_table.c.role == handle.role.value,
            leadership_table.c.instance_id == handle.instance_id,
            leadership_table.c.fencing_token == handle.fencing_token,
            leadership_table.c.status == LeadershipStatus.HELD.value,
        )

    @staticmethod
    def fenced_exists(handle: LeadershipHandle):
        """A correlated ``EXISTS`` carrying the fence, for composing into a write.

        The form that actually gets used: a caller updating ``cp_queue`` cannot
        add a predicate on ``cp_leadership`` directly, so the fence travels as a
        subquery evaluated inside the same statement. Same guarantee, no join.
        """
        return sa.exists(
            sa.select(sa.literal(1)).where(*SqlLeadershipStore.fenced_where(handle))
        )

    # ------------------------------------------------------------------
    # Observation
    # ------------------------------------------------------------------

    def current(
        self,
        *,
        role: LeadershipRole,
        scope: str = PLATFORM_SCOPE,
        unit: Optional[UnitOfWork] = None,
    ) -> Optional[dict]:
        """Who holds the role, for an operator and for a readiness report."""
        with enlisted(self._store, unit) as work:
            row = work.execute(
                sa.select(leadership_table).where(
                    leadership_table.c.scope == scope,
                    leadership_table.c.role == role.value,
                )
            ).mappings().first()
            now = work.now
        if row is None:
            return None
        expires = _aware(row["expires_at"])
        return {
            "role": row["role"],
            "scope": row["scope"],
            "instance_id": row["instance_id"],
            "fencing_token": int(row["fencing_token"]),
            "status": row["status"],
            "live": (
                row["status"] == LeadershipStatus.HELD.value
                and expires is not None
                and now < expires
            ),
            "acquired_at": row["acquired_at"],
            "heartbeat_at": row["heartbeat_at"],
            "expires_at": row["expires_at"],
        }

    def roles(self, *, scope: str = PLATFORM_SCOPE) -> Sequence[dict]:
        return tuple(
            entry
            for entry in (self.current(role=role, scope=scope) for role in LeadershipRole)
            if entry is not None
        )

    # ------------------------------------------------------------------

    def _ensure_row(self, work: UnitOfWork, role: LeadershipRole, scope: str) -> None:
        """Create the role's row once. The token starts at zero and only rises.

        Idempotent by primary key: two instances racing to create it produce one
        row and one loser, and the loser's collision is not an error — it means
        the row it wanted exists, which is what it wanted.
        """
        try:
            # Savepointed. The collision is the ordinary path -- after the first
            # election the row always exists -- and on PostgreSQL a failed
            # statement aborts the whole transaction, so the acquisition UPDATE
            # that follows this call would raise 25P02 and every election after
            # the first would fail. On SQLite it worked, which is why no phase
            # before this one saw it.
            with work.attempt():
                work.execute(
                    sa.insert(leadership_table).values(
                        scope=scope,
                        role=role.value,
                        instance_id=None,
                        fencing_token=0,
                        status=LeadershipStatus.VACANT.value,
                    )
                )
        except ConstraintConflict:
            return

    def _count(self, name: str, role: LeadershipRole) -> None:
        if self._metrics is None or name not in self.METRICS:
            return
        try:
            self._metrics.increment(
                name, labels={"role": role.value, "instance": self._instance_id}
            )
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("leadership metric failed", exc_info=False)


def _aware(value: Any) -> Optional[datetime]:
    """Restore UTC awareness to a timestamp a driver returned naive.

    SQLite has no timezone type. Comparing a naive value against an aware clock
    reading raises, and the comparison it would have made is a leadership-expiry
    decision — so the repair happens here rather than at each call site.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
