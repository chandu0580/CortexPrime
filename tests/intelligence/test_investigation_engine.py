"""Phase 8.2 — the investigation engine (context, proposals, policy, loop).

Deterministic context assembly; the model proposes only; the platform validates
tests and updates the differential from OBSERVED world values; budgets bound the
loop; termination is evidence-based. In-memory scripted ports; the real-Postgres
vertical slice + crash/resume is the phase82 harness.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.contracts.tenant import TenantRef
from backend.contracts.world import HypothesisStatus
from backend.contracts.intelligence import (
    DifferentialHypothesis, InvestigationConclusion, InvestigationStatus, TemporalFit,
)
from backend.intelligence.application import (
    ContextAssembler, ContextBudget, EvidenceRequest, EvidenceResult,
    EvidenceSelectionPolicy, InvestigationBudget, InvestigationEngine,
    InvestigationProposal, InvestigationService, ProposedHypothesis, ProposedTest,
    StepOutcome, TestRejected,
)

ACME = TenantRef(tenant_id="acme")
CAUSE = {"cause": "rollout"}


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


class MemRepo:
    def __init__(self):
        self.by_identity, self.events = {}, []

    def append(self, *, event_id, identity_digest, investigation_id, tenant_id,
               incident_ref, seq, event_kind, from_status, to_status,
               autonomy_level, state, payload, recorded_at):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = True
        self.events.append((investigation_id, tenant_id, seq, state))
        return True

    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events if e[0] == investigation_id and e[1] == tenant_id]
        return max(rows, key=lambda e: e[2])[3] if rows else None


class ScriptedModel:
    """Deterministic scripted provider: proposes the 3-hypothesis differential on
    the first step, then a discriminating test for the first OPEN hypothesis. It
    honestly labels provider='scripted' and suggests a conclusion it has no
    authority to set."""

    def propose(self, *, context, investigation, now):
        hyps = ()
        if not investigation.differential:
            hyps = (
                ProposedHypothesis("h1", "rollout regression", "deployment/payments", "consistent"),
                ProposedHypothesis("h2", "db saturation", "deployment/payments", "unknown"),
                ProposedHypothesis("h3", "network degradation", "deployment/payments", "unknown"),
            )
        # test the first OPEN hypothesis (existing, or one being proposed this step);
        # H1 is supported by the world, the others are refuted.
        target_ref = next((h.hypothesis_ref for h in investigation.differential
                           if h.status is HypothesisStatus.OPEN),
                          hyps[0].hypothesis_ref if hyps else None)
        test = None
        if target_ref is not None:
            supports = CAUSE if target_ref == "h1" else {"cause": "other"}
            contradicts = {"cause": "other"} if target_ref == "h1" else CAUSE
            test = ProposedTest(
                discriminates_hypothesis=target_ref, tool="deploy.history",
                subject_ref="deployment/payments", predicate="state",
                evidence_expected="what caused the incident", supports_if="cause matches",
                contradicts_if="cause differs", residual_uncertainty="timing precision",
                supports_value=supports, contradicts_value=contradicts)
        return InvestigationProposal(
            provider="scripted", proposal_digest="d", interpretation="testing differential",
            proposed_hypotheses=hyps, proposed_test=test, suggested_conclusion="resolved")


class ScriptedWorldRead:
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"subject_ref": subject_ref, "predicate": predicate, "value": CAUSE,
                "status": "affirmed", "source": "connector:kubernetes", "freshness": "fresh"}


class ScriptedEvidence:
    def __init__(self):
        self.calls = 0

    def acquire(self, *, tenant, request, now):
        self.calls += 1
        assert request.read_only  # governed READ only
        return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                              observation_ref=f"wobs-{self.calls}", fact_ref=f"wfact-{self.calls}",
                              observed_value=CAUSE, source_ref="connector:kubernetes")


def _engine(evidence=None):
    svc = InvestigationService(repository=MemRepo())
    return svc, InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=ScriptedModel(),
        evidence_port=evidence or ScriptedEvidence(), world_read_port=ScriptedWorldRead(),
        policy=EvidenceSelectionPolicy(), harness_version="h/1",
        available_tools=("deploy.history", "metrics.window"))


def _open_inv(svc):
    inv = svc.create(tenant=ACME, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0))
    return svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                          cause="triage", now=_t(1))


# ======================================================================
# Context assembly — deterministic + versioned
# ======================================================================

class TestContext:
    def test_same_inputs_same_digest(self):
        svc = InvestigationService(repository=MemRepo())
        inv = _open_inv(svc)
        a = ContextAssembler()
        c1 = a.assemble(investigation=inv, world_evidence=({"x": 1},), available_tools=("t",),
                        harness_version="h/1", now=_t(2))
        c2 = a.assemble(investigation=inv, world_evidence=({"x": 1},), available_tools=("t",),
                        harness_version="h/1", now=_t(2))
        assert c1.context_digest == c2.context_digest

    def test_different_evidence_changes_digest(self):
        svc = InvestigationService(repository=MemRepo())
        inv = _open_inv(svc)
        a = ContextAssembler()
        c1 = a.assemble(investigation=inv, world_evidence=({"x": 1},), available_tools=("t",),
                        harness_version="h/1", now=_t(2))
        c2 = a.assemble(investigation=inv, world_evidence=({"x": 2},), available_tools=("t",),
                        harness_version="h/1", now=_t(2))
        assert c1.context_digest != c2.context_digest

    def test_sections_have_provenance_and_budget(self):
        svc = InvestigationService(repository=MemRepo())
        inv = _open_inv(svc)
        c = ContextAssembler().assemble(investigation=inv, world_evidence=(), available_tools=("t",),
                                        harness_version="h/1", now=_t(2))
        assert all(s.provenance and s.inclusion_reason and s.digest for s in c.sections)
        assert c.total_tokens >= 0

    def test_budget_drops_lowest_priority(self):
        svc = InvestigationService(repository=MemRepo())
        inv = _open_inv(svc)
        big = tuple({"k": "x" * 500} for _ in range(30))
        c = ContextAssembler().assemble(investigation=inv, world_evidence=big, available_tools=("t",),
                                        harness_version="h/1", now=_t(2),
                                        budget=ContextBudget(max_context_tokens=200))
        # some sections excluded with a reason; high-priority incident stays
        assert any(not s.included and s.exclusion_reason for s in c.sections)
        assert next(s for s in c.sections if s.section_type == "incident").included


# ======================================================================
# Evidence selection policy — falsifiable / discriminating / read-only
# ======================================================================

class TestEvidencePolicy:
    def _inv_with_h1(self, svc):
        inv = _open_inv(svc)
        return svc.upsert_hypothesis(investigation=inv, now=_t(2), hypothesis=DifferentialHypothesis(
            hypothesis_ref="h1", subject_ref="deployment/payments", proposition="rollout",
            status=HypothesisStatus.OPEN, temporal_fit=TemporalFit.UNKNOWN, created_by="model"))

    def _test(self, **over):
        base = dict(discriminates_hypothesis="h1", tool="deploy.history",
                    subject_ref="deployment/payments", predicate="state",
                    evidence_expected="cause", supports_if="matches", contradicts_if="differs",
                    residual_uncertainty="timing", supports_value={"cause": "rollout"})
        base.update(over)
        return ProposedTest(**base)

    def test_valid_test_passes(self):
        svc = InvestigationService(repository=MemRepo())
        inv = self._inv_with_h1(svc)
        v = EvidenceSelectionPolicy().validate(investigation=inv, proposed=self._test(),
                                               available_tools=("deploy.history",))
        assert v.request.read_only and v.tool == "deploy.history"

    def test_unknown_hypothesis_refused(self):
        svc = InvestigationService(repository=MemRepo())
        inv = self._inv_with_h1(svc)
        with pytest.raises(TestRejected):
            EvidenceSelectionPolicy().validate(investigation=inv,
                                               proposed=self._test(discriminates_hypothesis="hX"),
                                               available_tools=("deploy.history",))

    def test_undeclared_tool_refused(self):
        svc = InvestigationService(repository=MemRepo())
        inv = self._inv_with_h1(svc)
        with pytest.raises(TestRejected):
            EvidenceSelectionPolicy().validate(investigation=inv, proposed=self._test(tool="shell.exec"),
                                               available_tools=("deploy.history",))

    def test_url_or_shell_reference_refused(self):
        svc = InvestigationService(repository=MemRepo())
        inv = self._inv_with_h1(svc)
        with pytest.raises(TestRejected):
            EvidenceSelectionPolicy().validate(
                investigation=inv, proposed=self._test(subject_ref="https://evil.example/x"),
                available_tools=("deploy.history",))

    def test_non_falsifiable_refused(self):
        svc = InvestigationService(repository=MemRepo())
        inv = self._inv_with_h1(svc)
        with pytest.raises(TestRejected):
            EvidenceSelectionPolicy().validate(
                investigation=inv, proposed=self._test(supports_value=None, contradicts_value=None),
                available_tools=("deploy.history",))


# ======================================================================
# The loop — platform controlled, differential, termination, budgets
# ======================================================================

class TestLoop:
    def test_step_records_hypotheses_and_runs_a_test(self):
        svc, eng = _engine()
        inv = _open_inv(svc)
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        assert res.provider == "scripted"
        assert len(res.investigation.differential) == 3
        assert res.investigation.reads_taken == 1  # one governed read
        assert res.outcome in (StepOutcome.ADVANCED, StepOutcome.TERMINATED)

    def test_full_loop_resolves(self):
        svc, eng = _engine()
        inv = _open_inv(svc)
        final = eng.run(investigation=inv, budget=InvestigationBudget(), clock=lambda i: _t(2 + i))
        assert final.status is InvestigationStatus.COMPLETED
        assert final.conclusion is InvestigationConclusion.RESOLVED
        supported = [h for h in final.differential if h.status is HypothesisStatus.SUPPORTED]
        assert [h.hypothesis_ref for h in supported] == ["h1"]

    def test_model_suggestion_has_no_authority(self):
        # the scripted proposal suggests conclusion 'resolved' every step, but the
        # investigation is NOT concluded until the platform's evidence rule fires
        svc, eng = _engine()
        inv = _open_inv(svc)
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        # after step 1 only h1 supported, h2/h3 still OPEN -> not concluded
        assert res.investigation.conclusion is None
        assert res.investigation.status is InvestigationStatus.INVESTIGATING

    def test_step_budget_terminates(self):
        svc, eng = _engine()
        inv = _open_inv(svc)
        final = eng.run(investigation=inv, budget=InvestigationBudget(max_steps=1),
                        clock=lambda i: _t(2 + i))
        assert final.is_terminal  # budget forced a deterministic terminal state
        assert final.conclusion is not None

    def test_read_budget_terminates_insufficient(self):
        svc, eng = _engine()
        inv = _open_inv(svc)
        final = eng.run(investigation=inv, budget=InvestigationBudget(max_reads=0),
                        clock=lambda i: _t(2 + i))
        assert final.conclusion is InvestigationConclusion.INSUFFICIENT_EVIDENCE

    def test_blocked_evidence_terminates_blocked(self):
        class Blocked:
            def acquire(self, *, tenant, request, now):
                return EvidenceResult(ok=False, subject_ref=request.subject_ref,
                                      predicate=request.predicate, reason="connector unavailable")
        svc, eng = _engine(evidence=Blocked())
        inv = _open_inv(svc)
        final = eng.run(investigation=inv, budget=InvestigationBudget(), clock=lambda i: _t(2 + i))
        assert final.conclusion is InvestigationConclusion.BLOCKED
        assert final.status is InvestigationStatus.FAILED
