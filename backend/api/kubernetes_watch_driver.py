"""The governed Kubernetes observation stream — Phase 9.3 (ADR-083).

What this is
--------------
The loop that keeps the World Plane continuously informed of what Kubernetes is
doing, built entirely out of parts that already existed:

    last position (a durable Observation)
        |
        v  absent, or expired
    governed LIST   -----------------------------> real resourceVersion
        |                                              |
        |<---------------------------------------------+
        v
    governed WATCH window (?watch=true&resourceVersion=RV&timeoutSeconds=W)
        |
        v
    ADDED / MODIFIED / DELETED  ->  one Observation each
    BOOKMARK                    ->  position only, never a mutation
    ERROR(410)                  ->  discard the position, take a fresh LIST
        |
        v
    checkpoint Observation (the new position)  ->  repeat

Every provider contact in that diagram is an ordinary governed capability
execution. There is no second gateway, executor, scheduler, transport, credential
path, audit chain, observation store or election here — this module holds a
reader, an observer, a repository, a leadership store and a clock, and every one
of them is the one that already existed.

Bounded windows, and why that is the honest design
----------------------------------------------------
A Kubernetes watch is a long-lived chunked response. The governed transport is
deliberately a request/response client — it refuses server-sent events outright,
because a stream needs idle-timeout and per-frame accounting a request/response
adapter cannot provide — so consuming a watch as a continuous stream would mean
building a second transport, which is the thing this phase must not do.

So each window is bounded by ``timeoutSeconds``: the API server closes it, the
answer arrives as one complete body, and the next window resumes from the exact
resourceVersion the last event carried. Continuity is preserved exactly. What is
*not* claimed is streaming: an event becomes visible to the World Plane at the end
of the window it arrived in, so per-event latency is bounded by the window length,
not by network arrival. That is a real property of this design and is stated
everywhere rather than glossed as "continuous".

Bookmarks are why a quiet cluster does not go stale: the API server periodically
sends a position with no resource change, so the driver can hold an *unexpired*
position through long quiet periods without inventing anything.

At-least-once, and exactly what that means here
-------------------------------------------------
Events are recorded, and only then is the position advanced. Crash between the
two and the events are re-delivered on the next window. That is deliberate and it
is the only safe order: advancing first would lose, silently, whatever a crash
interrupted.

So a re-delivered event can produce a second Observation row — a second honest
record of a second delivery, with its own ``recorded_at`` — and never a lost one.
Fact derivation then resolves it to ``DEDUPED``, because the value effective at
that instant is already what is held, so world *belief* does not move. Duplicate
delivery is visible in the ledger and inert in the conclusions. **Exactly-once is
not claimed and is not implemented.**
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "WatchPosition",
    "WatchCycleReport",
    "KubernetesWatchDriver",
    "STREAM_PREDICATE",
    "RESOURCE_PREDICATE",
]

#: The predicate under which a stream's position is recorded. A distinct
#: predicate rather than a distinct table: the position is an observation about a
#: stream, the observation ledger is already append-only and tenant-scoped, and a
#: second store would be a second thing that could disagree about where we are.
STREAM_PREDICATE = "watch_position"

#: The predicate under which an observed resource state is recorded — the same
#: predicate the Phase 9.2 governed read uses, deliberately: a pod observed by a
#: watch event and a pod observed by a list are the same proposition about the
#: same subject, and giving them different predicates would split one fact into
#: two that never corroborate.
RESOURCE_PREDICATE = "state"

#: How a position came to be. Recorded in the checkpoint so recovery is legible
#: in provenance rather than inferred from a gap in timestamps.
ORIGIN_LIST = "list"
ORIGIN_WATCH = "watch"
ORIGIN_LIST_AFTER_EXPIRY = "list_after_expiry"


@dataclass(frozen=True)
class WatchPosition:
    """Where this stream is, as last durably recorded."""

    resource_version: str
    origin: str
    observation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.resource_version, str) or not self.resource_version:
            raise ContractViolation(
                "a watch position is an opaque, non-empty resourceVersion; an "
                "empty one would mean 'from now', which is a different operation"
            )


@dataclass(frozen=True)
class WatchCycleReport:
    """What one cycle did. Facts only — nothing here decides anything."""

    outcome: str
    started_from: Optional[str] = None
    advanced_to: Optional[str] = None
    events_seen: int = 0
    observations_recorded: int = 0
    observations_deduped: int = 0
    bookmarks: int = 0
    recovered_from_expiry: bool = False
    execution_id: Optional[str] = None
    detail: Optional[str] = None
    provider_calls: int = 0
    durations: Mapping[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "outcome": self.outcome,
            "started_from": self.started_from,
            "advanced_to": self.advanced_to,
            "events_seen": self.events_seen,
            "observations_recorded": self.observations_recorded,
            "observations_deduped": self.observations_deduped,
            "bookmarks": self.bookmarks,
            "recovered_from_expiry": self.recovered_from_expiry,
            "execution_id": self.execution_id,
            "detail": self.detail,
            "provider_calls": self.provider_calls,
            "durations": dict(self.durations),
        }


class KubernetesWatchDriver:
    """Advances one tenant's Kubernetes pod observation stream.

    Explicit lifecycle, like the scheduler it borrows its shape from: ``cycle``
    does one bounded window and returns. There is no thread here and nothing that
    starts on import — a loop that ran itself would be a provider being contacted
    because a module was imported.
    """

    def __init__(
        self,
        *,
        reader: Any,
        observer: Any,
        observations: Any,
        leadership: Any,
        tenant: Any,
        namespace: str,
        list_operation: str,
        watch_operation: str,
        window_seconds: int,
        lease_seconds: int = 60,
        max_expiry_recoveries: int = 3,
        clock: Any = None,
    ) -> None:
        if not namespace or not isinstance(namespace, str):
            raise ContractViolation("a watch stream is scoped to a named namespace")
        if lease_seconds <= window_seconds:
            # A lease shorter than a window expires *while the window is open*,
            # so the advance at the end of every window is refused by the fence
            # and the stream can never move. It looks like a fencing problem and
            # is a configuration one, so it is refused here rather than
            # discovered as a stream that quietly observes and never advances.
            raise ContractViolation(
                f"the stream lease ({lease_seconds}s) must outlive one watch "
                f"window ({window_seconds}s); a lease that expires mid-window "
                "fences every advance and the position never moves"
            )
        self._reader = reader
        self._observer = observer
        self._observations = observations
        self._leadership = leadership
        self._tenant = tenant
        self._namespace = namespace
        self._list_operation = list_operation
        self._watch_operation = watch_operation
        self._window_seconds = window_seconds
        self._lease_seconds = lease_seconds
        self._max_expiry_recoveries = max_expiry_recoveries
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._handle: Optional[Any] = None
        self._expiry_recoveries = 0

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def stream_subject(self) -> str:
        """The subject the stream's *position* is about. The stream, not a pod."""
        return f"kubernetes:podstream:{self._namespace}"

    def resource_subject(self, name: str) -> str:
        return f"kubernetes:pod:{self._namespace}/{name}"

    @property
    def leadership_handle(self) -> Optional[Any]:
        return self._handle

    # ------------------------------------------------------------------
    # Leadership
    # ------------------------------------------------------------------

    def hold_leadership(self) -> bool:
        """Take or keep the stream role. ``False`` is the ordinary follower answer.

        Reuses ``SqlLeadershipStore`` unchanged. There is no Kubernetes-specific
        election here and there must not be: a second election is a second
        opinion about who is in charge, which is the failure it exists to prevent.
        """
        from backend.database.durable.leadership import LeadershipRole

        if self._handle is not None:
            renewed = self._leadership.heartbeat(
                self._handle, lease_seconds=self._lease_seconds)
            if renewed is not None:
                self._handle = renewed
                return True
            # The lease was not renewed: somebody else holds the role now, or it
            # lapsed while this process was stalled. Drop the handle rather than
            # keep using a stale one.
            self._handle = None
        self._handle = self._leadership.acquire(
            role=LeadershipRole.WORLD_WATCH,
            lease_seconds=self._lease_seconds,
            scope=self._tenant.tenant_id,
        )
        return self._handle is not None

    def release_leadership(self) -> bool:
        if self._handle is None:
            return False
        released = self._leadership.release(self._handle)
        self._handle = None
        return released

    def _still_leader(self) -> Optional[str]:
        """Re-assert the role immediately before a durable advance.

        Uses ``heartbeat``, not ``assert_current``, and the difference matters
        twice over:

        * **It is fenced by the database.** ``heartbeat`` is a conditional
          ``UPDATE`` matching on ``instance_id`` AND ``fencing_token`` AND
          status; a process whose role was taken while it was working gets
          ``None`` back from the store rather than from a read-and-compare this
          code performed. That is the mechanism ``assert_current`` explicitly
          says it is not.
        * **It renews.** A cycle is a whole governed execution — a watch window
          plus dispatch, plus persistence — and a leader that is demonstrably
          alive and still holds the token should not lose the role merely for
          having taken longer than one lease to do one unit of work. Renewal is
          bounded and repeated, exactly as the leadership module intends; a
          leader that is wedged stops calling this and lapses on its own.

        It still narrows a window rather than closing it, for the reason ADR-054
        states for the audit writer: an ``INSERT`` into the observation ledger
        has no ``WHERE`` for the token to join, so a stall between this call and
        the insert is not covered.

        What that residual window can and cannot cause is worth being exact
        about. A stale writer that slips through can write a *late checkpoint*,
        which can move the position backwards. It cannot corrupt anything:
        observations are append-only and identity-deduped, so the worst outcome
        is that events are re-delivered — at-least-once, which is what is
        claimed. It cannot delete, cannot overwrite, and cannot make the
        successor's own later checkpoint disappear.
        """
        if self._handle is None:
            return "this process does not hold the stream role"
        renewed = self._leadership.heartbeat(
            self._handle, lease_seconds=self._lease_seconds)
        if renewed is None:
            self._handle = None
            return ("this process no longer holds the stream role; the advance "
                    "is refused by the fence")
        self._handle = renewed
        return None

    # ------------------------------------------------------------------
    # Position
    # ------------------------------------------------------------------

    def current_position(self) -> Optional[WatchPosition]:
        """The last position durably recorded, reconstructed from the ledger.

        No separate stream-state store, on purpose. The position was written as an
        append-only Observation like everything else the World Plane knows, so
        there is exactly one place that can answer "where are we", and recovery
        after a crash is the same read as the ordinary one.
        """
        observation = self._observations.latest_for_subject(
            tenant_id=self._tenant.tenant_id,
            subject_ref=self.stream_subject,
            predicate=STREAM_PREDICATE,
        )
        if observation is None:
            return None
        value = observation.value
        if not isinstance(value, Mapping):
            return None
        version = value.get("resourceVersion")
        if not isinstance(version, str) or not version:
            return None
        return WatchPosition(
            resource_version=version,
            origin=str(value.get("origin") or "unknown"),
            observation_id=observation.record_id,
        )

    # ------------------------------------------------------------------
    # The cycle
    # ------------------------------------------------------------------

    def cycle(self, context: Any) -> WatchCycleReport:
        """One bounded step of the stream. Never blocks on a lease, never loops."""
        if not self.hold_leadership():
            return WatchCycleReport(
                outcome="follower",
                detail="another instance holds this tenant's stream role",
            )

        position = self.current_position()
        if position is None:
            return self._establish(context, origin=ORIGIN_LIST)
        return self._watch(context, position)

    def run(self, context: Any, *, windows: int) -> tuple:
        """A bounded sequence of cycles. Bounded because an unbounded loop in a
        library is a daemon somebody has to find a way to stop."""
        if windows < 1:
            raise ContractViolation("a run covers at least one window")
        return tuple(self.cycle(context) for _ in range(windows))

    # ------------------------------------------------------------------

    def _establish(self, context: Any, *, origin: str) -> WatchCycleReport:
        """Take a fresh position from a governed LIST.

        The resourceVersion recorded here is the one the cluster returned, copied
        exactly. Nothing is minted, incremented, or carried over from the position
        this replaced — after an expiry the old one is gone, and pretending
        otherwise would be claiming continuity across a gap that really happened.
        """
        outcome = self._reader.read(
            context, operation=self._list_operation,
            payload={"namespace": self._namespace},
        )
        if not outcome.succeeded:
            return WatchCycleReport(
                outcome="list_failed", execution_id=outcome.execution_id or None,
                detail=outcome.failure_reason,
                durations={"list": outcome.duration_seconds},
            )
        version = outcome.evidence.get("resourceVersion")
        if not isinstance(version, str) or not version:
            # The operation's own required-field check should already have
            # refused this. Checked again because starting a watch from a
            # resourceVersion nobody returned is the one thing that must not
            # happen, and a second check costs nothing.
            return WatchCycleReport(
                outcome="list_failed", execution_id=outcome.execution_id,
                detail="the governed list returned no resourceVersion; a watch "
                       "cannot be started from a position the cluster did not give",
                durations={"list": outcome.duration_seconds},
            )

        fenced = self._still_leader()
        if fenced is not None:
            return WatchCycleReport(outcome="fenced", detail=fenced)

        recorded = self._checkpoint(
            outcome, version=version, origin=origin,
            extra={"podCount": outcome.evidence.get("podCount")},
        )
        return WatchCycleReport(
            outcome="established", advanced_to=version,
            observations_recorded=1 if recorded else 0,
            observations_deduped=0 if recorded else 1,
            recovered_from_expiry=origin == ORIGIN_LIST_AFTER_EXPIRY,
            execution_id=outcome.execution_id, provider_calls=1,
            durations={"list": outcome.duration_seconds},
        )

    def _watch(self, context: Any, position: WatchPosition) -> WatchCycleReport:
        outcome = self._reader.read(
            context, operation=self._watch_operation,
            payload={
                "namespace": self._namespace,
                # The position, exactly as it was recorded. Never re-derived,
                # never adjusted, never a number this code produced.
                "resourceVersion": position.resource_version,
                "timeoutSeconds": self._window_seconds,
            },
        )
        durations = {"watch": outcome.duration_seconds}

        if outcome.expired:
            return self._recover_expired(context, position, outcome, durations)

        if not outcome.succeeded:
            # A failure stays a failure. The position does not move, no
            # observation is written, and the next cycle tries the same window
            # again — a reconnect is not a success and is never recorded as one.
            return WatchCycleReport(
                outcome="watch_failed", started_from=position.resource_version,
                execution_id=outcome.execution_id, detail=outcome.failure_reason,
                provider_calls=1, durations=durations,
            )

        events = outcome.evidence.get("events")
        events = events if isinstance(events, list) else []
        moment = self._clock()
        legs = self._legs(events, moment)

        recorded = deduped = 0
        if legs:
            results = self._observer.observe(
                tenant=self._tenant, outcome=outcome, legs=legs,
                trace_ref=self._trace_ref(context), now=moment,
            )
            recorded = sum(1 for _, newly in results if newly)
            deduped = len(results) - recorded

        advanced = outcome.evidence.get("lastResourceVersion")
        advanced = advanced if isinstance(advanced, str) and advanced else None

        if advanced is not None:
            fenced = self._still_leader()
            if fenced is not None:
                # Events are already durable; only the advance is refused. The
                # successor re-delivers this window, which is at-least-once.
                return WatchCycleReport(
                    outcome="fenced", started_from=position.resource_version,
                    events_seen=len(events), observations_recorded=recorded,
                    observations_deduped=deduped, detail=fenced,
                    execution_id=outcome.execution_id, provider_calls=1,
                    durations=durations,
                )
            # Events first, position second. Always. A crash between them
            # re-delivers; a crash in the other order would lose.
            self._checkpoint(outcome, version=advanced, origin=ORIGIN_WATCH,
                             extra={"eventCount": outcome.evidence.get("eventCount")},
                             now=moment)
            self._expiry_recoveries = 0

        return WatchCycleReport(
            outcome="observed" if events else "idle",
            started_from=position.resource_version,
            advanced_to=advanced, events_seen=len(events),
            observations_recorded=recorded, observations_deduped=deduped,
            bookmarks=int(outcome.evidence.get("bookmarkCount") or 0),
            execution_id=outcome.execution_id, provider_calls=1,
            durations=durations,
        )

    def _recover_expired(
        self, context: Any, position: WatchPosition, outcome: Any, durations: dict
    ) -> WatchCycleReport:
        """410 Gone: the cluster no longer retains this position.

        Continuity is genuinely lost, and the recovery says so. The expired
        position is discarded and never presented again; a fresh governed LIST
        produces a new real resourceVersion; the checkpoint that records it names
        the expiry it followed, so an operator reading the ledger sees the gap
        instead of a smooth line through it.

        Bounded, because a cluster that expires every position we take is a
        condition to surface, not one to hide inside a loop.
        """
        self._expiry_recoveries += 1
        if self._expiry_recoveries > self._max_expiry_recoveries:
            return WatchCycleReport(
                outcome="expiry_recovery_exhausted",
                started_from=position.resource_version,
                execution_id=outcome.execution_id, provider_calls=1,
                detail=(
                    f"the watch position expired {self._expiry_recoveries} times "
                    f"in a row (limit {self._max_expiry_recoveries}); the stream "
                    "is not keeping up with the cluster's retention and that is "
                    "reported rather than retried indefinitely"
                ),
                durations=durations,
            )
        report = self._establish(context, origin=ORIGIN_LIST_AFTER_EXPIRY)
        merged = dict(report.durations)
        merged.update(durations)
        return WatchCycleReport(
            outcome=("recovered_from_expiry" if report.outcome == "established"
                     else report.outcome),
            started_from=position.resource_version,
            advanced_to=report.advanced_to,
            observations_recorded=report.observations_recorded,
            observations_deduped=report.observations_deduped,
            recovered_from_expiry=True,
            execution_id=report.execution_id,
            detail=report.detail,
            provider_calls=1 + report.provider_calls,
            durations=merged,
        )

    # ------------------------------------------------------------------

    def _legs(self, events: Sequence[Mapping], moment: datetime) -> tuple:
        """One observation leg per *resource mutation*. Bookmarks produce none.

        A bookmark says "the stream is at this position and nothing changed". An
        Observation built from one would assert a resource state the cluster never
        reported — a fabricated observation, which is the specific thing the World
        Plane exists to make impossible. It advances the position and nothing else.
        """
        from backend.api.governed_read_observer import ObservationLeg
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            KUBERNETES_WATCH_MUTATION_TYPES,
        )

        legs: list = []
        for event in events:
            if not isinstance(event, Mapping):
                continue
            kind = event.get("type")
            if kind not in KUBERNETES_WATCH_MUTATION_TYPES:
                continue
            name = event.get("name")
            if not isinstance(name, str) or not name:
                # The normalizer already refuses an unidentifiable mutation; if
                # one reached here it is skipped rather than given a placeholder.
                continue
            legs.append(ObservationLeg(
                subject_ref=self.resource_subject(name),
                predicate=RESOURCE_PREDICATE,
                value={
                    "eventType": kind,
                    "resourceVersion": event.get("resourceVersion"),
                    "kind": event.get("kind"),
                    "namespace": event.get("namespace"),
                    "name": name,
                    "uid": event.get("uid"),
                    "observedVia": "watch",
                },
                observed_at=moment,
            ))
        return tuple(legs)

    def _checkpoint(
        self, outcome: Any, *, version: str, origin: str,
        extra: Optional[Mapping] = None, now: Optional[datetime] = None,
    ) -> bool:
        """Record the new position as an ordinary Observation. Returns ``newly``."""
        from backend.api.governed_read_observer import ObservationLeg

        moment = now or self._clock()
        value = {
            "resourceVersion": version,
            "origin": origin,
            "namespace": self._namespace,
        }
        for key, item in (extra or {}).items():
            if item is not None:
                value[key] = item
        results = self._observer.observe(
            tenant=self._tenant, outcome=outcome,
            legs=(ObservationLeg(
                subject_ref=self.stream_subject, predicate=STREAM_PREDICATE,
                value=value, observed_at=moment),),
            now=moment,
        )
        return bool(results and results[0][1])

    @staticmethod
    def _trace_ref(context: Any) -> Optional[str]:
        correlation = getattr(context, "correlation", None)
        return getattr(correlation, "correlation_id", None) if correlation else None
