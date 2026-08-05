"""Knowledge vocabulary.

Owner: BC-7 Knowledge.

Constitution S5 defines four knowledge kinds with different lifecycles and,
critically, different *authority*. Invariant I7 states: experiential memory may
propose; it may never authorize.

``KnowledgeItem`` therefore carries an explicit ``authority`` that consumers can
check, and ``AssembledContext`` refuses to construct if an experiential item
claims authoritative status. The guard is here rather than in BC-7 because a
rule enforced at the type boundary cannot be forgotten by a caller.

This module also implements the Constitution's stated guard on memory: prior
experience is advisory and weighted, never dispositive, because accumulated
agent memory can degrade performance through error propagation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "KnowledgeKind",
    "KnowledgeAuthority",
    "KnowledgeItem",
    "AssembledContext",
]


class KnowledgeKind(str, Enum):
    """The four kinds, each with its own lifecycle (Constitution S5)."""

    STRUCTURAL = "structural"
    """What exists and what depends on what. Cached, expires, never "updated"."""

    PROCEDURAL = "procedural"
    """Runbooks and curated remedies. Versioned, owned, reviewable."""

    EXPERIENTIAL = "experiential"
    """What happened before. Append-only, advisory, weighted by outcome."""

    EVIDENCE_DERIVED = "evidence_derived"
    """Conclusions previously drawn from evidence. Advisory; re-verify before reuse."""

    @property
    def may_be_authoritative(self) -> bool:
        """Only curated procedure and current structure can be authoritative (I7)."""
        return self in {KnowledgeKind.STRUCTURAL, KnowledgeKind.PROCEDURAL}


class KnowledgeAuthority(str, Enum):
    """How much weight a consumer may place on an item."""

    AUTHORITATIVE = "authoritative"
    """May be relied upon directly."""

    ADVISORY = "advisory"
    """May inform, must not decide."""


@dataclass(frozen=True)
class KnowledgeItem(Contract):
    """One piece of retrieved context, tagged with provenance and authority.

    ``confidence`` is mandatory for advisory items and forbidden for
    authoritative ones: an authoritative item with a confidence score is
    self-contradictory, and an advisory item without one gives the consumer no
    basis for discounting it.
    """

    CONTRACT_NAME = "cortexprime.knowledge.item"

    item_id: str
    kind: KnowledgeKind
    authority: KnowledgeAuthority
    content: str
    recorded_at: datetime
    confidence: Optional[float] = None
    source_reference: Optional[str] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id.strip():
            raise ContractViolation("item_id must be a non-blank string")
        if not isinstance(self.kind, KnowledgeKind):
            raise ContractViolation("kind must be a KnowledgeKind")
        if not isinstance(self.authority, KnowledgeAuthority):
            raise ContractViolation("authority must be a KnowledgeAuthority")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ContractViolation("content must be non-blank")
        if self.recorded_at.tzinfo is None:
            raise ContractViolation("recorded_at must be timezone-aware")

        # Invariant I7, enforced at construction.
        if (
            self.authority is KnowledgeAuthority.AUTHORITATIVE
            and not self.kind.may_be_authoritative
        ):
            raise ContractViolation(
                f"{self.kind.value} knowledge cannot be authoritative; experience and "
                "prior conclusions may propose but never authorize (Constitution I7)"
            )

        if self.authority is KnowledgeAuthority.ADVISORY:
            if self.confidence is None:
                raise ContractViolation(
                    "advisory knowledge must carry a confidence so consumers can discount it"
                )
            if not 0.0 <= self.confidence <= 1.0:
                raise ContractViolation("confidence must be between 0.0 and 1.0")
        elif self.confidence is not None:
            raise ContractViolation("authoritative knowledge must not carry a confidence score")

        if self.expires_at is not None:
            if self.expires_at.tzinfo is None:
                raise ContractViolation("expires_at must be timezone-aware")
            if self.expires_at <= self.recorded_at:
                raise ContractViolation("expires_at must be after recorded_at")

    def is_expired_at(self, moment: datetime) -> bool:
        if moment.tzinfo is None:
            raise ContractViolation("moment must be timezone-aware")
        return self.expires_at is not None and moment >= self.expires_at


@dataclass(frozen=True)
class AssembledContext(Contract):
    """The bounded, provenance-tagged context handed to reasoning.

    Constitution S5: "The output is a bounded, provenance-tagged context object
    -- never a raw result list handed to a model."

    An empty context is explicitly valid. Missions must be able to run with no
    prior knowledge (BC-7 failure boundary): knowledge is an accelerant, never a
    dependency.
    """

    CONTRACT_NAME = "cortexprime.knowledge.assembled_context"

    assembled_at: datetime
    goal_reference: str
    items: tuple[KnowledgeItem, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.assembled_at.tzinfo is None:
            raise ContractViolation("assembled_at must be timezone-aware")
        if not isinstance(self.goal_reference, str) or not self.goal_reference.strip():
            raise ContractViolation("goal_reference must be a non-blank string")
        if not isinstance(self.items, tuple):
            raise ContractViolation("items must be a tuple (contracts are immutable)")

        identifiers = [item.item_id for item in self.items]
        if len(set(identifiers)) != len(identifiers):
            raise ContractViolation("items must not contain duplicate item_id values")

    @property
    def authoritative_items(self) -> tuple[KnowledgeItem, ...]:
        return tuple(
            item for item in self.items if item.authority is KnowledgeAuthority.AUTHORITATIVE
        )

    @property
    def advisory_items(self) -> tuple[KnowledgeItem, ...]:
        return tuple(item for item in self.items if item.authority is KnowledgeAuthority.ADVISORY)

    def live_items(self, moment: datetime) -> tuple[KnowledgeItem, ...]:
        """Items that have not expired as of ``moment``."""
        return tuple(item for item in self.items if not item.is_expired_at(moment))
