"""Discovery outcomes: source health, change detection, observations.

The rule this module exists to enforce
----------------------------------------
**Absence is not revocation.** A capability that did not appear in this run is
``NOT_SEEN`` -- never revoked, never disabled. The distinction matters because
the most common reason a capability stops appearing is that the source was
briefly unreachable, and a runtime that revoked on absence would tear down a
working inventory every time a server restarted.

Withdrawing a capability is a governance decision made by somebody who knows why.
Discovery's job is to report what it saw and to be honest that it may have seen
nothing for uninteresting reasons.

Which is why source health is separate from results
-----------------------------------------------------
"The source returned zero capabilities" and "the source could not be reached"
must never collapse into the same fact. A timeout that reads as an empty
inventory is how every capability from one provider silently disappears at once.
``SourceHealth`` is checked before results are interpreted at all, and an
unhealthy source's empty result is reported as *unknown*, not as *empty*.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "SourceHealth",
    "ChangeKind",
    "IngestionOutcome",
    "DiscoveryObservation",
    "DiscoveryReport",
]


class SourceHealth(str, Enum):
    """Whether what a source told us can be believed to be its whole story."""

    HEALTHY = "healthy"
    """Answered, and the answer parsed."""

    EMPTY = "empty"
    """Answered, and genuinely offers nothing. Distinct from UNAVAILABLE: this
    one is a fact about the source, not about the network."""

    MALFORMED = "malformed"
    """Answered with something that is not what it claims to be. Whatever parsed
    may be kept; the rest is reported, never guessed at."""

    UNAVAILABLE = "unavailable"
    """Could not be reached. Says nothing whatsoever about what it offers."""

    UNAUTHORIZED = "unauthorized"
    """Reached, and refused us. Also says nothing about what it offers -- there
    may be a full inventory behind that refusal."""

    @property
    def results_are_complete(self) -> bool:
        """Whether this run's results can be read as the source's full inventory.

        The single most important property here. Only a healthy or genuinely
        empty source supports the conclusion "these are all the capabilities" --
        which is the conclusion any change detection depends on.
        """
        return self in {SourceHealth.HEALTHY, SourceHealth.EMPTY}

    @property
    def is_reachable(self) -> bool:
        return self not in {SourceHealth.UNAVAILABLE, SourceHealth.UNAUTHORIZED}


class ChangeKind(str, Enum):
    """How an observation relates to what the registry already holds."""

    NEW = "new"
    """No registration exists for this reference."""

    UNCHANGED = "unchanged"
    """Registered, and the contract digest matches."""

    CHANGED = "changed"
    """A *new version* of something already registered. Ordinary and safe: a new
    version is a new contract, registered alongside the old one."""

    CONFLICTING = "conflicting"
    """The same version, with a different contract. Refused. Something is trying
    to redefine a version that may already have been approved and executed
    against, and accepting it would turn an approval for one thing into
    permission for another."""

    NOT_SEEN = "not_seen"
    """Registered, and absent from this run. **Not** revoked. Reported so a human
    can decide, because the ordinary cause is a restart, not a withdrawal."""

    @property
    def is_actionable(self) -> bool:
        """Whether ingestion would do anything."""
        return self in {ChangeKind.NEW, ChangeKind.CHANGED}

    @property
    def needs_attention(self) -> bool:
        return self in {ChangeKind.CONFLICTING, ChangeKind.NOT_SEEN}


class IngestionOutcome(str, Enum):
    """What ingesting one candidate actually did."""

    REGISTERED = "registered"
    """A new version was recorded, as REGISTERED and UNVERIFIED. Not enabled,
    not trusted, not executable."""

    ALREADY_REGISTERED = "already_registered"
    """Identical to what is stored. Nothing changed -- notably, no trust or
    lifecycle decision already made about it was disturbed."""

    CONFLICT = "conflict"
    """Refused: same version, different contract."""

    INCOMPLETE = "incomplete"
    """The source did not provide enough to register anything."""

    REJECTED = "rejected"
    """Structurally unusable."""

    @property
    def changed_the_registry(self) -> bool:
        return self is IngestionOutcome.REGISTERED


@dataclass(frozen=True)
class DiscoveryObservation:
    """One thing seen, and what came of it."""

    source_id: str
    source_type: str
    observed_at: datetime
    candidate_id: Optional[str] = None
    candidate_reference: Optional[str] = None
    observation_digest: Optional[str] = None
    change: Optional[ChangeKind] = None
    outcome: Optional[IngestionOutcome] = None
    error_class: Optional[str] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ContractViolation("source_id must be non-blank text")
        if self.observed_at.tzinfo is None:
            raise ContractViolation("observed_at must be timezone-aware")

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "observed_at": self.observed_at.isoformat(),
            "candidate_id": self.candidate_id,
            "candidate_reference": self.candidate_reference,
            "observation_digest": self.observation_digest,
            "change": self.change.value if self.change else None,
            "outcome": self.outcome.value if self.outcome else None,
            "error_class": self.error_class,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True)
class DiscoveryReport:
    """Everything one discovery run saw from one source."""

    source_id: str
    source_type: str
    health: SourceHealth
    started_at: datetime
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    candidates: tuple = ()
    observations: tuple = ()
    not_seen: tuple = ()
    dropped_for_budget: int = 0
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.health, SourceHealth):
            raise ContractViolation("health must be a SourceHealth")
        if not self.health.is_reachable and self.candidates:
            raise ContractViolation(
                f"a {self.health.value} source cannot have produced candidates; "
                "reporting both would let an unreachable source look like a "
                "partially working one"
            )
        # The invariant that stops a timeout from erasing an inventory.
        if not self.health.results_are_complete and self.not_seen:
            raise ContractViolation(
                f"a {self.health.value} source cannot report capabilities as "
                "not-seen; it did not tell us what it has, so absence from this "
                "run is a fact about the network rather than about the source"
            )

    @property
    def usable_candidates(self) -> tuple:
        return tuple(c for c in self.candidates if c.may_be_ingested)

    @property
    def conflicts(self) -> tuple:
        return tuple(
            o for o in self.observations if o.change is ChangeKind.CONFLICTING
        )

    @property
    def registered_count(self) -> int:
        return sum(
            1
            for o in self.observations
            if o.outcome is IngestionOutcome.REGISTERED
        )

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "health": self.health.value,
            "results_are_complete": self.health.results_are_complete,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "candidate_count": len(self.candidates),
            "usable_count": len(self.usable_candidates),
            "conflict_count": len(self.conflicts),
            "registered_count": self.registered_count,
            "not_seen": list(self.not_seen),
            "dropped_for_budget": self.dropped_for_budget,
            "error": self.error,
            "candidates": [c.to_dict() for c in self.candidates],
            "observations": [o.to_dict() for o in self.observations],
        }
