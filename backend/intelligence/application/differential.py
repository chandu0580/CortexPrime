"""Differential-diagnosis intelligence — Phase 8.4.

The platform's deterministic reasoning ABOUT the model's proposals. Three things
the model does NOT get to decide:

  * **Evidence-gap analysis** (``analyze_gaps``) — for each live hypothesis, what
    is known, what is missing, and *why it remains unresolved*. Deterministic; it
    explains "H1 is unresolved because no discriminating observation of X exists",
    never "H1 is most likely".

  * **Categorical test quality** (``TestQuality`` + ``classify_test``) — a proposed
    test is DISCRIMINATING / PARTIALLY_DISCRIMINATING / NON_DISCRIMINATING /
    REDUNDANT / UNAVAILABLE / FORBIDDEN. These are engineering categories, NOT a
    truth confidence: a test never becomes more authoritative for scoring high.

  * **Deterministic next-test selection** (``select_test``) — the platform picks
    the most discriminating admissible candidate; ties break on a deterministic
    identity, never on model-verbalised preference. The platform owns the loop.

And the honest terminal (``settle``): a single supported hypothesis is the leading
explanation with its residual uncertainty named — it is NOT claimed FALSE for the
alternatives and NOT claimed verified (Assurance is a separate, later gate). No
numeric confidence appears anywhere here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts.world import HypothesisStatus
from backend.intelligence.application.proposal import ProposedTest, test_identity

__all__ = [
    "TestQuality",
    "EvidenceGap",
    "TestSelection",
    "DiagnosticSummary",
    "LIVE_STATUSES",
    "live_hypotheses",
    "analyze_gaps",
    "classify_test",
    "select_test",
    "settle",
]

#: A hypothesis still competing in the differential. REFUTED is eliminated — it no
#: longer competes, so a test that only touches it does not discriminate anything.
LIVE_STATUSES: frozenset = frozenset({
    HypothesisStatus.OPEN, HypothesisStatus.SUPPORTED, HypothesisStatus.UNRESOLVED})

#: URL / shell / injection fragments a reference must never contain (the same set
#: the EvidenceSelectionPolicy enforces — one definition of "unsafe reference").
_FORBIDDEN_FRAGMENTS = ("http://", "https://", "$(", "`", ";", "&&", "|", "../", "\n")


class TestQuality(str, Enum):
    """A deterministic, categorical judgement of a proposed test's discrimination
    value — an engineering property, never a truth confidence."""

    DISCRIMINATING = "discriminating"
    """Narrows a differential of two or more live hypotheses."""
    PARTIALLY_DISCRIMINATING = "partially_discriminating"
    """Advances the one remaining live hypothesis (confirm/deny, no competitor)."""
    NON_DISCRIMINATING = "non_discriminating"
    """Targets no live hypothesis, or carries no structured expectation."""
    REDUNDANT = "redundant"
    """Already run, or targets an eliminated hypothesis — wastes a read."""
    UNAVAILABLE = "unavailable"
    """Names a tool outside the exposed read-only allowlist."""
    FORBIDDEN = "forbidden"
    """Carries a URL / shell / injection fragment — never reaches a provider."""


_ADMISSIBLE = (TestQuality.DISCRIMINATING, TestQuality.PARTIALLY_DISCRIMINATING)


@dataclass(frozen=True)
class EvidenceGap:
    """What we know, what we do not, and why a hypothesis is still unresolved."""

    hypothesis_ref: str
    subject_ref: str
    status: str
    known: tuple[str, ...]
    unknown: tuple[str, ...]
    would_support: str
    would_contradict: str
    discriminates_from: tuple[str, ...]
    unresolved_reason: str

    def to_dict(self) -> dict:
        return {
            "hypothesis_ref": self.hypothesis_ref, "subject_ref": self.subject_ref,
            "status": self.status, "known": list(self.known), "unknown": list(self.unknown),
            "would_support": self.would_support, "would_contradict": self.would_contradict,
            "discriminates_from": list(self.discriminates_from),
            "unresolved_reason": self.unresolved_reason,
        }


@dataclass(frozen=True)
class TestSelection:
    """The platform's deterministic choice of the next test among candidates."""

    chosen: Optional[ProposedTest]
    quality: Optional[TestQuality]
    classifications: tuple[tuple[str, str], ...]   # (test_identity, quality.value)
    reason: str


@dataclass(frozen=True)
class DiagnosticSummary:
    """An honest terminal read of the differential. ``verified`` is always False in
    Phase 8.4 — Assurance verification is a separate, later gate (ADR-073)."""

    conclusion: str          # InvestigationConclusion value
    supported: tuple[str, ...]
    eliminated: tuple[str, ...]
    open_: tuple[str, ...]
    residual_uncertainty: str
    verified: bool = False

    def to_dict(self) -> dict:
        return {
            "conclusion": self.conclusion, "supported": list(self.supported),
            "eliminated": list(self.eliminated), "open": list(self.open_),
            "residual_uncertainty": self.residual_uncertainty, "verified": self.verified,
        }


def live_hypotheses(investigation) -> tuple:
    """The hypotheses still competing (OPEN/SUPPORTED/UNRESOLVED — never REFUTED)."""
    return tuple(h for h in investigation.differential if h.status in LIVE_STATUSES)


def analyze_gaps(investigation) -> tuple[EvidenceGap, ...]:
    """Deterministic per-hypothesis evidence-gap analysis (Part C). For each live
    hypothesis: what we know, what is missing, what would change our mind, which
    other live hypotheses this bears against, and *why it is still unresolved*."""
    live = live_hypotheses(investigation)
    live_refs = tuple(h.hypothesis_ref for h in live)
    gaps: list[EvidenceGap] = []
    for h in live:
        others = tuple(r for r in live_refs if r != h.hypothesis_ref)
        known = tuple(dict.fromkeys(h.evidence_for + h.evidence_against))
        unknown = h.missing_evidence or (() if known else (f"observation:{h.subject_ref}",))
        if h.status is HypothesisStatus.SUPPORTED:
            reason = (f"{h.hypothesis_ref} is supported by {list(h.evidence_for)}; "
                      f"not Assurance-verified")
        elif known:
            reason = (f"{h.hypothesis_ref} has evidence {list(known)} but remains "
                      f"unresolved — no observation has discriminated it")
        else:
            reason = (f"{h.hypothesis_ref} remains unresolved because no discriminating "
                      f"observation of {h.subject_ref} has been acquired yet")
        gaps.append(EvidenceGap(
            hypothesis_ref=h.hypothesis_ref, subject_ref=h.subject_ref, status=h.status.value,
            known=known, unknown=tuple(unknown),
            would_support=f"an observation of {h.subject_ref} consistent with '{h.proposition}'",
            would_contradict=f"an observation of {h.subject_ref} inconsistent with '{h.proposition}'",
            discriminates_from=others, unresolved_reason=reason))
    return tuple(gaps)


def classify_test(*, proposed: ProposedTest, investigation, available_tools) -> TestQuality:
    """Deterministically categorise a proposed test. Order matters: safety
    categories (FORBIDDEN/UNAVAILABLE) first, then structure, then discrimination.

    A test is DISCRIMINATING only when it targets a live hypothesis AND the
    differential still holds two or more live hypotheses (so resolving the target
    narrows the competition). With one live hypothesis it is PARTIALLY (confirm/
    deny only). This is the deterministic sense in which a test 'discriminates
    between competing hypotheses' — it is not a probability."""
    if not isinstance(proposed, ProposedTest):
        return TestQuality.NON_DISCRIMINATING
    # FORBIDDEN: any reference/tool carrying a URL/shell/injection fragment.
    for value in (proposed.subject_ref, proposed.predicate, proposed.tool):
        if not isinstance(value, str) or not value.strip():
            return TestQuality.FORBIDDEN
        if any(bad in value.lower() for bad in _FORBIDDEN_FRAGMENTS):
            return TestQuality.FORBIDDEN
    # UNAVAILABLE: tool outside the exposed read-only allowlist.
    if proposed.tool not in available_tools:
        return TestQuality.UNAVAILABLE
    known = {h.hypothesis_ref: h for h in investigation.differential}
    target = known.get(proposed.discriminates_hypothesis)
    # NON_DISCRIMINATING: unknown target, or no structured/falsifiable expectation.
    if target is None:
        return TestQuality.NON_DISCRIMINATING
    if proposed.supports_value is None and proposed.contradicts_value is None:
        return TestQuality.NON_DISCRIMINATING
    if not (proposed.supports_if.strip() and proposed.contradicts_if.strip()):
        return TestQuality.NON_DISCRIMINATING
    # REDUNDANT: identical test already run, or the target is already eliminated.
    tid = test_identity(discriminates=proposed.discriminates_hypothesis, tool=proposed.tool,
                        subject_ref=proposed.subject_ref, predicate=proposed.predicate)
    if any(tid in ref for ref in investigation.test_refs):
        return TestQuality.REDUNDANT
    if target.status is HypothesisStatus.REFUTED:
        return TestQuality.REDUNDANT
    if target.status not in LIVE_STATUSES:
        return TestQuality.NON_DISCRIMINATING
    # Discrimination power: two or more live hypotheses -> narrowing is possible.
    return (TestQuality.DISCRIMINATING if len(live_hypotheses(investigation)) >= 2
            else TestQuality.PARTIALLY_DISCRIMINATING)


def select_test(*, candidates, investigation, available_tools) -> TestSelection:
    """Deterministically select the next test (Part D/N). The platform prefers a
    DISCRIMINATING candidate over a PARTIALLY_DISCRIMINATING one, breaking ties on
    the deterministic test identity — never on model preference. NON_DISCRIMINATING
    / REDUNDANT / UNAVAILABLE / FORBIDDEN candidates are dropped."""
    classifications: list[tuple[str, str]] = []
    scored: list[tuple[int, str, ProposedTest]] = []
    for t in candidates:
        if not isinstance(t, ProposedTest):
            continue
        q = classify_test(proposed=t, investigation=investigation, available_tools=available_tools)
        tid = test_identity(discriminates=t.discriminates_hypothesis, tool=t.tool,
                            subject_ref=t.subject_ref, predicate=t.predicate)
        classifications.append((tid, q.value))
        if q in _ADMISSIBLE:
            scored.append((0 if q is TestQuality.DISCRIMINATING else 1, tid, t))
    if not scored:
        return TestSelection(None, None, tuple(classifications),
                             "no admissible discriminating test among the candidates")
    scored.sort(key=lambda s: (s[0], s[1]))
    rank, tid, chosen = scored[0]
    quality = TestQuality.DISCRIMINATING if rank == 0 else TestQuality.PARTIALLY_DISCRIMINATING
    return TestSelection(chosen, quality, tuple(classifications), f"selected {tid} ({quality.value})")


def settle(investigation) -> DiagnosticSummary:
    """The honest terminal read when no further discriminating test is available.

    RESOLVED means exactly one hypothesis is supported by admissible world evidence
    and no competitor is also supported — it does NOT claim the still-open
    alternatives are false, and it does NOT claim Assurance verified anything (both
    are carried as residual uncertainty; ``verified`` stays False). Competing
    support is CONFLICTED, not a coin-flip. Nothing here collapses UNKNOWN/OPEN
    into FALSE."""
    from backend.contracts.intelligence import InvestigationConclusion

    supported = tuple(h.hypothesis_ref for h in investigation.differential
                      if h.status is HypothesisStatus.SUPPORTED)
    eliminated = tuple(h.hypothesis_ref for h in investigation.differential
                       if h.status is HypothesisStatus.REFUTED)
    open_ = tuple(h.hypothesis_ref for h in investigation.differential
                  if h.status in (HypothesisStatus.OPEN, HypothesisStatus.UNRESOLVED))

    if len(supported) >= 2:
        conclusion = InvestigationConclusion.CONFLICTED
        residual = f"competing supported hypotheses {list(supported)}; unresolved by evidence"
    elif len(supported) == 1:
        conclusion = InvestigationConclusion.RESOLVED
        residual = f"leading hypothesis {supported[0]} supported by world evidence; not Assurance-verified"
        if open_:
            residual += f"; alternatives not eliminated: {list(open_)}"
    elif open_:
        conclusion = InvestigationConclusion.UNRESOLVED
        residual = f"no hypothesis affirmed; still open: {list(open_)}"
    elif investigation.differential:
        conclusion = InvestigationConclusion.UNRESOLVED
        residual = f"all hypotheses eliminated ({list(eliminated)}); none affirmed"
    else:
        conclusion = InvestigationConclusion.INSUFFICIENT_EVIDENCE
        residual = "no admissible evidence to adjudicate"
    return DiagnosticSummary(conclusion=conclusion.value, supported=supported,
                             eliminated=eliminated, open_=open_, residual_uncertainty=residual)
