"""World Plane temporal vocabulary — Phase 7.1 (Part K).

Phase 7.1 does NOT implement bitemporal persistence. It defines the temporal
*vocabulary* future phases build on, keeping three times distinct because
collapsing them is the failure the Phase 7.0 audit found everywhere:

  OBSERVATION TIME  (``observed_at``)  — when the fact was true in the world,
                    as reported by the instrument. On an Observation.
  RECORDING TIME    (``recorded_at``)  — when CortexPrime learned/wrote it
                    (transaction time). On every epistemic record.
  VALID TIME        (``valid_from`` / ``valid_to``) — the interval over which a
                    Fact is asserted true in the world. On a Fact.

The Phase 7.0 deployment example stays deterministic: a fact whose *valid* time
begins at 09:58 can be *recorded* at 10:10, and an as-of query on recording
time returns what we believed then, while a query on valid time returns what
was true then. Neither overwrites the other.

These are value objects (frozen Contracts). No clocks, no persistence — a time
is supplied by the caller, never read from a system clock here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["ObservationInstant", "ValidityInterval"]


def _require_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime):
        raise ContractViolation(f"{label} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(
            f"{label} must be timezone-aware; a naive timestamp cannot be "
            "compared across observation, recording and valid time"
        )


@dataclass(frozen=True)
class ObservationInstant(Contract):
    """The two times an observation carries, kept distinct (Part C, Part K).

    ``observed_at`` is when the instrument says the world was in the observed
    state. ``retrieved_at`` is when CortexPrime fetched it. They are different
    facts: a metric scraped at 10:04 may describe the world at 10:00. This is
    the only event-vs-ingest split the Phase 7.0 audit found worth preserving
    (salvaged in spirit from ``contracts.evidence.Citation``).
    """

    CONTRACT_NAME = "cortexprime.world.observation_instant"

    observed_at: datetime
    retrieved_at: datetime

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "observed_at")
        _require_aware(self.retrieved_at, "retrieved_at")
        if self.retrieved_at < self.observed_at:
            raise ContractViolation(
                "retrieved_at precedes observed_at; a fetch cannot happen "
                "before the moment it observed"
            )

    def age_at(self, moment: datetime) -> "Optional[float]":
        """Seconds between ``observed_at`` and ``moment`` — the staleness input.
        Freshness policy lives in a later phase; this only exposes the age."""
        _require_aware(moment, "moment")
        return (moment - self.observed_at).total_seconds()


@dataclass(frozen=True)
class ValidityInterval(Contract):
    """The valid-time interval a Fact asserts (Part D, Part K).

    ``valid_from`` is when the asserted state began being true; ``valid_to`` is
    when it stopped (``None`` means "still asserted / open interval"). This is
    *valid time*, independent of when we recorded the fact — a later
    observation can correct ``valid_from`` backwards without changing when we
    learned it. Supersession (writing ``valid_to`` on a prior version) is a
    later-phase persistence concern; here the interval is only the vocabulary.
    """

    CONTRACT_NAME = "cortexprime.world.validity_interval"

    valid_from: datetime
    valid_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_aware(self.valid_from, "valid_from")
        if self.valid_to is not None:
            _require_aware(self.valid_to, "valid_to")
            if self.valid_to <= self.valid_from:
                raise ContractViolation(
                    "valid_to must be strictly after valid_from; an interval "
                    "that ends at or before it begins asserts nothing"
                )

    @property
    def is_open(self) -> bool:
        """Whether the interval has no recorded end (still asserted)."""
        return self.valid_to is None

    def covers(self, moment: datetime) -> bool:
        """Whether the asserted state was true at ``moment`` in valid time.
        A closed interval is half-open ``[valid_from, valid_to)``."""
        _require_aware(moment, "moment")
        if moment < self.valid_from:
            return False
        if self.valid_to is None:
            return True
        return moment < self.valid_to
