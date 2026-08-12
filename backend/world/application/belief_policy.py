"""Governed belief policy — when is a belief *sufficiently supported*?

Phase 7.4 established policies as deterministic configuration. This adds the
support policy: an explicit, versioned, inspectable rule for whether a belief's
evidence meets a governed bar. It answers "is this belief acceptable to act on?"
WITHOUT inventing a confidence number and WITHOUT letting a model choose.

Acceptance is a separate axis from ``EpistemicStatus`` (which stays AFFIRMED /
STALE / CONFLICTED / UNKNOWN). A belief may be AFFIRMED yet only PROVISIONAL if
the support requirement is not met. Absence never becomes FALSE; an unmet
requirement is UNMET, not false.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.world.application.authority import AuthorityStatus
from backend.world.application.belief import CorroborationLevel

__all__ = [
    "SupportRequirement",
    "BeliefAcceptance",
    "BeliefPolicyResult",
    "BeliefSupportPolicy",
    "BeliefSupportRule",
]


class SupportRequirement(str, Enum):
    """What evidence a belief needs to be ACCEPTED — explicit, no numbers."""

    AUTHORITATIVE = "authoritative"
    """An authoritative source resolving the value is sufficient."""
    AUTHORITATIVE_OR_INDEPENDENT = "authoritative_or_independent"
    """Authoritative resolution OR >=2 genuinely independent sources agreeing."""
    INDEPENDENT_REQUIRED = "independent_required"
    """Two or more genuinely independent (distinct known lineage) sources must
    agree; an authoritative single source is only PROVISIONAL."""


class BeliefAcceptance(str, Enum):
    """Whether a belief meets the governed support requirement."""

    ACCEPTED = "accepted"
    PROVISIONAL = "provisional"
    """Held with some support, but the requirement is not fully met (e.g. single
    source when independence is required, or independence unproven)."""
    UNMET = "unmet"
    """Conflicted or unknown — no acceptable support."""
    NOT_APPLICABLE = "not_applicable"
    """No support policy governs this belief."""


@dataclass(frozen=True)
class BeliefPolicyResult:
    acceptance: BeliefAcceptance
    requirement: Optional[SupportRequirement]
    reason: str
    policy_name: str = ""


@dataclass(frozen=True)
class BeliefSupportRule:
    """A support requirement for a match (by predicate). ``None`` matches all;
    first matching rule wins."""

    requirement: SupportRequirement
    predicate: Optional[str] = None


@dataclass(frozen=True)
class BeliefSupportPolicy:
    """Ordered support rules. Deterministic, versioned by ``name``. A belief
    matched by no rule is NOT_APPLICABLE (ungoverned — the 7.5 behavior)."""

    rules: tuple[BeliefSupportRule, ...] = ()
    name: str = "belief-support-policy"

    @classmethod
    def none(cls) -> "BeliefSupportPolicy":
        return cls(rules=(), name="no-support-policy")

    @property
    def governs(self) -> bool:
        return bool(self.rules)

    def evaluate(
        self,
        *,
        predicate: str,
        authority_status: AuthorityStatus,
        corroboration: CorroborationLevel,
        is_affirmed: bool,
    ) -> BeliefPolicyResult:
        """Deterministically decide acceptance from the (already computed)
        authority and corroboration verdicts. A model does not enter here."""
        rule = next((r for r in self.rules if r.predicate in (None, predicate)), None)
        if rule is None:
            return BeliefPolicyResult(
                acceptance=BeliefAcceptance.NOT_APPLICABLE, requirement=None,
                reason="no support policy governs this belief", policy_name=self.name)

        if not is_affirmed:
            return BeliefPolicyResult(
                acceptance=BeliefAcceptance.UNMET, requirement=rule.requirement,
                reason="belief is not affirmed (conflicted or unknown); support "
                       "requirement cannot be met", policy_name=self.name)

        authoritative = authority_status is AuthorityStatus.RESOLVED
        independent = corroboration is CorroborationLevel.INDEPENDENT

        req = rule.requirement
        if req is SupportRequirement.AUTHORITATIVE:
            ok = authoritative
        elif req is SupportRequirement.AUTHORITATIVE_OR_INDEPENDENT:
            ok = authoritative or independent
        else:  # INDEPENDENT_REQUIRED
            ok = independent

        if ok:
            return BeliefPolicyResult(
                acceptance=BeliefAcceptance.ACCEPTED, requirement=req,
                reason=f"requirement {req.value!r} met "
                       f"(authoritative={authoritative}, independent={independent})",
                policy_name=self.name)
        return BeliefPolicyResult(
            acceptance=BeliefAcceptance.PROVISIONAL, requirement=req,
            reason=f"requirement {req.value!r} not fully met "
                   f"(authoritative={authoritative}, independent={independent}); "
                   "held provisionally, not accepted",
            policy_name=self.name)
