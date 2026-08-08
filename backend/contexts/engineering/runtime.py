"""The Engineering Runtime service.

Executes the Engineering Constitution's lifecycle. It orchestrates; it never
implements, reviews, or verifies anything itself -- those belong to contexts
reached through ports.

Ordering, and why it is what it is
----------------------------------
Every transition runs::

    1. acquire the per-WorkOrder lock
    2. read the current snapshot through the port
    3. check legality and the caller's precondition      -- nothing has happened yet
    4. check the collaborator for the target phase exists
    5. run policy
    6. ask the collaborator to begin (review request, bundle assembly)
    7. move the WorkOrder through the port
    8. record events in the log
    9. release the lock
    10. drain the dispatcher

Steps 1-5 change nothing, so a refusal there needs no rollback -- there is
nothing to undo. Step 6 is the first that can leave a trace elsewhere, and step 7
is the first that changes state.

**Rollback** covers the window between 6 and 8. If step 7 raises after step 6
succeeded, the collaborator was told to start work that will not happen; the
runtime records a rollback event so the log says so, and re-raises wrapped in
:class:`TransitionRolledBack` with the original cause attached. If step 8 raised
after 7 succeeded the state would be changed with no record -- so the append
happens inside the lock and before the lock is released, and a failure there
attempts to move the WorkOrder back.

**Dispatch is outside the transition entirely** (step 10). Delivery cannot fail a
transition, because the events are already in the log; a subscriber that raises
delays delivery rather than losing it. That is the outbox pattern, and it is the
only arrangement where "state changed" and "events emitted" cannot disagree.

**Concurrency** is a per-WorkOrder reentrant lock plus an optional
``expected_phase`` precondition. The lock stops two transitions interleaving
their read-modify-write; the precondition stops a command composed against a
stale read from being applied to a state its author never saw. Both, because the
lock alone does not help a caller that read the snapshot before acquiring it.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.engineering.errors import (
    ConcurrentModification,
    TransitionRolledBack,
    WorkOrderUnknown,
)
from backend.contexts.engineering.event_log import (
    EngineeringEventDispatcher,
    EngineeringEventLog,
)
from backend.contexts.engineering.events import (
    AGGREGATE_TYPE,
    ImplementationCompleted,
    ImplementationStarted,
    ReviewCompleted,
    ReviewRequested,
    VerificationCompleted,
    VerificationRequested,
)
from backend.contexts.engineering.lifecycle import Collaborators, WorkOrderLifecycleManager
from backend.contexts.engineering.policy import EngineeringPolicy, default_policy
from backend.contexts.engineering.ports import WorkOrderPhase, WorkOrderSnapshot
from backend.contexts.engineering.state_executor import (
    StateMachineExecutor,
    TransitionDecision,
    coerce_phase,
)
from backend.platform.events import EventMetadata

__all__ = ["EngineeringRuntime", "TransitionResult"]


@dataclass(frozen=True)
class TransitionResult:
    """What a transition produced."""

    snapshot: WorkOrderSnapshot
    decision: TransitionDecision
    events: tuple
    advisory: tuple = ()

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class EngineeringRuntime:
    """Executes WorkOrder lifecycle transitions."""

    def __init__(
        self,
        collaborators: Collaborators,
        *,
        policy: Optional[EngineeringPolicy] = None,
        log: Optional[EngineeringEventLog] = None,
    ) -> None:
        self._collaborators = collaborators
        self._lifecycle = WorkOrderLifecycleManager(collaborators)
        self._executor = StateMachineExecutor(policy or default_policy())
        self._log = log or EngineeringEventLog()
        self._dispatcher = EngineeringEventDispatcher(self._log)
        self._locks: dict = defaultdict(threading.RLock)
        self._lock_table_guard = threading.Lock()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def log(self) -> EngineeringEventLog:
        return self._log

    @property
    def dispatcher(self) -> EngineeringEventDispatcher:
        return self._dispatcher

    @property
    def lifecycle(self) -> WorkOrderLifecycleManager:
        return self._lifecycle

    @property
    def executor(self) -> StateMachineExecutor:
        return self._executor

    def _lock_for(self, work_id: str) -> threading.RLock:
        with self._lock_table_guard:
            return self._locks[work_id]

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, work_id: str, **attributes: Any) -> EventMetadata:
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=work_id,
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
            attributes=attributes or None,
        )

    def _count(self, work_id: str, event_type: str) -> int:
        return sum(
            1 for entry in self._log.for_work_order(work_id) if entry.event_type == event_type
        )

    def round_number(self, work_id: str) -> int:
        """The implementation round currently in flight.

        Derived from the log rather than counted in memory: an in-memory counter
        disagrees with the log the moment the process restarts, and the log is
        authoritative.

        Distinct from :meth:`next_round`, and conflating the two is a real bug --
        entering review must report the round that just *finished*, not the one
        that would start next.
        """
        return max(self._count(work_id, ImplementationStarted.EVENT_TYPE), 1)

    def next_round(self, work_id: str) -> int:
        """The round about to begin."""
        return self._count(work_id, ImplementationStarted.EVENT_TYPE) + 1

    def attempt_number(self, work_id: str) -> int:
        """The verification attempt currently in flight."""
        return max(self._count(work_id, VerificationRequested.EVENT_TYPE), 1)

    def next_attempt(self, work_id: str) -> int:
        return self._count(work_id, VerificationRequested.EVENT_TYPE) + 1

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def snapshot(self, context: Any, work_id: str) -> WorkOrderSnapshot:
        found = self._collaborators.work_order.snapshot(context, work_id)
        if found is None:
            raise WorkOrderUnknown(work_id)
        return found

    # ------------------------------------------------------------------
    # The transition
    # ------------------------------------------------------------------

    def transition(
        self,
        context: Any,
        work_id: str,
        to_phase: Any,
        *,
        actor: str,
        expected_phase: Optional[Any] = None,
    ) -> TransitionResult:
        """Move a WorkOrder, or refuse. See the module docstring for ordering."""
        if not actor or not isinstance(actor, str) or not actor.strip():
            raise ContractViolation("actor is required; a transition is an act by someone")

        target = coerce_phase(to_phase)

        with self._lock_for(work_id):
            snapshot = self.snapshot(context, work_id)

            # Nothing has happened yet -- a refusal here needs no rollback.
            decision = self._executor.decide(
                snapshot, target, context, expected_phase=expected_phase
            )
            self._lifecycle.require_collaborator_for(target)

            # First step that can leave a trace outside this runtime.
            side_effects = self._begin_phase(context, snapshot, target)

            try:
                moved = self._collaborators.work_order.transition(
                    context, work_id, target, actor
                )
            except Exception as exc:
                self._record_rollback(context, snapshot, target, exc)
                raise TransitionRolledBack(
                    work_id=work_id, transition=decision.label, cause=exc
                ) from exc

            if moved.phase is not target:
                # The port reported a phase other than the one requested. Treat
                # it as a race rather than trusting either value: something else
                # moved this WorkOrder while the lock was held, which should be
                # impossible and therefore matters.
                raise ConcurrentModification(
                    work_id=work_id,
                    detail=(
                        f"requested {target.value!r} but the port reports "
                        f"{moved.phase.value!r} after the move"
                    ),
                )

            # Building the events is inside the protected region, not merely the
            # append. An event whose invariants refuse construction -- a review
            # request naming no lens, say -- would otherwise leave the phase
            # changed with nothing recorded, which is precisely the disagreement
            # between state and log the outbox exists to make impossible.
            try:
                events = self._events_for(context, snapshot, moved, target, side_effects)
                self._log.append(work_id, events)
            except Exception as exc:
                self._attempt_reverse(context, work_id, snapshot.phase, actor)
                raise TransitionRolledBack(
                    work_id=work_id, transition=decision.label, cause=exc
                ) from exc

        # Outside the lock and outside the transition: delivery cannot fail a
        # transition whose events are already recorded.
        self._dispatcher.drain()

        return TransitionResult(
            snapshot=moved,
            decision=decision,
            events=events,
            advisory=decision.policy.advisory,
        )

    # ------------------------------------------------------------------
    # Phase side effects
    # ------------------------------------------------------------------

    def _begin_phase(
        self, context: Any, snapshot: WorkOrderSnapshot, target: WorkOrderPhase
    ) -> dict:
        """Ask the collaborator for the target phase to start. Returns what it said."""
        if target is WorkOrderPhase.IMPLEMENTATION:
            return {"context_bundle": self._lifecycle.on_entering_implementation(context, snapshot) or ""}
        if target is WorkOrderPhase.REVIEW:
            # The round that just finished, not the one that would start next.
            round_number = self.round_number(snapshot.work_id)
            return {"lenses": tuple(self._lifecycle.on_entering_review(context, snapshot, round_number))}
        if target is WorkOrderPhase.VERIFICATION:
            attempt = self.next_attempt(snapshot.work_id)
            self._lifecycle.on_entering_verification(context, snapshot, attempt)
            return {"attempt": attempt}
        return {}

    def _events_for(
        self,
        context: Any,
        before: WorkOrderSnapshot,
        after: WorkOrderSnapshot,
        target: WorkOrderPhase,
        side_effects: dict,
    ) -> tuple:
        """The runtime's own phase-boundary events for this transition.

        The WorkOrder context emits its own state-change events; these are the
        orchestration facts no aggregate can know.
        """
        work_id = after.work_id
        events: list = []

        if target is WorkOrderPhase.IMPLEMENTATION:
            events.append(
                ImplementationStarted(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    round=self.next_round(work_id),
                    context_bundle=side_effects.get("context_bundle", ""),
                )
            )
        elif target is WorkOrderPhase.REVIEW:
            round_number = self.round_number(work_id)
            events.append(
                ImplementationCompleted(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    round=round_number,
                )
            )
            events.append(
                ReviewRequested(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    round=round_number,
                    lenses=side_effects.get("lenses", ("correctness",)),
                )
            )
        elif target is WorkOrderPhase.VERIFICATION:
            round_number = self.round_number(work_id)
            outcomes = self._safe_review_outcomes(context, work_id, round_number)
            events.append(
                ReviewCompleted(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    round=round_number,
                    lenses_reported=tuple(sorted(o.lens for o in outcomes)),
                    blocking_findings=sum(o.blocking_findings for o in outcomes),
                    passed=bool(outcomes) and all(o.passed for o in outcomes),
                )
            )
            events.append(
                VerificationRequested(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    attempt=side_effects.get("attempt", self.attempt_number(work_id)),
                )
            )
        elif target is WorkOrderPhase.READY:
            attempt = self.attempt_number(work_id)
            outcome = self._safe_verification_outcome(context, work_id, attempt)
            events.append(
                VerificationCompleted(
                    metadata=self._metadata(context, work_id),
                    work_id=work_id,
                    version=after.version,
                    attempt=attempt,
                    status=outcome.status if outcome else "complete",
                    reproduced=outcome.claims_reproduced if outcome else 0,
                    contradicted=outcome.claims_contradicted if outcome else 0,
                    unreproducible=outcome.claims_unreproducible if outcome else 0,
                )
            )

        return tuple(events)

    def _safe_review_outcomes(self, context: Any, work_id: str, round_number: int) -> tuple:
        if self._collaborators.review is None:
            return ()
        return self._lifecycle.review_outcomes(context, work_id, round_number)

    def _safe_verification_outcome(self, context: Any, work_id: str, attempt: int):
        if self._collaborators.verification is None:
            return None
        return self._lifecycle.verification_outcome(context, work_id, attempt)

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def _record_rollback(
        self, context: Any, snapshot: WorkOrderSnapshot, target: WorkOrderPhase, cause: BaseException
    ) -> None:
        """Record that a started phase did not happen.

        Best-effort by necessity: if the log itself is what failed there is
        nowhere to record that it failed. Swallowing the secondary error is
        deliberate -- it would mask the original cause, which is the one worth
        surfacing.
        """
        try:
            self._log.append(
                snapshot.work_id,
                (
                    ImplementationCompleted(
                        metadata=self._metadata(
                            context,
                            snapshot.work_id,
                            rolled_back="true",
                            target=target.value,
                            cause=type(cause).__name__,
                        ),
                        work_id=snapshot.work_id,
                        version=snapshot.version,
                        round=self.round_number(snapshot.work_id),
                        claims=0,
                    ),
                ),
            )
        except Exception:  # noqa: BLE001 - see docstring
            pass

    def _attempt_reverse(
        self, context: Any, work_id: str, back_to: WorkOrderPhase, actor: str
    ) -> None:
        """Try to put the WorkOrder back. Best-effort.

        Reached only when the state moved but the log append failed, which
        leaves the two disagreeing. Reversing may itself be illegal -- the
        machine has few backward edges by design -- and when it is, the
        disagreement stands and the raised ``TransitionRolledBack`` is what says
        so.
        """
        try:
            self._collaborators.work_order.transition(context, work_id, back_to, actor)
        except Exception:  # noqa: BLE001 - see docstring
            pass

    # ------------------------------------------------------------------
    # Rejection routing
    # ------------------------------------------------------------------

    def reject(
        self,
        context: Any,
        work_id: str,
        *,
        rejection_type: str,
        detail: str,
        raised_by: str,
        expected_phase: Optional[Any] = None,
    ) -> TransitionResult:
        """Route a typed rejection.

        Goes through the same validator as any other transition, so a rejection
        from a phase the Constitution does not permit one from is refused
        exactly like an illegal move -- rejection is not an escape hatch from the
        machine.
        """
        with self._lock_for(work_id):
            snapshot = self.snapshot(context, work_id)
            decision = self._executor.decide(
                snapshot, WorkOrderPhase.REJECTED, context, expected_phase=expected_phase
            )
            moved = self._collaborators.work_order.reject(
                context, work_id, rejection_type, detail, raised_by
            )

        self._dispatcher.drain()
        return TransitionResult(snapshot=moved, decision=decision, events=())

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    def replay(self, work_id: Optional[str] = None) -> tuple:
        """The recorded event sequence, for rebuilding a projection.

        Returns entries rather than applying them. What a projection *is* is the
        consumer's business; the runtime's job is to guarantee the sequence is
        complete and ordered.
        """
        entries = (
            self._log.for_work_order(work_id) if work_id is not None else self._log.since(0)
        )
        return tuple(entries)
