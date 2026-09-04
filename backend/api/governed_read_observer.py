"""Governed read → durable Observation. The production leg — Phase 9.3 (ADR-083).

The gap this closes
---------------------
Phases 7.2 through 9.2 all proved the same shape: a governed read happens, its
bounded provider evidence reaches the execution aggregate, and an ``Observation``
is written from it. But that middle step — *turning an execution result into a
``ReadObservation``* — existed only inside each phase's harness script. A grep for
``ReadObservation(`` across ``backend/`` before this module returned nothing.

That was fine while the caller was always a harness proving a point. It stops
being fine the moment something has to observe continuously: a watch driver
cannot live in ``scripts/``.

Why it lives in ``backend/api/`` and not in ``backend/world/``
---------------------------------------------------------------
Because it has to see both planes, and the World Plane is not allowed to. Running
a governed capability means importing ``backend.contexts.execution``, which
``BND-WORLD-CANNOT-EXECUTE`` makes an architecture-test ERROR for anything under
``backend.world``. That rule *is* the enforcement of "the World Plane never opens
the Kubernetes connection itself", and this module is on the correct side of it:

    governed execution/capability  ->  provider  ->  evidence
                                                       |
                                          this module  v
                                              ObservationIngestion  ->  World

The direction never reverses. Nothing here reads a provider, holds a credential,
opens a socket, or writes anything but through the World Plane's own ingestion
boundary — which applies its own tenant rule and its own secret firewall on top.

Tenant
--------
Taken from the governed ``ExecutionContext`` the read ran under. Never from the
provider payload, never from the evidence, never from a Kubernetes object's
namespace, never from a parameter. A context without a tenant is a refusal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.errors import ContractViolation

__all__ = [
    "GovernedReadOutcome",
    "GovernedCapabilityReader",
    "ObservationLeg",
    "GovernedReadObserver",
]


def __getattr__(name: str):
    """``GovernedCapabilityReader`` lives in the composition root.

    Running a governed capability means touching Connectivity (authorize,
    resolve) AND Execution (start, dispatch, read the aggregate), and exactly
    five named, ADR-recorded modules are permitted to import two contexts. This
    module is not one of them, and should not become one: what it does — map an
    execution result to an Observation — needs neither context.

    So the reader lives in ``capability_execution_composition``, where "a
    binding meets a runtime" already lives, and is re-exported here (lazily, so
    the import edge is never created at module scope) because callers want both
    halves from one place.
    """
    if name == "GovernedCapabilityReader":
        from backend.api.capability_execution_composition import (
            GovernedCapabilityReader as _Reader,
        )
        return _Reader
    raise AttributeError(name)


@dataclass(frozen=True)
class GovernedReadOutcome:
    """What one governed read actually produced. Facts, not a decision.

    ``evidence`` is the operation's declared, bounded provider evidence as it
    reached the execution aggregate — the same dict the adapter extracted, not a
    reconstruction of it. ``status`` is the provider's HTTP status where the
    aggregate carries one; it is what lets a caller tell an expired watch
    position (410) from a refused one (403) without reading prose.
    """

    operation: str
    execution_id: str
    node_state: Optional[str]
    succeeded: bool
    evidence: Mapping[str, Any]
    status: Optional[int] = None
    failure_reason: Optional[str] = None
    duration_seconds: float = 0.0

    @property
    def expired(self) -> bool:
        """The provider said this continuation point no longer exists.

        Kubernetes says it two ways and both mean the same thing: an HTTP 410 on
        the request, or a 200 whose stream carries a ``Status`` with code 410.
        Neither is a success and neither is an ordinary failure — it is the one
        failure whose correct answer is "go and get a new position".
        """
        if self.status == 410:
            return True
        return self.evidence.get("streamErrorCode") == 410


@dataclass(frozen=True)
class ObservationLeg:
    """One observation an evidence mapping is being asked to produce.

    Separate from ``ReadObservation`` because the World Plane's contract is the
    World Plane's; this is the caller's description of what it believes it saw,
    and the ingestion boundary remains free to refuse it.
    """

    subject_ref: str
    predicate: str
    value: Mapping[str, Any]
    observed_at: Optional[datetime] = None
    retrieved_at: Optional[datetime] = None
    """When the instrument was queried, when the caller must say so itself.

    Normally the observer's own moment is right. It is not right when the
    provider states its own observation time from its own clock: two clocks
    disagree, and a provider whose clock runs a second ahead would otherwise
    produce ``observed_at > retrieved_at`` — which the temporal contract refuses,
    correctly, because a fetch cannot precede the moment it observed. The caller
    that knows about the skew reconciles it and says so here."""


class GovernedReadObserver:
    """Turns governed read outcomes into durable Observations. Nothing else.

    Three things it will not do, each because the alternative is a way world
    state stops being trustworthy:

    * **A failed read produces no observation.** Not an observation recording the
      failure, not one with a status of "unknown" — none. The World Plane records
      what an instrument reported about the world; a provider that refused
      reported nothing about the world, only about itself. The failure is already
      durable on the execution attempt, where failures belong.
    * **It never invents a value.** Every field of every observation comes from
      the declared evidence the adapter extracted.
    * **It never chooses a tenant.** The tenant is the governed context's, passed
      through to an ingestion boundary that checks it again.
    """

    def __init__(self, *, ingestion: Any, source_ref: str, produced_by: str) -> None:
        self._ingestion = ingestion
        self._source_ref = source_ref
        self._produced_by = produced_by

    def observe(
        self,
        *,
        tenant: Any,
        outcome: GovernedReadOutcome,
        legs: Sequence[ObservationLeg],
        trace_ref: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Record one observation per leg. Returns ``(observation, newly)`` pairs.

        ``newly`` False is the ordinary at-least-once outcome — the same external
        observation delivered twice collides on its deterministic identity and is
        not recorded again. It is not an error and is never treated as one.
        """
        from backend.contracts.evidence import SourceStatus
        from backend.contracts.world import ObservationSourceKind
        from backend.world.application import ReadObservation

        if not outcome.succeeded:
            # Stated rather than silently returning nothing: a caller that passed
            # a failed read here has a bug, and an empty tuple would look like a
            # provider that had nothing to say.
            raise ContractViolation(
                f"{outcome.operation!r} did not succeed ({outcome.failure_reason}); "
                "a read that failed observed nothing about the world, and the "
                "World Plane does not record the absence of an answer as one"
            )
        moment = now or datetime.now(timezone.utc)
        recorded: list = []
        for leg in legs:
            read = ReadObservation(
                source_kind=ObservationSourceKind.CONNECTOR,
                source_ref=self._source_ref,
                subject_ref=leg.subject_ref,
                predicate=leg.predicate,
                value=dict(leg.value),
                status=SourceStatus.RETURNED_DATA,
                # The instrument's report of when the world was in this state.
                # For a watch event that is the moment the event was observed;
                # for a plain read it is the retrieval moment, said so.
                observed_at=leg.observed_at or moment,
                retrieved_at=leg.retrieved_at or moment,
                produced_by=self._produced_by,
                execution_ref=outcome.execution_id,
                trace_ref=trace_ref,
            )
            recorded.append(
                self._ingestion.ingest(tenant=tenant, read=read, recorded_at=moment))
        return tuple(recorded)
