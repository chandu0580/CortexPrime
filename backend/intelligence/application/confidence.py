"""Categorical confidence and the investigation assessment — Phase 11.3 (ADR-123).

The Intelligence Plane deliberately carries no numeric confidence on a
hypothesis (ADR-085: "a number here would be a confidence score in disguise").
This module does not add one. It answers the operator's questions — how sure,
on what, contradicted by what, and what is still unknown — with a CATEGORY
whose criteria are stated, computed from things the platform already decided:

* the differential's statuses (SUPPORTED / REFUTED / OPEN — set from observed
  values, never from a model),
* the LINEAGE of the observations that support the leading hypothesis (how
  many distinct KNOWN origins agree — an API server and a kubelet are two;
  ten log lines from one kubelet are one),
* the FRESHNESS of that evidence, and
* whether anything CONTRADICTS the leading hypothesis.

Evidence weighting (section 16 of the phase brief) is therefore categorical and
de-duplicated by origin: directness is the lineage relation, reliability is the
authority tier, recency is the freshness state, independence is the distinct
origin count, contradiction is the contradiction refs. Correlated evidence is
counted once. Nothing is multiplied.

The empirical reliability of each category is the Calibration Plane's business
(Phase 8.7): it can later say how often "high" was right. This module says only
what the evidence supports now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from backend.contracts.intelligence import InvestigationConclusion
from backend.contracts.world import HypothesisStatus

__all__ = [
    "ConfidenceLevel", "EvidenceWeight", "InvestigationAssessment", "assess",
    "OUTCOME_ROOT_CAUSE", "OUTCOME_LIKELY_CAUSE", "OUTCOME_INSUFFICIENT_EVIDENCE",
    "OUTCOME_CONFLICTED", "OUTCOME_BLOCKED",
]


class ConfidenceLevel:
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


OUTCOME_ROOT_CAUSE = "ROOT_CAUSE_IDENTIFIED"
OUTCOME_LIKELY_CAUSE = "LIKELY_CAUSE"
OUTCOME_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
OUTCOME_CONFLICTED = "CONFLICTED"
OUTCOME_BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class EvidenceWeight:
    """One observation's standing, categorically."""

    observation_ref: str
    subject_ref: str
    predicate: str
    source_ref: str
    origin: Optional[str]          # known lineage origin, or None
    directness: str                # lineage relation: direct/derived/mirrored/unknown
    freshness: str                 # fresh/stale/unknown
    role: str                      # supports/contradicts/context
    hypothesis_ref: Optional[str] = None
    counted: bool = True           # False when another item from the same origin already counts

    def to_dict(self) -> dict:
        return {
            "observation_ref": self.observation_ref, "subject_ref": self.subject_ref,
            "predicate": self.predicate, "source_ref": self.source_ref, "origin": self.origin,
            "directness": self.directness, "freshness": self.freshness, "role": self.role,
            "hypothesis_ref": self.hypothesis_ref, "counted": self.counted,
        }


@dataclass(frozen=True)
class InvestigationAssessment:
    investigation_ref: str
    incident_ref: str
    outcome: str
    confidence: str
    root_cause: Optional[str]
    root_cause_hypothesis: Optional[str]
    basis: tuple                         # human-readable criteria that produced the level
    independent_origins: tuple
    supporting_evidence: tuple
    contradicting_evidence: tuple
    eliminated: tuple                    # (hypothesis_ref, [evidence refs])
    alternatives_open: tuple             # hypothesis refs still open
    unknowns: tuple
    next_step: Optional[str]
    recommended_action_candidate: Optional[str]
    weights: tuple
    timeline: tuple
    window: Mapping[str, Any]
    assessed_at: datetime
    authority: str = "none"

    def to_dict(self) -> dict:
        return {
            "investigation_ref": self.investigation_ref, "incident_ref": self.incident_ref,
            "outcome": self.outcome, "confidence": self.confidence,
            "root_cause": self.root_cause, "root_cause_hypothesis": self.root_cause_hypothesis,
            "basis": list(self.basis), "independent_origins": list(self.independent_origins),
            "supporting_evidence": list(self.supporting_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
            "eliminated": [{"hypothesis_ref": h, "by": list(refs)} for h, refs in self.eliminated],
            "alternatives_open": list(self.alternatives_open), "unknowns": list(self.unknowns),
            "next_step": self.next_step,
            "recommended_action_candidate": self.recommended_action_candidate,
            "weights": [w.to_dict() for w in self.weights],
            "timeline": [dict(t) for t in self.timeline], "window": dict(self.window),
            "assessed_at": self.assessed_at.isoformat(), "authority": self.authority,
        }


#: Recommendation CANDIDATES per hypothesis. Advice with ``authority: none``;
#: Prompt 4 and the governance layer decide whether any becomes an action.
_RECOMMENDATIONS = {
    "h-deployment-regression": "roll the deployment back to the previous revision (requires approval)",
    "h-configuration": "correct the missing or invalid configuration/secret and roll out",
    "h-dependency-connectivity": "restore the dependency or its network path; then restart the workload",
    "h-resource-exhaustion": "raise the container memory limit or fix the leak; then roll out",
    "h-startup-failure": "inspect the application error at startup; fix and roll out",
    "h-probe-failure": "fix the readiness/liveness probe or the endpoint it checks",
    "h-image-pull-failure": "fix the image reference or registry credentials",
}

_CHANGE_REFS = frozenset({"h-deployment-regression"})

_NEXT_STEPS = {
    "h-configuration": "collect the container's log patterns from the run that died",
    "h-dependency-connectivity": "collect the container's log patterns for connectivity errors",
    "h-startup-failure": "collect the container's log patterns for a crash signature",
    "h-resource-exhaustion": "read the last termination and memory against the limit",
    "h-deployment-regression": "read the ReplicaSet lineage inside the change window",
    "h-probe-failure": "read the pod's events for probe failures",
    "h-image-pull-failure": "read the pod's waiting reason and events",
}


def _weights_for(investigation: Any, evidence_view: Mapping[str, Mapping[str, Any]],
                 lineage_of) -> tuple:
    """Every linked observation as a weight, with roles from the differential."""
    roles: dict = {}
    for hypothesis in investigation.differential:
        for ref in hypothesis.evidence_for:
            roles[ref] = ("supports", hypothesis.hypothesis_ref)
        for ref in hypothesis.evidence_against:
            roles.setdefault(ref, ("contradicts", hypothesis.hypothesis_ref))
    weights = []
    for ref in investigation.evidence_refs:
        view = evidence_view.get(ref)
        if view is None:
            continue
        role, hypothesis_ref = roles.get(ref, ("context", None))
        lineage = lineage_of(source_kind=str(view.get("source_kind") or "connector"),
                             source_ref=str(view.get("source_ref") or ""))
        weights.append(EvidenceWeight(
            observation_ref=ref, subject_ref=str(view.get("subject_ref") or ""),
            predicate=str(view.get("predicate") or ""), source_ref=str(view.get("source_ref") or ""),
            origin=getattr(lineage, "origin_id", None),
            directness=getattr(getattr(lineage, "relation", None), "value", "unknown"),
            freshness=str(view.get("freshness") or "unknown"), role=role,
            hypothesis_ref=hypothesis_ref))
    return tuple(weights)


def _dedupe_by_origin(weights: Sequence[EvidenceWeight]) -> tuple:
    """Correlated evidence counts once: the first weight per (origin, role,
    hypothesis) counts, later ones from the same origin do not."""
    seen: set = set()
    out = []
    for weight in weights:
        key = (weight.origin or f"unknown:{weight.source_ref}", weight.role, weight.hypothesis_ref)
        counted = key not in seen
        seen.add(key)
        out.append(EvidenceWeight(**{**weight.__dict__, "counted": counted}))
    return tuple(out)


def assess(*, investigation: Any, evidence_view: Mapping[str, Mapping[str, Any]],
           lineage_of, window: Optional[Mapping[str, Any]] = None,
           timeline: Sequence[Mapping[str, Any]] = (), now: Optional[datetime] = None,
           ) -> InvestigationAssessment:
    """Compute the assessment. Reads state; decides a CATEGORY by stated rules.

    Rules for the leading (single SUPPORTED) hypothesis:
      HIGH   — no contradiction, no open alternative, no unknown lineage, all
               supporting evidence fresh, AND either (a) supported by >= 2
               distinct known origins, or (b) supported by 1 known origin with
               every alternative eliminated and at least one elimination coming
               from a DIFFERENT known origin than the support (the case rests on
               independent instruments even though only one names the cause)
      MEDIUM — supported by >= 1 known origin with no contradiction, but with a
               stale item, an open alternative alongside >= 2 origins, or
               eliminations that all share the supporter's origin
      LOW    — supported by 1 origin with alternatives open, or with unknown
               lineage, or contradicted
    Otherwise (nothing supported, or several) the outcome is INSUFFICIENT_EVIDENCE
    or CONFLICTED with confidence NONE.
    """
    now = now or datetime.now(timezone.utc)
    weights = _dedupe_by_origin(_weights_for(investigation, evidence_view, lineage_of))
    supported = [h for h in investigation.differential if h.status is HypothesisStatus.SUPPORTED]
    refuted = [h for h in investigation.differential if h.status is HypothesisStatus.REFUTED]
    open_ = [h for h in investigation.differential if h.status is HypothesisStatus.OPEN]
    eliminated = tuple((h.hypothesis_ref, tuple(h.evidence_against)) for h in refuted)
    unknowns = tuple(f"{h.hypothesis_ref}: {'; '.join(h.missing_evidence) or 'untested'}" for h in open_)
    conclusion = investigation.conclusion
    basis: list = []
    root_cause = root_ref = None
    outcome = OUTCOME_INSUFFICIENT_EVIDENCE
    confidence = ConfidenceLevel.NONE
    supporting: tuple = ()
    contradicting: tuple = ()
    origins: tuple = ()

    if conclusion in (InvestigationConclusion.BLOCKED, InvestigationConclusion.FAILED):
        outcome = OUTCOME_BLOCKED
        basis.append(f"the investigation concluded {conclusion.value}: evidence could not be obtained")
    elif len(supported) >= 2 and conclusion is not InvestigationConclusion.RESOLVED:
        outcome = OUTCOME_CONFLICTED
        basis.append("two or more hypotheses are supported by observed evidence; "
                     "the evidence does not discriminate between them")
    elif supported:
        # One supported hypothesis, or several the engine resolved as a
        # declared-compatible COMPOSITE (a change plus the mechanism it
        # introduced). The lead is the mechanism; the change is named with it.
        change = [h for h in supported if h.hypothesis_ref in _CHANGE_REFS]
        mechanism = [h for h in supported if h.hypothesis_ref not in _CHANGE_REFS]
        lead = (mechanism or change)[0]
        composite = change if mechanism and change else []
        root_ref = lead.hypothesis_ref
        supported_refs = {h.hypothesis_ref for h in supported}
        lead_weights = [w for w in weights if w.role == "supports" and w.hypothesis_ref in supported_refs]
        known = sorted({w.origin for w in lead_weights if w.origin})
        unknown_lineage = [w for w in lead_weights if not w.origin]
        stale = [w for w in lead_weights if w.freshness != "fresh"]
        contradiction = [w for w in weights if w.role == "contradicts" and w.hypothesis_ref in supported_refs]
        contradiction += [w for w in weights if w.observation_ref in lead.contradiction_refs]
        origins = tuple(known)
        supporting = tuple(w.observation_ref for w in lead_weights)
        contradicting = tuple(dict.fromkeys(w.observation_ref for w in contradiction))
        elimination_origins = sorted({w.origin for w in weights
                                      if w.role == "contradicts" and w.hypothesis_ref not in supported_refs
                                      and w.origin})
        independent_elimination = any(o not in known for o in elimination_origins)
        basis.append(f"{lead.hypothesis_ref} is supported by {len(lead_weights)} observation(s) "
                     f"from {len(known)} distinct known origin(s): {known or 'none known'}")
        if refuted:
            basis.append(f"{len(refuted)} alternative(s) eliminated by evidence from origin(s) "
                         f"{elimination_origins or 'unknown'}"
                         + ("; at least one elimination is independent of the supporting origin"
                            if independent_elimination else ""))
        if unknown_lineage:
            basis.append(f"{len(unknown_lineage)} supporting observation(s) have unknown lineage")
        if stale:
            basis.append(f"{len(stale)} supporting observation(s) are not fresh")
        if contradiction:
            basis.append(f"{len(contradicting)} observation(s) contradict it")
        if open_:
            basis.append(f"alternatives still open: {[h.hypothesis_ref for h in open_]}")
        else:
            basis.append("every alternative was eliminated by observation")
        clean = not stale and not open_ and not unknown_lineage
        if contradiction:
            confidence = ConfidenceLevel.LOW
        elif clean and (len(known) >= 2 or (len(known) == 1 and refuted and independent_elimination)):
            confidence = ConfidenceLevel.HIGH
        elif len(known) >= 2 or (len(known) == 1 and not open_ and not unknown_lineage):
            confidence = ConfidenceLevel.MEDIUM
        else:
            confidence = ConfidenceLevel.LOW
        root_cause = lead.proposition
        if composite:
            root_cause = (f"{composite[0].proposition} -- specifically: {lead.proposition}")
            basis.append(f"composite explanation: {[h.hypothesis_ref for h in supported]} are supported "
                         "and declared compatible (a change and the mechanism it introduced)")
        outcome = OUTCOME_ROOT_CAUSE if confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM) \
            else OUTCOME_LIKELY_CAUSE
    else:
        basis.append("no hypothesis is supported by observed evidence")
        if refuted and not open_:
            basis.append("every seeded hypothesis was eliminated; the cause is outside the differential")

    next_step = None
    if outcome in (OUTCOME_INSUFFICIENT_EVIDENCE, OUTCOME_LIKELY_CAUSE, OUTCOME_CONFLICTED) and open_:
        first = open_[0]
        next_step = _NEXT_STEPS.get(first.hypothesis_ref, f"obtain evidence for {first.hypothesis_ref}")
    elif outcome == OUTCOME_BLOCKED:
        next_step = "restore the evidence source and re-run the investigation"
    elif outcome == OUTCOME_INSUFFICIENT_EVIDENCE and not open_:
        next_step = "widen the differential: the seeded explanations do not cover this failure"
    recommendation = _RECOMMENDATIONS.get(root_ref) if root_ref and outcome != OUTCOME_LIKELY_CAUSE else None

    return InvestigationAssessment(
        investigation_ref=investigation.investigation_ref, incident_ref=investigation.incident_ref,
        outcome=outcome, confidence=confidence, root_cause=root_cause, root_cause_hypothesis=root_ref,
        basis=tuple(basis), independent_origins=origins, supporting_evidence=supporting,
        contradicting_evidence=contradicting, eliminated=eliminated,
        alternatives_open=tuple(h.hypothesis_ref for h in open_), unknowns=unknowns,
        next_step=next_step, recommended_action_candidate=recommendation, weights=weights,
        timeline=tuple(timeline), window=dict(window or {}), assessed_at=now)
