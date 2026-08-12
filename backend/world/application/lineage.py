"""Source lineage — where evidence ultimately came from, deterministically.

Phase 7.5 corroboration treated a distinct ``source_ref`` as independent
evidence. That is optimistic: two providers may both read the same API, the same
cache, the same upstream event, or a mirror of the same database. A distinct
source reference is NOT proof of independent evidence.

Lineage answers "where did this evidence originate?" with the strongest model
that can actually be *verified from available metadata* — an explicit, deterministic
policy mapping a source to an origin and a relation. It does not attempt perfect
causal provenance; it attempts honesty:

  * two sources that resolve to the SAME known origin are correlated, not
    independent;
  * two sources with DISTINCT known origins are independent;
  * a source whose lineage is UNKNOWN can never be *claimed* independent —
    false certainty is worse than admitting the evidence is insufficient.

Lineage is a third concept, separate from authority (who has standing) and
corroboration (is there independent support). This module owns only lineage; the
corroboration revision that consumes it lives in ``belief.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

__all__ = [
    "LineageRelation",
    "SourceLineage",
    "LineageRule",
    "LineagePolicy",
]


class LineageRelation(str, Enum):
    """How a source relates to its origin — verifiable from metadata, not a
    numeric trust score."""

    DIRECT = "direct"
    """The source IS the origin's own interface (e.g. the cluster's API for its
    own state). The strongest lineage."""
    DERIVED = "derived"
    """The source computes/scrapes from the origin (e.g. Prometheus from
    kube-state-metrics from the K8s API). Not independent of the origin."""
    MIRRORED = "mirrored"
    """The source replicates the origin (a cache, a replica, a copied config).
    Not independent of the origin."""
    UNKNOWN = "unknown"
    """Lineage is not established. Independence cannot be claimed — the safe
    result is 'insufficient', never 'independent'."""


@dataclass(frozen=True)
class SourceLineage:
    """The resolved lineage of one source. ``origin_id`` is the shared root two
    sources are compared on; ``relation`` says how the source relates to it."""

    source_kind: str
    source_ref: str
    origin_id: Optional[str]
    relation: LineageRelation

    @property
    def is_known(self) -> bool:
        """Whether lineage is established well enough to reason about
        independence. UNKNOWN or a missing origin is not."""
        return self.origin_id is not None and self.relation is not LineageRelation.UNKNOWN

    def to_dict(self) -> dict:
        return {"source_kind": self.source_kind, "source_ref": self.source_ref,
                "origin_id": self.origin_id, "relation": self.relation.value}


@dataclass(frozen=True)
class LineageRule:
    """Maps a source (by kind and/or ref) to an origin and a relation. A ``None``
    match field matches anything; first matching rule wins."""

    origin_id: str
    relation: LineageRelation
    source_kind: Optional[str] = None
    source_ref: Optional[str] = None

    def matches(self, *, source_kind: str, source_ref: str) -> bool:
        if self.source_kind is not None and self.source_kind != source_kind:
            return False
        if self.source_ref is not None and self.source_ref != source_ref:
            return False
        return True


@dataclass(frozen=True)
class LineagePolicy:
    """An ordered set of explicit lineage rules. A source matched by no rule has
    UNKNOWN lineage — its independence is never assumed. Deterministic config; a
    model does not define lineage."""

    rules: tuple[LineageRule, ...] = ()
    name: str = "lineage-policy"

    @classmethod
    def none(cls) -> "LineagePolicy":
        """A policy that establishes no lineage — every source is UNKNOWN, so
        corroboration can never claim proven independence (the honest default
        until lineage is stated)."""
        return cls(rules=(), name="no-lineage-policy")

    @property
    def governs(self) -> bool:
        return bool(self.rules)

    def lineage_of(self, *, source_kind: str, source_ref: str) -> SourceLineage:
        rule = next(
            (r for r in self.rules
             if r.matches(source_kind=source_kind, source_ref=source_ref)),
            None,
        )
        if rule is None:
            return SourceLineage(source_kind=source_kind, source_ref=source_ref,
                                 origin_id=None, relation=LineageRelation.UNKNOWN)
        return SourceLineage(source_kind=source_kind, source_ref=source_ref,
                             origin_id=rule.origin_id, relation=rule.relation)
