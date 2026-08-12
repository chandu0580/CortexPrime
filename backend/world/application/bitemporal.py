"""Bitemporal projection — the deterministic reading of the fact ledger.

Pure functions over a set of immutable fact versions. No database, no clock, no
model, no randomness: given the same versions and the same query time, the same
answer, every time. This is where the two temporal axes become the two questions
the World Plane must answer:

    WHAT WAS TRUE IN THE WORLD?      -> valid time  (valid_from / valid_to)
    WHAT DID CORTEXPRIME KNOW?       -> knowledge time (recorded_at)

A version is one immutable assertion: "as recorded at ``recorded_at``, the value
was ``value``, valid from ``valid_from`` (open)." The effective end of a value's
valid interval is DERIVED here from the next differing-value version, never
stored and never mutated — so the history is append-only and reconstructable.

The reconciliation rule these projections encode (ADR-065), policy-free:
  * the value effective at valid time T is the one with the greatest
    ``valid_from <= T`` (a later world change wins its own later slot — this is
    valid-time succession, NOT "latest recorded wins");
  * if two versions share that greatest ``valid_from`` with *different* values,
    the instant is CONFLICTED — both are kept, neither is chosen (no authority
    to choose; timestamp order is not epistemic authority);
  * no version covering T at all is UNKNOWN — absence of evidence, never FALSE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from backend.contracts.world import EpistemicStatus

__all__ = [
    "FactVersion",
    "ConflictingValue",
    "FactStateView",
    "HistoryEntry",
    "knowledge_current",
    "project_valid_at",
    "current_state",
    "as_of_valid",
    "as_known",
    "history",
]


@dataclass(frozen=True)
class FactVersion:
    """One immutable fact-version row, as the projection needs to see it.

    A storage-neutral view: the SQL repository builds these from ``cw_fact``
    rows, and the in-memory test repository builds them directly. The projection
    depends on this shape only, never on a database.
    """

    fact_id: str
    semantic_identity: str
    tenant_id: str
    subject_ref: str
    predicate: str
    value: Any
    value_digest: str
    valid_from: datetime
    recorded_at: datetime
    status: EpistemicStatus
    authority: str
    observation_ref: str
    parent_claim_ref: Optional[str] = None


@dataclass(frozen=True)
class ConflictingValue:
    """One side of an unresolved conflict — a value and the evidence for it."""

    value: Any
    value_digest: str
    fact_id: str
    observation_ref: str


@dataclass(frozen=True)
class FactStateView:
    """The effective state of one semantic identity at one point in the two
    temporal axes. ``status`` is the deterministic epistemic answer:

      * AFFIRMED   — a single value is effective; ``value`` is it.
      * CONFLICTED — two values are effective at the same valid instant;
        ``value`` is None and ``conflicts`` lists both, each with its evidence.
      * UNKNOWN    — no version covers the queried valid time; ``value`` is None.
        (UNKNOWN is not FALSE.)
    """

    status: EpistemicStatus
    value: Any = None
    value_digest: Optional[str] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None
    evidence: tuple[str, ...] = ()          # observation_refs grounding the state
    fact_ids: tuple[str, ...] = ()
    conflicts: tuple[ConflictingValue, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.status is not EpistemicStatus.UNKNOWN


@dataclass(frozen=True)
class HistoryEntry:
    """One version in the append-only history of a semantic identity."""

    fact_id: str
    value: Any
    valid_from: datetime
    recorded_at: datetime
    status: EpistemicStatus
    observation_ref: str
    parent_claim_ref: Optional[str]


def knowledge_current(
    versions: tuple[FactVersion, ...], known_at: Optional[datetime]
) -> tuple[FactVersion, ...]:
    """The versions CortexPrime had recorded by knowledge time ``known_at``.

    ``None`` means "latest knowledge" — every version. This is the transaction-
    time filter: a version recorded after ``known_at`` was not yet known then, so
    an as-known query cannot see it.
    """
    if known_at is None:
        return tuple(versions)
    return tuple(v for v in versions if v.recorded_at <= known_at)


def project_valid_at(
    versions: tuple[FactVersion, ...], at_valid: datetime
) -> FactStateView:
    """The effective state at world/valid time ``at_valid`` over ``versions``.

    Deterministic: the value with the greatest ``valid_from <= at_valid`` wins;
    a tie on that ``valid_from`` with differing values is CONFLICTED; nothing
    covering ``at_valid`` is UNKNOWN. ``valid_to`` is derived as the next
    differing-value ``valid_from`` after the winning slot (open if none).
    """
    covering = [v for v in versions if v.valid_from <= at_valid]
    if not covering:
        return FactStateView(status=EpistemicStatus.UNKNOWN)

    max_vf = max(v.valid_from for v in covering)
    top = [v for v in covering if v.valid_from == max_vf]
    distinct = {v.value_digest for v in top}

    if len(distinct) > 1:
        # Two values asserted effective from the same valid instant, no authority
        # to choose. Both retained and reported; the instant is CONFLICTED.
        conflicts = tuple(
            ConflictingValue(
                value=v.value, value_digest=v.value_digest,
                fact_id=v.fact_id, observation_ref=v.observation_ref)
            for v in sorted(top, key=lambda v: (v.value_digest, v.fact_id))
        )
        return FactStateView(
            status=EpistemicStatus.CONFLICTED,
            valid_from=max_vf,
            evidence=tuple(v.observation_ref for v in top),
            fact_ids=tuple(v.fact_id for v in top),
            conflicts=conflicts,
        )

    # A single effective value. Its interval ends at the next CHANGE — the
    # smallest valid_from strictly after max_vf whose value differs.
    winner = top[0]
    later_changes = [
        v.valid_from for v in versions
        if v.valid_from > max_vf and v.value_digest != winner.value_digest
    ]
    valid_to = min(later_changes) if later_changes else None
    return FactStateView(
        status=EpistemicStatus.AFFIRMED,
        value=winner.value,
        value_digest=winner.value_digest,
        valid_from=max_vf,
        valid_to=valid_to,
        evidence=(winner.observation_ref,),
        fact_ids=(winner.fact_id,),
    )


def current_state(
    versions: tuple[FactVersion, ...], now: datetime
) -> FactStateView:
    """A — what the World Plane currently represents: latest knowledge, valid at
    ``now``."""
    return project_valid_at(knowledge_current(versions, None), now)


def as_of_valid(
    versions: tuple[FactVersion, ...],
    at_valid: datetime,
    *,
    known_at: Optional[datetime] = None,
) -> FactStateView:
    """B — what was valid at world time ``at_valid`` (per latest knowledge, or
    per knowledge as of ``known_at`` if given). The two axes are independent and
    both queryable together."""
    return project_valid_at(knowledge_current(versions, known_at), at_valid)


def as_known(
    versions: tuple[FactVersion, ...], known_at: datetime
) -> FactStateView:
    """C — what CortexPrime had recorded by knowledge time ``known_at``,
    projected to the world as it understood it then (valid at ``known_at``).
    Versions recorded after ``known_at`` are invisible — so a fact learned later
    cannot leak into what we knew earlier."""
    return project_valid_at(knowledge_current(versions, known_at), known_at)


def history(versions: tuple[FactVersion, ...]) -> tuple[HistoryEntry, ...]:
    """D — the full append-only version history of a semantic identity, in the
    order it was recorded then by valid time. Nothing is elided; a superseded or
    conflicted version remains."""
    ordered = sorted(versions, key=lambda v: (v.recorded_at, v.valid_from, v.fact_id))
    return tuple(
        HistoryEntry(
            fact_id=v.fact_id, value=v.value, valid_from=v.valid_from,
            recorded_at=v.recorded_at, status=v.status,
            observation_ref=v.observation_ref, parent_claim_ref=v.parent_claim_ref)
        for v in ordered
    )
