"""Recovery over durable lease state. **No second recovery policy.**

What this is, precisely
-------------------------
``RecoveryCoordinator`` (Phase 3.4) decides. It reads a run, asks
``plan_recovery``, and produces a ``RecoveryPlan``. It has always been correct
and it is untouched here.

What it could not do before Phase 5.1 was see the durable truth about *leases*.
Its notion of an expired lease came from the aggregate, which is what the last
process happened to write down — so after a crash it was reasoning from a
snapshot rather than from what is actually held.

This connects the two. It reads the durable lease store, classifies each lease,
and hands the coordinator's decision the facts it needs. It **adds no policy**:
there is no branch here that decides to retry, to compensate, or to fail a run,
and there could not be — this module never calls ``plan_recovery`` and has no
access to the retry rules.

    durable lease state  →  this  →  RecoveryCoordinator.plan  →  a decision
                                     (the existing policy, unchanged)

Ambiguity is preserved, and never resolved by guessing
--------------------------------------------------------
Phase 5.1's ``AMBIGUOUS`` means: the lease expired, and its holder was
heartbeating recently enough that it may still be running. Reclaiming it would
run the node twice; refusing forever would strand it.

So an ambiguous lease is **never automatically reclaimed**. It becomes a durable
recovery decision that a person resolves, exactly as an ambiguous *outcome*
does. That is the whole reason the fourth lease state exists, and turning it into
a timeout would throw the distinction away.

Reclaiming is one transaction
-------------------------------
A reclaim invalidates the old ownership, advances the fence, and establishes the
new lease in a single unit. Doing it as read → decide → write would leave a
window where the old holder's heartbeat could revive a lease this process had
already decided to take.

The reclaim is also **fenced**: only the instance holding the recovery role may
perform one, and the fence travels into the write rather than being checked
before it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.contexts.execution.application.metrics import NullMetrics, SafeMetrics
from backend.contexts.execution.domain.invocation import Clock, SystemClock
from backend.contexts.execution.domain.recovery import RecoveryAction

__all__ = [
    "LeaseFinding",
    "DurableRecoveryReport",
    "DurableLeaseRecovery",
    "RECOVERY_METRICS",
]

log = logging.getLogger(__name__)

RECOVERY_METRICS = (
    "recovery.scan",
    "recovery.reclaim",
    "recovery.ambiguous",
    "recovery.refused",
)


@dataclass(frozen=True)
class LeaseFinding:
    """One durable lease, and what recovery may do about it. A fact.

    ``reclaimable`` is the *lease store's* answer about the lease, not a
    permission to act: the recovery policy still has to agree that the node it
    belongs to may be retried at all.
    """

    execution_id: str
    node_id: str
    worker_id: str
    lease_id: str
    state: str
    reclaimable: bool
    fence: int
    expires_at: Optional[datetime] = None
    heartbeat_at: Optional[datetime] = None

    @property
    def is_ambiguous(self) -> bool:
        return self.state == "ambiguous"

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "worker_id": self.worker_id,
            "lease_id": self.lease_id,
            "state": self.state,
            "reclaimable": self.reclaimable,
            "fence": self.fence,
        }


@dataclass(frozen=True)
class DurableRecoveryReport:
    """What one recovery sweep found and did. Never what it concluded."""

    at: datetime
    scanned: int = 0
    findings: tuple = ()
    reclaimed: tuple = ()
    ambiguous: tuple = ()
    refused: tuple = ()
    skipped: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "at": self.at.isoformat(),
            "scanned": self.scanned,
            "reclaimed": list(self.reclaimed),
            "ambiguous": [f.to_dict() for f in self.ambiguous],
            "refused": list(self.refused),
            "skipped": self.skipped,
            "reason": self.reason,
        }


class DurableLeaseRecovery:
    """Connects durable leases to the existing recovery policy. Adds no policy."""

    def __init__(
        self,
        *,
        coordinator: Any,
        leases: Any,
        executions: Any,
        leadership: Optional[Any] = None,
        readiness: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Clock] = None,
        ambiguity_seconds: int = 30,
    ) -> None:
        self._coordinator = coordinator
        self._leases = leases
        self._executions = executions
        self._leadership = leadership
        self._readiness = readiness
        self._metrics = SafeMetrics(metrics or NullMetrics())
        self._clock = clock or SystemClock()
        self._ambiguity_seconds = ambiguity_seconds
        """How recently a heartbeat must have landed for an expired lease to be
        ambiguous rather than simply expired. A **classification** input, not a
        policy: it decides which question recovery is asked, never what the
        answer is."""

    # ------------------------------------------------------------------

    def scan(self, context: Any, *, limit: int = 100) -> DurableRecoveryReport:
        """Classify every durable lease whose holder may be gone. Acts on none.

        Read-only, deliberately. What comes back is a set of findings; deciding
        what to do about them is the coordinator's, and doing it is
        ``reclaim``'s — kept apart so an operator can look without a look
        changing anything.
        """
        now = self._clock.now()
        if not self._ready():
            return DurableRecoveryReport(
                at=now, skipped=True, reason="durability_unavailable"
            )

        try:
            rows = self._leases.reclaimable(context, limit=limit)
        except Exception:  # noqa: BLE001 - unreadable state is not empty state
            log.warning("durable lease scan failed", exc_info=False)
            return DurableRecoveryReport(at=now, skipped=True, reason="scan_failed")

        findings: list = []
        for row in rows:
            state = self._leases.state_of(
                context,
                execution_id=row["execution_id"],
                node_id=row["node_id"],
                ambiguity_seconds=self._ambiguity_seconds,
            )
            if state is None:
                continue
            findings.append(
                LeaseFinding(
                    execution_id=state["execution_id"],
                    node_id=state["node_id"],
                    worker_id=state["worker_id"],
                    lease_id=state["lease_id"],
                    state=state["state"],
                    reclaimable=bool(state["reclaimable"]),
                    fence=int(state["fence"]),
                    expires_at=state.get("expires_at"),
                    heartbeat_at=state.get("heartbeat_at"),
                )
            )

        ambiguous = tuple(f for f in findings if f.is_ambiguous)
        self._metrics.increment("recovery.scan", value=len(findings), labels={})
        if ambiguous:
            self._metrics.increment(
                "recovery.ambiguous", value=len(ambiguous), labels={}
            )
            log.warning(
                "%d lease(s) are ambiguous: expired, but their holder was "
                "heartbeating recently. They are left for a decision rather "
                "than reclaimed -- reclaiming one would run the node twice",
                len(ambiguous),
            )
        return DurableRecoveryReport(
            at=now,
            scanned=len(findings),
            findings=tuple(findings),
            ambiguous=ambiguous,
        )

    # ------------------------------------------------------------------

    def reclaim(
        self,
        context: Any,
        finding: LeaseFinding,
        *,
        worker_id: str,
        lease_id: str,
        seconds: int,
        handle: Optional[Any] = None,
        unit: Optional[Any] = None,
    ) -> bool:
        """Take over one lease, **only if the existing policy permits it**.

        Three gates, in order, and all three must agree:

        1. the lease store says the lease is finished — released or expired;
        2. it is not ambiguous;
        3. ``RecoveryCoordinator.plan`` — the *existing* policy — returns an
           action that permits resuming this run.

        The third is the load-bearing one. This module has no opinion about
        whether a node may be retried; it asks the component that does, and
        refuses on anything other than an explicit resume or retry. A
        ``COMPENSATE`` or ``FAIL_EXECUTION`` decision is not a reclaim, and
        turning one into a reclaim here would be inventing retry behaviour.
        """
        if finding.is_ambiguous:
            self._metrics.increment("recovery.refused", labels={"reason": "ambiguous"})
            return False
        if not finding.reclaimable:
            self._metrics.increment("recovery.refused", labels={"reason": "held"})
            return False

        if handle is not None and self._leadership is not None:
            # Fenced. A process that lost the recovery role while deciding must
            # not be able to reclaim on the strength of that decision.
            try:
                self._leadership.assert_current(handle)
            except Exception:  # noqa: BLE001
                self._metrics.increment("recovery.refused", labels={"reason": "fenced"})
                log.warning(
                    "a reclaim was refused because this instance no longer holds "
                    "the recovery role"
                )
                return False

        if not self._policy_permits(context, finding):
            self._metrics.increment("recovery.refused", labels={"reason": "policy"})
            return False

        try:
            # One transaction: the old ownership is invalidated and the new lease
            # established together, and the fence advances as part of it. Read →
            # decide → write would leave a window in which the old holder's
            # heartbeat revives a lease already given away.
            self._leases.acquire(
                context,
                execution_id=finding.execution_id,
                node_id=finding.node_id,
                worker_id=worker_id,
                lease_id=lease_id,
                seconds=seconds,
                unit=unit,
            )
        except Exception as exc:  # noqa: BLE001
            # Somebody else took it between the scan and here. Refused, not
            # forced: two reclaimers must not both succeed.
            self._metrics.increment("recovery.refused", labels={"reason": "raced"})
            log.info(
                "reclaim of %s/%s lost a race (%s)",
                finding.execution_id,
                finding.node_id,
                type(exc).__name__,
            )
            return False

        self._metrics.increment("recovery.reclaim", labels={})
        log.info(
            "reclaimed %s/%s from %s; fence advanced past %s",
            finding.execution_id,
            finding.node_id,
            finding.worker_id,
            finding.fence,
        )
        return True

    # ------------------------------------------------------------------

    def _policy_permits(self, context: Any, finding: LeaseFinding) -> bool:
        """Ask the **existing** recovery policy. Never decide here.

        Loads the run and calls ``RecoveryCoordinator.plan``, which is the same
        call startup recovery makes. Anything other than an automatic resume or
        retry is a refusal — including a decision this module does not
        recognise, because an unrecognised action is not a permission.
        """
        from backend.contexts.execution.application.commands import GetExecution

        try:
            execution = self._executions.get(
                context, GetExecution(execution_id=finding.execution_id)
            )
        except Exception:  # noqa: BLE001 - an unreadable run is not a resumable one
            log.warning(
                "could not load execution %s to plan a reclaim", finding.execution_id
            )
            return False

        try:
            plan = self._coordinator.plan(context, execution)
        except Exception:  # noqa: BLE001
            log.warning("recovery planning failed for %s", finding.execution_id)
            return False

        return bool(plan.is_automatic) and plan.action in (
            RecoveryAction.RESUME_FROM_CHECKPOINT,
            RecoveryAction.RETRY_ATTEMPT,
        )

    def _ready(self) -> bool:
        if self._readiness is None:
            return True
        try:
            return bool(self._readiness.is_ready())
        except Exception:  # noqa: BLE001
            return False
