"""Authority — a deterministic, explicit, source-tier decision. Never recency,
never a model, never an arbitrary number.

A fact has provenance, a source, a timestamp, an observation, and an authority —
and these are not the same thing (Part E). Authority answers "why is this value
the one to rely on?" It is decided by an explicit ``AuthorityPolicy`` that maps a
source to a ``SourceAuthority`` tier (the existing contract vocabulary:
UNVERIFIED < SINGLE_SOURCE < CORROBORATED < AUTHORITATIVE). A source the policy
does not name is UNVERIFIED — it cannot alone be authoritative.

Two hard rules (Part F, K):
  * **Recency is not authority.** A newer observation from a lower-tier source
    (e.g. a stale cache) never overrides a higher-tier source (e.g. the cluster's
    own API). The decision is by tier, and recency is only a tiebreak *within*
    one tier (that is just the same source changing over time).
  * **No authority to choose ⇒ CONFLICTED.** When the highest tier covering an
    instant holds two different values, neither is selected; both are preserved
    and returned. The model never breaks the tie.

The policy is deterministic config, auditable, and tenant-scoped by the query
that applies it. A model cannot define authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from backend.contracts.world import SourceAuthority

__all__ = [
    "AuthorityStatus",
    "AuthorityRule",
    "AuthorityPolicy",
    "AuthorityAlternative",
    "AuthorityDecision",
]


class AuthorityStatus(str, Enum):
    """The outcome of an authority decision."""

    RESOLVED = "resolved"
    """One source's value is authoritative; ``value`` is it, with a reason."""
    CONFLICTED = "conflicted"
    """The highest tier disagrees at the same valid instant; both preserved."""
    UNGOVERNED = "ungoverned"
    """No authority policy governs this fact; the temporal projection stands."""
    UNKNOWN = "unknown"
    """No evidence covers the queried time."""


@dataclass(frozen=True)
class AuthorityRule:
    """Maps a source (by kind and/or reference) to a trust tier. A ``None`` field
    matches anything; first matching rule wins."""

    tier: SourceAuthority
    source_kind: Optional[str] = None
    source_ref: Optional[str] = None

    def matches(self, *, source_kind: Optional[str], source_ref: Optional[str]) -> bool:
        if self.source_kind is not None and self.source_kind != source_kind:
            return False
        if self.source_ref is not None and self.source_ref != source_ref:
            return False
        return True


@dataclass(frozen=True)
class AuthorityPolicy:
    """An ordered set of authority rules. A source matched by no rule is
    UNVERIFIED (cannot alone ground an authoritative fact). An empty policy
    governs nothing — the query then reports the temporal projection unchanged."""

    rules: tuple[AuthorityRule, ...] = ()
    name: str = "authority-policy"

    @classmethod
    def none(cls) -> "AuthorityPolicy":
        return cls(rules=(), name="no-authority-policy")

    @property
    def governs(self) -> bool:
        return bool(self.rules)

    def authority_of(
        self, *, source_kind: Optional[str], source_ref: Optional[str]
    ) -> SourceAuthority:
        rule = next(
            (r for r in self.rules
             if r.matches(source_kind=source_kind, source_ref=source_ref)),
            None,
        )
        return rule.tier if rule is not None else SourceAuthority.UNVERIFIED


@dataclass(frozen=True)
class AuthorityAlternative:
    """A value that was not selected, with the source and tier behind it —
    preserved so the decision is explainable and no evidence path is lost."""

    value: Any
    source_kind: str
    source_ref: str
    tier: SourceAuthority
    observation_ref: str


@dataclass(frozen=True)
class AuthorityDecision:
    """Why a value is (or is not) authoritative — the auditable record.

    ``status`` RESOLVED carries the chosen ``value``/``source``/``tier`` and a
    ``reason``; CONFLICTED carries no value and lists every competing side in
    ``alternatives``; UNGOVERNED means no policy applied; UNKNOWN means nothing
    covered the queried time. Losing/competing values always appear in
    ``alternatives`` (Part H)."""

    status: AuthorityStatus
    reason: str
    value: Any = None
    source_kind: Optional[str] = None
    source_ref: Optional[str] = None
    tier: Optional[SourceAuthority] = None
    alternatives: tuple[AuthorityAlternative, ...] = ()

    @property
    def is_conflicted(self) -> bool:
        return self.status is AuthorityStatus.CONFLICTED
