"""Discovery and ingestion.

The invariant this service exists to hold
-------------------------------------------
**A discovered capability arrives REGISTERED and UNVERIFIED, and nothing here
can change that.** There is no ``auto_trust`` parameter, no ``trusted_source``
flag, and no path from ``discover()`` to an enabled capability. Ingestion calls
``CapabilityService.register`` and stops. Validation, enabling and trust are
separate operations somebody has to perform deliberately.

That is enforced structurally rather than by discipline: this service holds a
``CapabilityService`` and calls exactly one method on it. It never touches the
repository, so it cannot write a definition of its own shape.

What a discovery source is
----------------------------
A Protocol that returns observations. Adapters that read V1 registries live at
the **composition root**, not here -- a bounded context may not import
``backend.mcp`` or ``backend.connectors`` (Constitution S2), and the neutral
``RawObservation`` boundary means nothing V1-shaped reaches the domain either.

No source in this phase performs a network call. MCP tool definitions in this
repository come from local configuration, so the whole inventory can be built
from information the platform already holds. A remote transport is a later
decision with a credential story attached, and inventing one here would mean
inventing the credential story too.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, Sequence, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contexts.connectivity.application.commands import RegisterCapability
from backend.contexts.connectivity.application.normalization import (
    RawObservation,
    normalize,
)
from backend.contexts.connectivity.domain.budgets import DEFAULT_BUDGET, DiscoveryBudget
from backend.contexts.connectivity.domain.candidate import (
    CandidateStatus,
    CapabilityCandidate,
)
from backend.contexts.connectivity.domain.definition import CapabilitySource
from backend.contexts.connectivity.domain.discovery import (
    ChangeKind,
    DiscoveryObservation,
    DiscoveryReport,
    IngestionOutcome,
    SourceHealth,
)
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotFound,
    CapabilityVersionNotFound,
    ConflictingRegistration,
)
from backend.contexts.connectivity.domain.events import (
    DiscoveryCompleted,
    DiscoveryConflictDetected,
    DiscoveryFailed,
    DiscoveryStarted,
)
from backend.contexts.connectivity.domain.identifiers import CapabilityRef
from backend.platform.events import EventMetadata

__all__ = [
    "CapabilityDiscoverySource",
    "SourceResult",
    "StaticObservationSource",
    "CapabilityDiscoveryService",
    "DiscoveryRunResult",
]


@dataclass(frozen=True)
class SourceResult:
    """What one source produced. Health first, results second.

    Health is a separate field rather than being inferred from an empty list,
    because "nothing to offer" and "could not be asked" must never look alike.
    """

    health: SourceHealth
    observations: tuple = ()
    error: Optional[str] = None
    total_offered: Optional[int] = None
    """How many the source claimed to have, when it can say. Lets the service
    report what a budget dropped instead of silently returning a short list."""

    def __post_init__(self) -> None:
        if not isinstance(self.health, SourceHealth):
            raise ContractViolation("health must be a SourceHealth")
        if not self.health.is_reachable and self.observations:
            raise ContractViolation(
                f"a {self.health.value} source cannot also return observations"
            )


@runtime_checkable
class CapabilityDiscoverySource(Protocol):
    """Something that can be asked what capabilities it offers.

    Narrow deliberately: it is asked once and answers with observations plus its
    own health. It is given an ``ExecutionContext`` because a tenant-scoped
    source must only report what that tenant may see.
    """

    @property
    def source_id(self) -> str: ...

    @property
    def source_type(self) -> CapabilitySource: ...

    def collect(self, context: Any, budget: DiscoveryBudget) -> SourceResult: ...


class StaticObservationSource:
    """A source over observations already in hand.

    Every adapter in this phase reduces to this: read something local, produce
    ``RawObservation`` values, hand them over. It is also what manual submission
    uses, so a hand-written candidate travels the same validation path as a
    discovered one and cannot skip ahead of it.
    """

    def __init__(
        self,
        source_id: str,
        source_type: CapabilitySource,
        observations: Sequence[RawObservation],
        *,
        health: SourceHealth = SourceHealth.HEALTHY,
        error: Optional[str] = None,
    ) -> None:
        self._source_id = source_id
        self._source_type = source_type
        self._observations = tuple(observations)
        self._health = health if self._observations or health is not SourceHealth.HEALTHY else SourceHealth.EMPTY
        self._error = error

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> CapabilitySource:
        return self._source_type

    def collect(self, context: Any, budget: DiscoveryBudget) -> SourceResult:
        return SourceResult(
            health=self._health,
            observations=self._observations,
            error=self._error,
            total_offered=len(self._observations),
        )


@dataclass(frozen=True)
class DiscoveryRunResult:
    reports: tuple = ()
    events: tuple = ()

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)

    @property
    def conflicts(self) -> tuple:
        return tuple(c for report in self.reports for c in report.conflicts)

    @property
    def registered_count(self) -> int:
        return sum(r.registered_count for r in self.reports)

    def to_dict(self) -> dict:
        return {
            "sources": len(self.reports),
            "registered": self.registered_count,
            "conflicts": len(self.conflicts),
            "events": list(self.event_types),
            "reports": [r.to_dict() for r in self.reports],
        }


class CapabilityDiscoveryService:
    """Collects candidates and, when asked, ingests them into the registry."""

    def __init__(
        self,
        *,
        registry: Any,
        budget: DiscoveryBudget = DEFAULT_BUDGET,
    ) -> None:
        self._registry = registry
        self._budget = budget

    @property
    def budget(self) -> DiscoveryBudget:
        return self._budget

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    @staticmethod
    def _metadata(context: Any, source_id: str) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=source_id, aggregate_type="capability_source", scope=scope
        )

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(
        self,
        context: Any,
        sources: Sequence[CapabilityDiscoverySource],
        *,
        ingest: bool = False,
    ) -> DiscoveryRunResult:
        """Collect from each source, and optionally ingest what is usable.

        ``ingest`` defaults to **False**. Discovery is an inventory operation,
        and making the registry change a deliberate second choice keeps
        "look at what is out there" from being the same act as "record it".

        Even with ``ingest=True`` nothing becomes enabled or trusted. The most
        an ingested capability reaches is REGISTERED/UNVERIFIED.
        """
        if len(sources) > self._budget.max_sources:
            raise ContractViolation(
                f"{len(sources)} sources exceeds the discovery budget of "
                f"{self._budget.max_sources}"
            )

        reports: list = []
        events: list = []

        for source in sources:
            started = datetime.now(timezone.utc)
            events.append(
                DiscoveryStarted(
                    metadata=self._metadata(context, source.source_id),
                    source_id=source.source_id,
                    source_type=source.source_type.value,
                )
            )
            report = self._run_source(context, source, started, ingest=ingest)
            reports.append(report)

            if report.health.is_reachable:
                events.append(
                    DiscoveryCompleted(
                        metadata=self._metadata(context, source.source_id),
                        source_id=source.source_id,
                        source_type=source.source_type.value,
                        health=report.health.value,
                        candidates=len(report.candidates),
                        registered=report.registered_count,
                        conflicts=len(report.conflicts),
                        not_seen=len(report.not_seen),
                    )
                )
            else:
                events.append(
                    DiscoveryFailed(
                        metadata=self._metadata(context, source.source_id),
                        source_id=source.source_id,
                        source_type=source.source_type.value,
                        health=report.health.value,
                        reason=report.error or "source unreachable",
                    )
                )

            for conflict in report.conflicts:
                events.append(
                    DiscoveryConflictDetected(
                        metadata=self._metadata(context, source.source_id),
                        source_id=source.source_id,
                        source_type=source.source_type.value,
                        capability_reference=conflict.candidate_reference or "",
                        observation_digest=conflict.observation_digest or "",
                        detail=str(conflict.detail.get("message", "")),
                    )
                )

        return DiscoveryRunResult(reports=tuple(reports), events=tuple(events))

    def _run_source(
        self,
        context: Any,
        source: CapabilityDiscoverySource,
        started: datetime,
        *,
        ingest: bool,
    ) -> DiscoveryReport:
        try:
            result = source.collect(context, self._budget)
        except Exception as exc:  # noqa: BLE001 - a broken source is a health fact
            # A source that raises is unavailable, not empty. Letting the
            # exception escape would abort discovery of every other source, and
            # treating it as an empty inventory would erase everything it offers.
            return DiscoveryReport(
                source_id=source.source_id,
                source_type=source.source_type.value,
                health=SourceHealth.UNAVAILABLE,
                started_at=started,
                error=f"{type(exc).__name__}: {exc}",
            )

        if not result.health.is_reachable:
            return DiscoveryReport(
                source_id=source.source_id,
                source_type=source.source_type.value,
                health=result.health,
                started_at=started,
                error=result.error,
            )

        taken = self._budget.truncated(
            "max_capabilities_per_source", tuple(result.observations)
        )
        dropped = max(0, (result.total_offered or len(result.observations)) - len(taken))

        candidates: list = []
        observations: list = []
        for raw in taken:
            candidate = normalize(raw, budget=self._budget)
            candidates.append(candidate)
            observations.append(
                self._observe(context, source, candidate, ingest=ingest)
            )

        health = result.health
        if health is SourceHealth.HEALTHY and not candidates:
            health = SourceHealth.EMPTY

        not_seen: tuple = ()
        if health.results_are_complete:
            not_seen = self._not_seen(context, source, candidates)

        return DiscoveryReport(
            source_id=source.source_id,
            source_type=source.source_type.value,
            health=health,
            started_at=started,
            candidates=tuple(candidates),
            observations=tuple(observations),
            not_seen=not_seen,
            dropped_for_budget=dropped,
            error=result.error,
        )

    # ------------------------------------------------------------------
    # Change detection and ingestion
    # ------------------------------------------------------------------

    def classify(self, context: Any, candidate: CapabilityCandidate) -> ChangeKind:
        """How this observation relates to what is already registered. Read-only."""
        registered = self._registered(context, candidate.reference)
        if registered is None:
            return ChangeKind.NEW
        if candidate.contract is None:
            return ChangeKind.UNCHANGED
        # Compare against the authoritative contract digest, not the observation
        # fingerprint: a rewritten description is not a changed contract, and a
        # changed effect class with an identical description is.
        offered = self._contract_digest(context, candidate)
        if offered == registered.digest:
            return ChangeKind.UNCHANGED
        return ChangeKind.CONFLICTING

    def ingest(self, context: Any, candidate: CapabilityCandidate) -> DiscoveryObservation:
        """Record one candidate. The only path from discovery into the registry.

        Registers, and nothing else. There is no argument that would make this
        enable, validate, or trust anything.
        """
        moment = datetime.now(timezone.utc)
        base = {
            "source_id": candidate.source.source_id,
            "source_type": candidate.source.source_type.value,
            "observed_at": moment,
            "candidate_id": candidate.candidate_id,
            "candidate_reference": candidate.reference.value,
            "observation_digest": candidate.observation_digest,
        }

        if candidate.status is CandidateStatus.REJECTED:
            return DiscoveryObservation(
                **base,
                outcome=IngestionOutcome.REJECTED,
                error_class="rejected",
                detail={"rejections": list(candidate.rejections)},
            )
        if candidate.status is CandidateStatus.INCOMPLETE:
            return DiscoveryObservation(
                **base,
                outcome=IngestionOutcome.INCOMPLETE,
                error_class="incomplete",
                detail={"missing": list(candidate.missing)},
            )

        try:
            result = self._registry.register(
                context, self._registration_for(candidate)
            )
        except ConflictingRegistration as exc:
            # The registry refused. Reported as a conflict rather than swallowed:
            # something is offering a different contract for a version that may
            # already have been approved and executed against.
            return DiscoveryObservation(
                **base,
                change=ChangeKind.CONFLICTING,
                outcome=IngestionOutcome.CONFLICT,
                error_class="conflicting_registration",
                detail={
                    "message": str(exc),
                    "registered_digest": exc.registered_digest,
                    "offered_digest": exc.offered_digest,
                },
            )

        idempotent = bool(result.events) and getattr(
            result.events[0], "idempotent_registration", False
        )
        stored = result.capability
        return DiscoveryObservation(
            **base,
            change=ChangeKind.UNCHANGED if idempotent else ChangeKind.NEW,
            outcome=(
                IngestionOutcome.ALREADY_REGISTERED
                if idempotent
                else IngestionOutcome.REGISTERED
            ),
            detail={
                "status": stored.status.value,
                "trust": stored.trust.value,
                # Recorded on every ingestion so the invariant is visible in the
                # audit trail rather than only in the code that upholds it.
                "executable": stored.is_executable,
                "contract_digest": stored.digest,
            },
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _observe(
        self,
        context: Any,
        source: CapabilityDiscoverySource,
        candidate: CapabilityCandidate,
        *,
        ingest: bool,
    ) -> DiscoveryObservation:
        if ingest:
            return self.ingest(context, candidate)
        change = (
            self.classify(context, candidate)
            if candidate.may_be_ingested
            else None
        )
        outcome = None
        if candidate.status is CandidateStatus.REJECTED:
            outcome = IngestionOutcome.REJECTED
        elif candidate.status is CandidateStatus.INCOMPLETE:
            outcome = IngestionOutcome.INCOMPLETE
        return DiscoveryObservation(
            source_id=source.source_id,
            source_type=source.source_type.value,
            observed_at=candidate.observed_at,
            candidate_id=candidate.candidate_id,
            candidate_reference=candidate.reference.value,
            observation_digest=candidate.observation_digest,
            change=change,
            outcome=outcome,
            detail={
                "missing": list(candidate.missing),
                "rejections": list(candidate.rejections),
            },
        )

    def _not_seen(
        self,
        context: Any,
        source: CapabilityDiscoverySource,
        candidates: Sequence[CapabilityCandidate],
    ) -> tuple:
        """Registered capabilities from this provider that this run did not see.

        Reported, never acted on. Absence is not revocation: the usual reason a
        capability stops appearing is that a server restarted, and withdrawing
        it would tear down a working inventory on a transient fault.
        """
        seen = {c.reference.value for c in candidates}
        providers = {c.provider for c in candidates}
        if not providers:
            return ()
        from backend.contexts.connectivity.application.commands import ListCapabilities

        registered = self._registry.list(
            context, ListCapabilities(include_undiscoverable=False)
        )
        return tuple(
            sorted(
                d.reference.value
                for d in registered
                if d.provider in providers and d.reference.value not in seen
            )
        )

    def _registered(self, context: Any, reference: CapabilityRef):
        from backend.contexts.connectivity.application.commands import GetCapability

        try:
            return self._registry.get(
                context,
                GetCapability(
                    capability_id=reference.capability_id.value,
                    version=reference.version.number,
                ),
            )
        except (CapabilityNotFound, CapabilityVersionNotFound):
            return None

    def _contract_digest(self, context: Any, candidate: CapabilityCandidate) -> str:
        """The digest the registry would compute for this candidate."""
        from backend.contexts.connectivity.domain.definition import CapabilityDefinition

        probe = CapabilityDefinition.register(
            **self._definition_fields(candidate)
        )
        return probe.digest or ""

    def _definition_fields(self, candidate: CapabilityCandidate) -> dict:
        from backend.contracts.identity import PrincipalKind, PrincipalRef
        from backend.contexts.connectivity.domain.definition import CapabilityTenancy

        return {
            "capability_id": candidate.capability_id,
            "version": candidate.version,
            "name": candidate.name,
            "description": candidate.description or candidate.name,
            "provider": candidate.provider,
            "contract": candidate.contract,
            # The source is the owner of record. A discovered capability is owned
            # by whatever declared it, which is exactly the fact somebody needs
            # when deciding whether to trust it.
            "owner": PrincipalRef(
                principal_id=candidate.source.source_id,
                kind=PrincipalKind.EXTERNAL_SYSTEM,
                display_name=candidate.source.server_name,
            ),
            "tenancy": CapabilityTenancy.PLATFORM,
            "source": candidate.source.source_type,
        }

    def _registration_for(self, candidate: CapabilityCandidate) -> RegisterCapability:
        contract = candidate.contract
        return RegisterCapability(
            capability_id=candidate.capability_id.value,
            version=candidate.version.number,
            name=candidate.name,
            description=candidate.description or candidate.name,
            provider=candidate.provider,
            interface=contract.interface.value,
            side_effect_class=contract.side_effect_class.value,
            effect_semantics=contract.effect_semantics.value,
            isolation_tier=contract.isolation_tier.value,
            code_trust=contract.code_trust.value,
            execution_mode=contract.execution_mode.value,
            owner_id=candidate.source.source_id,
            owner_kind="external_system",
            owner_display_name=candidate.source.server_name,
            tenancy="platform",
            source=candidate.source.source_type.value,
            supported_environments=tuple(
                e.value for e in contract.supported_environments
            ),
            input_schema=(
                contract.input_schema.to_dict() if contract.input_schema else None
            ),
            output_schema=(
                contract.output_schema.to_dict() if contract.output_schema else None
            ),
            required_permissions=tuple(contract.required_permissions),
            idempotency_supported=contract.idempotency_supported,
            retryable=contract.retryable,
            cancellable=contract.cancellable,
            timeout_seconds=contract.timeout_seconds,
            metadata={
                "discovered": True,
                "source_id": candidate.source.source_id,
                "server_name": candidate.source.server_name,
                "endpoint": (
                    candidate.source.endpoint.value
                    if candidate.source.endpoint
                    else None
                ),
                "observation_digest": candidate.observation_digest,
                "observed_at": candidate.observed_at.isoformat(),
                # Preserved as claims, never read as trust.
                "claims": dict(candidate.claims),
                "is_self_declared": candidate.is_self_declared,
            },
        )
