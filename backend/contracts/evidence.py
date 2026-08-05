"""Evidence vocabulary.

Owner: BC-2 Evidence.

Encodes Constitution P1 ("Evidence or Silence") and P6 ("Borrowed Telemetry").
Two rules shape this module:

1. **Unavailability is a value, not an absence.** ``EvidenceSet`` records which
   sources failed alongside what was retrieved. A source that errored and a
   source that legitimately returned nothing are different facts, and collapsing
   them into an empty list is how "no evidence of a problem" silently becomes
   "evidence of no problem" (BC-2 failure boundary).

2. **We cite, we do not copy.** ``EvidenceItem`` carries the excerpt that
   supports a claim plus the query that produced it -- enough to defend the
   finding and reproduce it, not enough to constitute a telemetry store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "EvidenceKind",
    "SourceStatus",
    "Citation",
    "EvidenceItem",
    "SourceOutcome",
    "EvidenceSet",
]


class EvidenceKind(str, Enum):
    """What sort of observation an item represents."""

    METRIC = "metric"
    LOG = "log"
    TRACE = "trace"
    EVENT = "event"
    CONFIGURATION = "configuration"
    CHANGE = "change"
    """A deployment, config edit, or code change. Privileged: "what changed" is
    the highest-yield operational question (Constitution S7)."""

    TOPOLOGY = "topology"


class SourceStatus(str, Enum):
    """How a source responded."""

    RETURNED_DATA = "returned_data"
    RETURNED_EMPTY = "returned_empty"
    """Queried successfully; the source genuinely has nothing. A real finding."""

    UNAVAILABLE = "unavailable"
    """Could not be queried. NOT the same as empty -- reasoning must discount it."""

    NOT_CONFIGURED = "not_configured"
    """No integration exists. A gap in coverage, not a gap in the data."""

    @property
    def is_informative(self) -> bool:
        """Whether an absence of findings from this source means anything."""
        return self in {SourceStatus.RETURNED_DATA, SourceStatus.RETURNED_EMPTY}


@dataclass(frozen=True)
class Citation(Contract):
    """A stable, reproducible pointer to one observation.

    ``query`` is mandatory: a citation that cannot be re-executed is an
    assertion wearing a citation's clothes.
    """

    CONTRACT_NAME = "cortexprime.evidence.citation"

    citation_id: str
    source_system: str
    query: str
    observed_at: datetime
    retrieved_at: datetime

    def __post_init__(self) -> None:
        for label, value in (
            ("citation_id", self.citation_id),
            ("source_system", self.source_system),
            ("query", self.query),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if self.observed_at.tzinfo is None or self.retrieved_at.tzinfo is None:
            raise ContractViolation("citation timestamps must be timezone-aware")
        if self.retrieved_at < self.observed_at:
            raise ContractViolation("retrieved_at must not precede observed_at")

    def staleness_at(self, moment: datetime) -> timedelta:
        """How old the underlying observation is as of ``moment``."""
        if moment.tzinfo is None:
            raise ContractViolation("moment must be timezone-aware")
        return moment - self.observed_at


@dataclass(frozen=True)
class EvidenceItem(Contract):
    """One cited observation.

    ``excerpt`` is text, not structured data, and is expected to be small. This
    is a deliberate constraint: a contract that comfortably carried megabytes of
    telemetry would make violating P6 easy.
    """

    CONTRACT_NAME = "cortexprime.evidence.item"

    kind: EvidenceKind
    citation: Citation
    excerpt: str
    summary: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.kind, EvidenceKind):
            raise ContractViolation("kind must be an EvidenceKind")
        if not isinstance(self.excerpt, str) or not self.excerpt.strip():
            raise ContractViolation("excerpt must be non-blank; an item with no content is not evidence")


@dataclass(frozen=True)
class SourceOutcome(Contract):
    """What happened when one source was queried.

    Present for every source attempted, including those that returned nothing,
    so that a reader can distinguish "we looked and found nothing" from "we
    never looked".
    """

    CONTRACT_NAME = "cortexprime.evidence.source_outcome"

    source_system: str
    status: SourceStatus
    detail: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_system, str) or not self.source_system.strip():
            raise ContractViolation("source_system must be a non-blank string")
        if not isinstance(self.status, SourceStatus):
            raise ContractViolation("status must be a SourceStatus")
        if self.status is SourceStatus.UNAVAILABLE and not (self.detail or "").strip():
            raise ContractViolation(
                "an unavailable source must state why; silent unavailability is how "
                "missing data becomes a false negative"
            )


@dataclass(frozen=True)
class EvidenceSet(Contract):
    """Everything gathered for one question, plus what could not be gathered.

    ``is_complete`` lets a consumer ask, in one call, whether an absence of
    findings is meaningful. Reasoning is expected to check it before concluding
    that nothing is wrong.
    """

    CONTRACT_NAME = "cortexprime.evidence.set"

    assembled_at: datetime
    items: tuple[EvidenceItem, ...] = field(default_factory=tuple)
    source_outcomes: tuple[SourceOutcome, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.assembled_at.tzinfo is None:
            raise ContractViolation("assembled_at must be timezone-aware")
        if not isinstance(self.items, tuple) or not isinstance(self.source_outcomes, tuple):
            raise ContractViolation("evidence collections must be tuples")

        cited_sources = {item.citation.source_system for item in self.items}
        reported_sources = {outcome.source_system for outcome in self.source_outcomes}
        missing = cited_sources - reported_sources
        if missing:
            raise ContractViolation(
                f"every cited source must have a recorded outcome; missing: {sorted(missing)}"
            )

    @property
    def is_complete(self) -> bool:
        """True when every attempted source answered informatively."""
        return all(outcome.status.is_informative for outcome in self.source_outcomes)

    @property
    def degraded_sources(self) -> tuple[SourceOutcome, ...]:
        """Sources whose silence must not be read as a negative finding."""
        return tuple(
            outcome for outcome in self.source_outcomes if not outcome.status.is_informative
        )

    def items_of_kind(self, kind: EvidenceKind) -> tuple[EvidenceItem, ...]:
        return tuple(item for item in self.items if item.kind is kind)
