"""Phase 11.3 (ADR-123): categorical confidence is computed from the
differential and evidence lineage by stated rules; correlated evidence counts
once; nothing here is a probability."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.contracts.intelligence import InvestigationConclusion
from backend.contracts.world import HypothesisStatus
from backend.intelligence.application.confidence import (
    OUTCOME_BLOCKED, OUTCOME_CONFLICTED, OUTCOME_INSUFFICIENT_EVIDENCE, OUTCOME_LIKELY_CAUSE,
    OUTCOME_ROOT_CAUSE, assess,
)
from backend.world.application.lineage import LineageRelation, SourceLineage

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORIGINS = {"connector:kubernetes": "kubernetes-cluster", "kubelet:container-logs": "kubelet",
           "prometheus:kubelet-cadvisor": "kubelet", "prometheus:kube-state-metrics": "kubernetes-cluster"}


def lineage_of(*, source_kind, source_ref):
    origin = ORIGINS.get(source_ref)
    return SourceLineage(source_kind=source_kind, source_ref=source_ref, origin_id=origin,
                         relation=LineageRelation.DIRECT if origin else LineageRelation.UNKNOWN)


def _h(ref, status, for_=(), against=(), missing=("gap",)):
    return SimpleNamespace(hypothesis_ref=ref, proposition=f"proposition of {ref}", status=status,
                           evidence_for=tuple(for_), evidence_against=tuple(against),
                           missing_evidence=tuple(missing), contradiction_refs=())


def _inv(hypotheses, evidence, conclusion=InvestigationConclusion.RESOLVED):
    return SimpleNamespace(investigation_ref="winv-1", incident_ref="kubernetes:pod:prod/api-1",
                           differential=tuple(hypotheses), evidence_refs=tuple(evidence), conclusion=conclusion)


def _view(**items):
    return {ref: {"source_kind": "connector", "source_ref": src, "subject_ref": "s", "predicate": p,
                  "freshness": fresh}
            for ref, (src, p, fresh) in items.items()}


class TestLevels:
    def test_two_independent_fresh_origins_and_no_alternative_is_high(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.SUPPORTED, for_=("wobs-1", "wobs-2")),
                    _h("h-resource-exhaustion", HypothesisStatus.REFUTED, against=("wobs-3",))],
                   ["wobs-1", "wobs-2", "wobs-3"])
        view = _view(**{"wobs-1": ("kubelet:container-logs", "log_patterns", "fresh"),
                        "wobs-2": ("connector:kubernetes", "last_termination", "fresh"),
                        "wobs-3": ("connector:kubernetes", "last_termination", "fresh")})
        result = assess(investigation=inv, evidence_view=view, lineage_of=lineage_of, now=NOW)
        assert result.outcome == OUTCOME_ROOT_CAUSE and result.confidence == "high"
        assert set(result.independent_origins) == {"kubelet", "kubernetes-cluster"}
        assert result.recommended_action_candidate and result.to_dict()["authority"] == "none"
        assert result.eliminated == (("h-resource-exhaustion", ("wobs-3",)),)

    def test_correlated_evidence_counts_once(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.SUPPORTED, for_=("wobs-1", "wobs-2"))], ["wobs-1", "wobs-2"])
        view = _view(**{"wobs-1": ("kubelet:container-logs", "log_patterns", "fresh"),
                        "wobs-2": ("prometheus:kubelet-cadvisor", "memory_pressure", "fresh")})
        result = assess(investigation=inv, evidence_view=view, lineage_of=lineage_of, now=NOW)
        assert result.independent_origins == ("kubelet",)
        counted = [w for w in result.weights if w.counted and w.role == "supports"]
        assert len(counted) == 1
        assert result.confidence == "medium"   # one origin, no alternative open

    def test_open_alternatives_or_stale_evidence_lower_the_level(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.SUPPORTED, for_=("wobs-1",)),
                    _h("h-dependency-connectivity", HypothesisStatus.OPEN)], ["wobs-1"])
        view = _view(**{"wobs-1": ("kubelet:container-logs", "log_patterns", "fresh")})
        result = assess(investigation=inv, evidence_view=view, lineage_of=lineage_of, now=NOW)
        assert result.confidence == "low" and result.outcome == OUTCOME_LIKELY_CAUSE
        assert result.alternatives_open == ("h-dependency-connectivity",)
        assert result.next_step and result.recommended_action_candidate is None

    def test_a_contradiction_is_never_hidden(self):
        inv = _inv([_h("h-deployment-regression", HypothesisStatus.SUPPORTED, for_=("wobs-1", "wobs-2"),
                       against=("wobs-3",))], ["wobs-1", "wobs-2", "wobs-3"])
        view = _view(**{"wobs-1": ("connector:kubernetes", "rollout_history", "fresh"),
                        "wobs-2": ("kubelet:container-logs", "log_patterns", "fresh"),
                        "wobs-3": ("connector:kubernetes", "events", "fresh")})
        result = assess(investigation=inv, evidence_view=view, lineage_of=lineage_of, now=NOW)
        assert result.contradicting_evidence == ("wobs-3",) and result.confidence == "low"

    def test_unknown_lineage_cannot_be_high(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.SUPPORTED, for_=("wobs-1", "wobs-2"))], ["wobs-1", "wobs-2"])
        view = _view(**{"wobs-1": ("mystery:instrument", "x", "fresh"),
                        "wobs-2": ("connector:kubernetes", "last_termination", "fresh")})
        result = assess(investigation=inv, evidence_view=view, lineage_of=lineage_of, now=NOW)
        assert result.confidence in ("medium", "low") and "unknown lineage" in " ".join(result.basis)


class TestHonestOutcomes:
    def test_nothing_supported_is_insufficient_evidence_with_a_next_step(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.OPEN), _h("h-startup-failure", HypothesisStatus.OPEN)],
                   [], conclusion=InvestigationConclusion.UNRESOLVED)
        result = assess(investigation=inv, evidence_view={}, lineage_of=lineage_of, now=NOW)
        assert result.outcome == OUTCOME_INSUFFICIENT_EVIDENCE and result.confidence == "none"
        assert result.root_cause is None and result.next_step
        assert len(result.unknowns) == 2

    def test_everything_eliminated_says_the_cause_is_outside_the_differential(self):
        inv = _inv([_h("h-configuration", HypothesisStatus.REFUTED, against=("wobs-1",))], ["wobs-1"],
                   conclusion=InvestigationConclusion.UNRESOLVED)
        result = assess(investigation=inv, evidence_view=_view(**{"wobs-1": ("kubelet:container-logs", "log_patterns", "fresh")}),
                        lineage_of=lineage_of, now=NOW)
        assert result.outcome == OUTCOME_INSUFFICIENT_EVIDENCE
        assert "outside the differential" in " ".join(result.basis) and "widen" in result.next_step

    def test_two_supported_is_conflicted(self):
        inv = _inv([_h("h-a", HypothesisStatus.SUPPORTED, for_=("wobs-1",)), _h("h-b", HypothesisStatus.SUPPORTED, for_=("wobs-2",))],
                   ["wobs-1", "wobs-2"], conclusion=InvestigationConclusion.CONFLICTED)
        result = assess(investigation=inv, evidence_view={}, lineage_of=lineage_of, now=NOW)
        assert result.outcome == OUTCOME_CONFLICTED and result.confidence == "none"

    def test_blocked_is_blocked(self):
        inv = _inv([_h("h-a", HypothesisStatus.OPEN)], [], conclusion=InvestigationConclusion.BLOCKED)
        result = assess(investigation=inv, evidence_view={}, lineage_of=lineage_of, now=NOW)
        assert result.outcome == OUTCOME_BLOCKED and "re-run" in result.next_step
