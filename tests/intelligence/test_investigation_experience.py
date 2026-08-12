"""Phase 8.6 — investigation experience memory.

Experience is a projection over the durable ledgers, distinguishable from world
truth: an episode references authoritative objects but can never mint one; retrieval
is deterministic, explainable, tenant-scoped, and temporally safe; and historical
experience is never allowed to become current truth. In-memory ports; the
real-Postgres experience-assisted investigation + crash/replay is the phase86
harness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.world import HypothesisStatus, ProvenanceRef
from backend.contracts.intelligence import (
    AssuranceStatus, AutonomyLevel, DifferentialHypothesis, EpisodeFacets, ExperienceQuality,
    Investigation, InvestigationConclusion, InvestigationEpisode, InvestigationStatus,
    TemporalFit,
)
from backend.intelligence.application import (
    EpisodeProjection, InvestigationService, StructuredExperienceRetrieval, derive_facets,
)
from backend.world.application import ReasoningKind

ACME, OTHER = TenantRef(tenant_id="acme"), TenantRef(tenant_id="other")


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


def _hyp(ref, subject, prop, status):
    return DifferentialHypothesis(
        hypothesis_ref=ref, subject_ref=subject, proposition=prop, status=status,
        temporal_fit=TemporalFit.CONSISTENT, created_by="scripted:model")


def _terminal_inv(ref="winv-e123", incident="incident:production:payments-api:latency-spike",
                  conclusion=InvestigationConclusion.RESOLVED, verification_refs=(),
                  tenant=ACME, hyps=None):
    hyps = hyps or (
        _hyp("h4", "dependency/stripe", "external dependency degradation", HypothesisStatus.SUPPORTED),
        _hyp("h2", "database/payments", "database saturation", HypothesisStatus.REFUTED),
        _hyp("h1", "deployment/payments", "deployment regression", HypothesisStatus.OPEN),
    )
    return Investigation(
        investigation_ref=ref, tenant=tenant, incident_ref=incident,
        status=InvestigationStatus.COMPLETED, autonomy_level=AutonomyLevel.A1_INVESTIGATE,
        seq=9, created_at=_t(0), updated_at=_t(10),
        provenance=ProvenanceRef(produced_by="intelligence:engine/1"),
        policy_ref="pol/1", harness_version="h/1", differential=hyps,
        evidence_refs=("wobs-1",), test_refs=("wtest-1", "wtest-2"),
        verification_refs=verification_refs, conclusion=conclusion)


# ======================================================================
# The episode contract — experience references, never mints (Part C)
# ======================================================================

class TestEpisodeContract:
    def test_episode_has_no_truth_minting_methods(self):
        # the load-bearing invariant: experience cannot become truth.
        for method in ("to_fact", "to_belief", "to_outcome", "to_verification"):
            assert not hasattr(InvestigationEpisode, method)

    def test_episode_holds_references_not_world_objects(self):
        ep = EpisodeProjection().project(investigation=_terminal_inv())
        # every hypothesis is a reference summary (strings), not a live object
        assert all(isinstance(h.status, str) for h in ep.hypotheses)
        assert all(isinstance(r, str) for r in ep.evidence_refs)
        assert ep.to_dict()["episode_ref"] == "winv-e123"

    def test_quality_is_categorical_not_numeric(self):
        ep = EpisodeProjection().project(investigation=_terminal_inv())
        assert isinstance(ep.quality, ExperienceQuality)


# ======================================================================
# Projection (Part D/E) — terminal only, honest quality/assurance
# ======================================================================

class TestProjection:
    def test_non_terminal_is_not_reusable(self):
        inv = _terminal_inv()
        inv = Investigation.from_dict({**inv.to_dict(), "status": "investigating"})
        assert EpisodeProjection().project(investigation=inv) is None

    def test_resolved_without_verification_is_supported_not_assured(self):
        ep = EpisodeProjection().project(investigation=_terminal_inv())
        # RESOLVED with an open alternative (h1) -> PARTIALLY_SUPPORTED, UNASSURED
        assert ep.quality is ExperienceQuality.PARTIALLY_SUPPORTED
        assert ep.assurance_status is AssuranceStatus.UNASSURED

    def test_directly_assured_requires_supported_verdict(self):
        inv = _terminal_inv(verification_refs=("wverif-1",))
        ep = EpisodeProjection().project(
            investigation=inv, assurance_verdicts={"wverif-1": "supported"})
        assert ep.assurance_status is AssuranceStatus.ASSURED
        assert ep.quality is ExperienceQuality.DIRECTLY_ASSURED

    def test_verification_without_support_is_not_assured(self):
        inv = _terminal_inv(verification_refs=("wverif-1",))
        ep = EpisodeProjection().project(
            investigation=inv, assurance_verdicts={"wverif-1": "unsupported"})
        assert ep.assurance_status is AssuranceStatus.INSUFFICIENT_EVIDENCE
        assert ep.quality is not ExperienceQuality.DIRECTLY_ASSURED

    def test_conflicted_stays_conflicted_not_certain(self):
        inv = _terminal_inv(conclusion=InvestigationConclusion.CONFLICTED)
        ep = EpisodeProjection().project(investigation=inv)
        assert ep.quality is ExperienceQuality.CONFLICTED
        assert ep.assurance_status is AssuranceStatus.CONFLICTED


class TestFacets:
    def test_derives_service_environment_symptom(self):
        f = derive_facets(_terminal_inv())
        assert f.service == "payments-api" and f.environment == "production"
        assert f.symptom_class == "latency-spike"
        assert "dependency" in f.resource_types and "database" in f.resource_types

    def test_deterministic(self):
        assert derive_facets(_terminal_inv()).to_dict() == derive_facets(_terminal_inv()).to_dict()


# ======================================================================
# Retrieval (Part F/G/J/K) — explainable, tenant-scoped, temporally safe
# ======================================================================

class _Source:
    """A tenant-scoped episode source stub (composition backs it with tenant-scoped
    SQL). ``list_terminal`` returns only the given tenant's states."""
    def __init__(self, by_tenant):
        self._by = by_tenant
    def list_terminal(self, *, tenant_id, limit=200):
        return tuple(self._by.get(tenant_id, ()))


def _retrieval(states_by_tenant, verdicts=None):
    return StructuredExperienceRetrieval(
        source=_Source(states_by_tenant),
        verdicts_for=(lambda t, refs: verdicts) if verdicts else None)


class TestRetrieval:
    def test_relevant_episode_found_with_reasons(self):
        past = _terminal_inv(ref="winv-e123").to_dict()
        ret = _retrieval({"acme": (past,)})
        current = _terminal_inv(ref="winv-e456")
        matches = ret.find_relevant_episodes(tenant=ACME, facets=derive_facets(current),
                                             now=_t(20), exclude_ref="winv-e456")
        assert len(matches) == 1
        m = matches[0]
        assert m.episode_ref == "winv-e123"
        assert any("service=payments-api" in r for r in m.match_reasons)
        assert any("symptom=latency-spike" in r for r in m.match_reasons)
        # it returns HISTORICAL evidence, never "the current answer"
        assert m.to_context_dict()["kind"] == "HISTORICAL_INVESTIGATION_EXPERIENCE"
        assert "not current world truth" in m.to_context_dict()["caveat"]

    def test_no_similarity_score_returned(self):
        past = _terminal_inv(ref="winv-e123").to_dict()
        ret = _retrieval({"acme": (past,)})
        m = ret.find_relevant_episodes(tenant=ACME, facets=derive_facets(_terminal_inv("x")),
                                       now=_t(20), exclude_ref="x")[0]
        d = m.to_context_dict()
        assert not any("similarity" in k or "score" in k for k in d)

    def test_irrelevant_service_not_returned(self):
        past = _terminal_inv(ref="winv-e123",
                             incident="incident:production:billing-api:disk-full").to_dict()
        ret = _retrieval({"acme": (past,)})
        current = _terminal_inv(ref="winv-e456")  # payments-api / latency
        matches = ret.find_relevant_episodes(tenant=ACME, facets=derive_facets(current),
                                             now=_t(20), exclude_ref="winv-e456")
        assert matches == ()

    def test_tenant_isolation(self):
        past = _terminal_inv(ref="winv-e123", tenant=OTHER).to_dict()
        ret = _retrieval({"other": (past,)})  # only OTHER has episodes
        matches = ret.find_relevant_episodes(tenant=ACME, facets=derive_facets(_terminal_inv("x")),
                                             now=_t(20), exclude_ref="x")
        assert matches == ()  # ACME sees nothing of OTHER's experience

    def test_temporal_safety_future_episode_excluded(self):
        # an episode that completed at 10:10 must not be visible to an as-known cut
        # of 10:05 (future knowledge, Part K).
        past = _terminal_inv(ref="winv-e123").to_dict()  # completed_at = _t(10)
        ret = _retrieval({"acme": (past,)})
        current = derive_facets(_terminal_inv("x"))
        assert ret.find_relevant_episodes(tenant=ACME, facets=current, now=_t(20),
                                          exclude_ref="x", as_known_at=_t(5)) == ()
        assert ret.find_relevant_episodes(tenant=ACME, facets=current, now=_t(20),
                                          exclude_ref="x", as_known_at=_t(15)) != ()


# ======================================================================
# Temporal safety of the investigation ledger (Part K / U#8)
# ======================================================================

class MemRepoTemporal:
    def __init__(self):
        self.events = []  # (inv, tenant, seq, state, recorded_at)
    def append(self, *, event_id, identity_digest, investigation_id, tenant_id, incident_ref,
               seq, event_kind, from_status, to_status, autonomy_level, state, payload, recorded_at):
        if any(e[0] == investigation_id and e[1] == tenant_id and e[2] == seq for e in self.events):
            return False
        self.events.append((investigation_id, tenant_id, seq, state, recorded_at))
        return True
    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events if e[0] == investigation_id and e[1] == tenant_id]
        return max(rows, key=lambda e: e[2])[3] if rows else None
    def latest_state_as_known(self, *, tenant_id, investigation_id, known_at):
        rows = [e for e in self.events if e[0] == investigation_id and e[1] == tenant_id
                and e[4] <= known_at]
        return max(rows, key=lambda e: e[2])[3] if rows else None


class TestTemporalReconstruction:
    def test_evidence_learned_after_t2_absent_in_as_known_view(self):
        svc = InvestigationService(repository=MemRepoTemporal())
        inv = svc.create(tenant=ACME, incident_ref="incident:x", policy_ref="pol/1",
                         harness_version="h/1", now=_t(0))
        inv = svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                             cause="triage", now=_t(1))
        inv = svc.link_evidence(investigation=inv, evidence_refs=("wobs-early",), now=_t(10))
        # evidence learned LATER (10:15)
        svc.link_evidence(investigation=inv, evidence_refs=("wobs-late",), now=_t(15))
        as_known = svc.reconstruct_as_known(tenant=ACME, investigation_ref=inv.investigation_ref,
                                            known_at=_t(12))
        assert "wobs-early" in as_known.evidence_refs
        assert "wobs-late" not in as_known.evidence_refs  # future knowledge excluded


# ======================================================================
# Adversarial contamination (Part U)
# ======================================================================

class TestContamination:
    def test_historical_supported_is_not_current_fact(self):
        # E123 supported H4, but the episode exposes only a status STRING + refs;
        # there is no way to turn it into a Fact/Belief/Outcome/Verification.
        ep = EpisodeProjection().project(investigation=_terminal_inv())
        h4 = next(h for h in ep.hypotheses if h.hypothesis_ref == "h4")
        assert h4.status == "supported"
        assert not hasattr(ep, "to_fact") and not hasattr(h4, "to_fact")

    def test_episode_is_immutable(self):
        ep = EpisodeProjection().project(investigation=_terminal_inv())
        with pytest.raises(Exception):
            ep.residual_uncertainty = "rewritten"  # frozen dataclass

    def test_experience_use_kind_exists_for_calibration(self):
        assert ReasoningKind.EXPERIENCE_USE.value == "experience_use"
