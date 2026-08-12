"""Freshness — an explicit, domain-specific policy, never a universal TTL.

The Phase 7.0 audit's staleness failure was TTL-free caches. The opposite
failure is just as wrong: declaring "everything older than 5 minutes is stale"
for every fact regardless of domain. Phase 7.4 refuses both.

Freshness here is a *policy the caller supplies*, built from explicit rules that
each say what freshness means for a specific source/predicate. A fact the policy
does not cover is **UNKNOWN**, never STALE — absence of a freshness rule is not
evidence of staleness, and staleness is never falseness (STALE ≠ FALSE ≠ 0).

No hidden clock: the evaluation time is passed in, so freshness is reproducible
under a deterministic clock in tests and under the governed clock in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

__all__ = [
    "FreshnessState",
    "FreshnessRule",
    "FreshnessPolicy",
    "FreshnessResult",
]


class FreshnessState(str, Enum):
    """How fresh the evidence is — a separate axis from the fact's truth value.

    STALE is NOT FALSE: a stale ``replicas = 5`` is still 5, just old enough that
    a consequential action should re-observe first. UNKNOWN is NOT FALSE either:
    no policy governs this fact, so freshness is simply not classified."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class FreshnessRule:
    """One explicit freshness rule. It matches an observation by source kind
    and/or predicate (a ``None`` field matches anything), and declares the
    horizon in seconds beyond which evidence for that match is STALE.

    There is no default horizon: a fact matched by no rule is UNKNOWN. That is
    the discipline — freshness must be *stated* for a domain, never assumed."""

    horizon_seconds: float
    source_kind: Optional[str] = None
    predicate: Optional[str] = None
    name: str = "freshness-rule"

    def __post_init__(self) -> None:
        if self.horizon_seconds <= 0:
            raise ValueError("horizon_seconds must be positive")

    def matches(self, *, source_kind: Optional[str], predicate: Optional[str]) -> bool:
        if self.source_kind is not None and self.source_kind != source_kind:
            return False
        if self.predicate is not None and self.predicate != predicate:
            return False
        return True


@dataclass(frozen=True)
class FreshnessResult:
    """The freshness verdict for one fact, with the evidence for it."""

    state: FreshnessState
    evaluated_at: datetime
    age_seconds: Optional[float] = None
    horizon_seconds: Optional[float] = None
    policy_name: str = ""
    reason: str = ""

    @property
    def is_stale(self) -> bool:
        return self.state is FreshnessState.STALE


@dataclass(frozen=True)
class FreshnessPolicy:
    """An ordered set of explicit freshness rules. First matching rule wins.

    An empty policy classifies everything UNKNOWN — the honest default when no
    domain freshness has been stated. Construct with explicit rules only."""

    rules: tuple[FreshnessRule, ...] = ()
    name: str = "freshness-policy"

    @classmethod
    def none(cls) -> "FreshnessPolicy":
        """A policy that governs nothing — every fact is UNKNOWN freshness."""
        return cls(rules=(), name="no-freshness-policy")

    @property
    def governs(self) -> bool:
        return bool(self.rules)

    def evaluate(
        self,
        *,
        observed_at: Optional[datetime],
        now: datetime,
        source_kind: Optional[str],
        predicate: Optional[str],
    ) -> FreshnessResult:
        """Classify the freshness of evidence observed at ``observed_at`` as of
        ``now``. Returns UNKNOWN when no rule matches or no observation time is
        available — never STALE by default, never FALSE."""
        rule = next(
            (r for r in self.rules
             if r.matches(source_kind=source_kind, predicate=predicate)),
            None,
        )
        if rule is None:
            return FreshnessResult(
                state=FreshnessState.UNKNOWN, evaluated_at=now,
                policy_name=self.name,
                reason="no freshness rule governs this fact; staleness is not "
                       "assumed (UNKNOWN, not STALE, never FALSE)")
        if observed_at is None:
            return FreshnessResult(
                state=FreshnessState.UNKNOWN, evaluated_at=now,
                horizon_seconds=rule.horizon_seconds, policy_name=self.name,
                reason="no observation time available to age against")
        age = (now - observed_at).total_seconds()
        state = FreshnessState.FRESH if age <= rule.horizon_seconds else FreshnessState.STALE
        return FreshnessResult(
            state=state, evaluated_at=now, age_seconds=age,
            horizon_seconds=rule.horizon_seconds, policy_name=self.name,
            reason=(f"observed {age:.0f}s ago; rule {rule.name!r} horizon is "
                    f"{rule.horizon_seconds:.0f}s → {state.value} "
                    "(STALE is not FALSE)"))
