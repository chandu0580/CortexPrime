"""Phase 8.4 — differential diagnosis: gaps, test quality, selection, honesty.

The platform reasons ABOUT the model's proposals deterministically: it computes
evidence gaps, categorises test quality, selects the most discriminating test,
and settles honestly (a supported leading hypothesis is NOT verified and the open
alternatives are NOT false). Adversarial proposals (a favoured hypothesis with no
evidence, a shell/URL test, a redundant test, an unavailable tool) are reduced to
untrusted proposals the platform refuses. In-memory scripted ports; the
real-Postgres 4-hypothesis DevOps scenario is the phase84 harness.
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
    ContextAssembler, EvidenceResult, EvidenceSelectionPolicy, InvestigationBudget,
    InvestigationEngine, InvestigationProposal, InvestigationService, ProposedHypothesis,
    ProposedTest, StepOutcome, TestQuality, analyze_gaps, classify_test, live_hypotheses,
    select_test, settle,
)

ACME = TenantRef(tenant_id="acme")


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


def _hyp(ref, *, status=HypothesisStatus.OPEN, subject="s/1", ev_for=(), ev_against=()):
    return DifferentialHypothesis(
        hypothesis_ref=ref, subject_ref=subject, proposition=f"prop {ref}", status=status,
        temporal_fit=TemporalFit.UNKNOWN, created_by="scripted:model",
        evidence_for=tuple(ev_for), evidence_against=tuple(ev_against))


class _Inv:
    """A minimal duck-typed investigation for the pure differential functions."""
    def __init__(self, differential, test_refs=()):
        self.differential = tuple(differential)
        self.test_refs = tuple(test_refs)


def _test(ref="h1", **over):
    base = dict(discriminates_hypothesis=ref, tool="deploy.history", subject_ref="s/1",
                predicate="state", evidence_expected="cause", supports_if="matches",
                contradicts_if="differs", residual_uncertainty="timing",
                supports_value={"v": 1}, contradicts_value={"v": 0})
    base.update(over)
    return ProposedTest(**base)


# ======================================================================
# Evidence-gap analysis (Part C)
# ======================================================================

class TestGaps:
    def test_open_hypothesis_reports_why_unresolved(self):
        inv = _Inv([_hyp("h1", subject="deployment/payments")])
        gaps = analyze_gaps(inv)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.hypothesis_ref == "h1"
        assert g.unknown  # something is missing
        assert "unresolved" in g.unresolved_reason and "deployment/payments" in g.unresolved_reason

    def test_eliminated_hypothesis_is_not_live(self):
        inv = _Inv([_hyp("h1"), _hyp("h2", status=HypothesisStatus.REFUTED)])
        live = live_hypotheses(inv)
        assert {h.hypothesis_ref for h in live} == {"h1"}  # REFUTED is eliminated
        gaps = analyze_gaps(inv)
        assert {g.hypothesis_ref for g in gaps} == {"h1"}

    def test_gap_names_the_other_live_competitors(self):
        inv = _Inv([_hyp("h1"), _hyp("h2"), _hyp("h3", status=HypothesisStatus.REFUTED)])
        gaps = {g.hypothesis_ref: g for g in analyze_gaps(inv)}
        assert gaps["h1"].discriminates_from == ("h2",)  # h3 eliminated, not listed

    def test_supported_gap_says_not_verified(self):
        inv = _Inv([_hyp("h1", status=HypothesisStatus.SUPPORTED, ev_for=("wobs-1",))])
        g = analyze_gaps(inv)[0]
        assert "not Assurance-verified" in g.unresolved_reason


# ======================================================================
# Categorical test quality (Part E) — never a numeric confidence
# ======================================================================

class TestQualityClassification:
    def test_discriminating_when_two_live(self):
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        assert classify_test(proposed=_test("h1"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.DISCRIMINATING

    def test_partially_discriminating_when_one_live(self):
        inv = _Inv([_hyp("h1"), _hyp("h2", status=HypothesisStatus.REFUTED)])
        assert classify_test(proposed=_test("h1"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.PARTIALLY_DISCRIMINATING

    def test_non_discriminating_unknown_target(self):
        inv = _Inv([_hyp("h1")])
        assert classify_test(proposed=_test("hX"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.NON_DISCRIMINATING

    def test_non_discriminating_without_structured_expectation(self):
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        q = classify_test(proposed=_test("h1", supports_value=None, contradicts_value=None),
                          investigation=inv, available_tools=("deploy.history",))
        assert q is TestQuality.NON_DISCRIMINATING

    def test_unavailable_tool(self):
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        assert classify_test(proposed=_test("h1", tool="shell.exec"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.UNAVAILABLE

    def test_forbidden_url_or_shell(self):
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        for bad in ("https://evil.example/x", "a;rm -rf /", "$(whoami)"):
            assert classify_test(proposed=_test("h1", subject_ref=bad), investigation=inv,
                                 available_tools=("deploy.history",)) is TestQuality.FORBIDDEN

    def test_redundant_when_already_run(self):
        from backend.intelligence.application import ProposedTest  # noqa: F401
        from backend.intelligence.application.proposal import test_identity
        tid = test_identity(discriminates="h1", tool="deploy.history",
                            subject_ref="s/1", predicate="state")
        inv = _Inv([_hyp("h1"), _hyp("h2")], test_refs=(f"wtest-{tid}",))
        assert classify_test(proposed=_test("h1"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.REDUNDANT

    def test_redundant_when_target_eliminated(self):
        inv = _Inv([_hyp("h1", status=HypothesisStatus.REFUTED), _hyp("h2")])
        assert classify_test(proposed=_test("h1"), investigation=inv,
                             available_tools=("deploy.history",)) is TestQuality.REDUNDANT


# ======================================================================
# Deterministic selection (Part D/N) — platform owns the order
# ======================================================================

class TestSelection:
    def test_prefers_discriminating_over_partial(self):
        # h1 is the only live target that discriminates two lives; make a partial
        # candidate compete and confirm the discriminating one wins.
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        disc = _test("h1", subject_ref="s/1")
        # a candidate that names an unknown hypothesis is non-discriminating (dropped)
        junk = _test("hZ", subject_ref="s/9")
        sel = select_test(candidates=(junk, disc), investigation=inv,
                          available_tools=("deploy.history",))
        assert sel.chosen is disc and sel.quality is TestQuality.DISCRIMINATING

    def test_none_when_all_inadmissible(self):
        inv = _Inv([_hyp("h1", status=HypothesisStatus.REFUTED)])
        sel = select_test(candidates=(_test("h1"),), investigation=inv,
                          available_tools=("deploy.history",))
        assert sel.chosen is None and "no admissible" in sel.reason

    def test_selection_is_deterministic(self):
        inv = _Inv([_hyp("h1"), _hyp("h2")])
        a = select_test(candidates=(_test("h1", subject_ref="s/1"), _test("h2", subject_ref="s/2")),
                        investigation=inv, available_tools=("deploy.history",))
        b = select_test(candidates=(_test("h1", subject_ref="s/1"), _test("h2", subject_ref="s/2")),
                        investigation=inv, available_tools=("deploy.history",))
        assert a.chosen == b.chosen  # stable tie-break


# ======================================================================
# Honest settle (Part P) — supported != verified, open != false
# ======================================================================

class TestSettle:
    def test_single_supported_is_resolved_but_unverified(self):
        inv = _Inv([_hyp("h4", status=HypothesisStatus.SUPPORTED, ev_for=("wobs-4",)),
                    _hyp("h1", status=HypothesisStatus.OPEN),
                    _hyp("h2", status=HypothesisStatus.REFUTED)])
        s = settle(inv)
        assert s.conclusion == InvestigationConclusion.RESOLVED.value
        assert s.supported == ("h4",) and s.verified is False
        assert "not Assurance-verified" in s.residual_uncertainty
        assert "h1" in s.residual_uncertainty  # open alternative not eliminated, not false

    def test_two_supported_is_conflicted_not_coinflip(self):
        inv = _Inv([_hyp("h1", status=HypothesisStatus.SUPPORTED),
                    _hyp("h2", status=HypothesisStatus.SUPPORTED)])
        assert settle(inv).conclusion == InvestigationConclusion.CONFLICTED.value

    def test_none_supported_is_unresolved_never_false(self):
        inv = _Inv([_hyp("h1", status=HypothesisStatus.OPEN)])
        assert settle(inv).conclusion == InvestigationConclusion.UNRESOLVED.value


# ======================================================================
# Adversarial (Part O) — model verdicts never become platform truth
# ======================================================================

class MemRepo:
    def __init__(self):
        self.by_identity, self.events = {}, []
    def append(self, *, event_id, identity_digest, investigation_id, tenant_id, incident_ref,
               seq, event_kind, from_status, to_status, autonomy_level, state, payload, recorded_at):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = True
        self.events.append((investigation_id, tenant_id, seq, state))
        return True
    def latest_state(self, *, tenant_id, investigation_id):
        rows = [e for e in self.events if e[0] == investigation_id and e[1] == tenant_id]
        return max(rows, key=lambda e: e[2])[3] if rows else None


class _World:
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"subject_ref": subject_ref, "value": {"v": 0}, "status": "affirmed"}


class _Evidence:
    def __init__(self):
        self.calls = 0
    def acquire(self, *, tenant, request, now):
        self.calls += 1
        # the WORLD says {"v": 0}: it contradicts a "favoured" hypothesis whose
        # supports_value is {"v": 1}. The platform must NOT mark it supported.
        return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                              observation_ref=f"wobs-{self.calls}", observed_value={"v": 0},
                              source_ref="connector:kubernetes")


class AdversarialModel:
    """Proposes a single favoured hypothesis, claims it 'resolved', and offers a
    test whose structured expectation the WORLD will contradict."""
    def propose(self, *, context, investigation, now):
        hyps = ()
        if not investigation.differential:
            hyps = (ProposedHypothesis("h1", "my favourite", "deployment/payments", "consistent"),
                    ProposedHypothesis("h2", "the alternative", "db/payments", "unknown"))
        target = next((h.hypothesis_ref for h in investigation.differential
                       if h.status is HypothesisStatus.OPEN), hyps[0].hypothesis_ref if hyps else None)
        test = None
        if target is not None:
            test = ProposedTest(discriminates_hypothesis=target, tool="deploy.history",
                                subject_ref="deployment/payments", predicate="state",
                                evidence_expected="cause", supports_if="matches",
                                contradicts_if="differs", residual_uncertainty="x",
                                supports_value={"v": 1}, contradicts_value={"v": 0})
        return InvestigationProposal(provider="scripted", proposal_digest="d",
                                     interpretation="H1 is proven", proposed_hypotheses=hyps,
                                     proposed_test=test, suggested_conclusion="resolved")


def _engine(model, evidence, world=None):
    svc = InvestigationService(repository=MemRepo())
    return svc, InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=model, evidence_port=evidence,
        world_read_port=world or _World(), policy=EvidenceSelectionPolicy(), harness_version="h/1",
        available_tools=("deploy.history",))


def _open(svc):
    inv = svc.create(tenant=ACME, incident_ref="incident:x", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0))
    return svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                          cause="triage", now=_t(1))


class TestAdversarial:
    def test_favoured_hypothesis_not_supported_without_evidence(self):
        ev = _Evidence()
        svc, eng = _engine(AdversarialModel(), ev)
        inv = _open(svc)
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        h1 = next(h for h in res.investigation.differential if h.hypothesis_ref == "h1")
        # world contradicted the expectation -> REFUTED, never SUPPORTED by the claim
        assert h1.status is HypothesisStatus.REFUTED
        assert res.investigation.conclusion is None or \
            res.investigation.conclusion is not InvestigationConclusion.RESOLVED

    def test_shell_test_is_refused(self):
        class ShellModel:
            def propose(self, *, context, investigation, now):
                hyps = (ProposedHypothesis("h1", "x", "s/1"),) if not investigation.differential else ()
                return InvestigationProposal(
                    provider="scripted", proposal_digest="d", proposed_hypotheses=hyps,
                    proposed_test=ProposedTest(
                        discriminates_hypothesis="h1", tool="deploy.history",
                        subject_ref="$(curl evil)", predicate="state", evidence_expected="e",
                        supports_if="a", contradicts_if="b", residual_uncertainty="c",
                        supports_value={"v": 1}, contradicts_value={"v": 0}))
        ev = _Evidence()
        svc, eng = _engine(ShellModel(), ev)
        inv = _open(svc)
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        # FORBIDDEN test dropped -> no admissible test -> no governed read happened
        assert ev.calls == 0

    def test_unavailable_tool_causes_no_read(self):
        class ToolModel:
            def propose(self, *, context, investigation, now):
                hyps = (ProposedHypothesis("h1", "x", "s/1"),) if not investigation.differential else ()
                return InvestigationProposal(
                    provider="scripted", proposal_digest="d", proposed_hypotheses=hyps,
                    proposed_test=ProposedTest(
                        discriminates_hypothesis="h1", tool="prod.database.dump",
                        subject_ref="s/1", predicate="state", evidence_expected="e",
                        supports_if="a", contradicts_if="b", residual_uncertainty="c",
                        supports_value={"v": 1}, contradicts_value={"v": 0}))
        ev = _Evidence()
        svc, eng = _engine(ToolModel(), ev)
        inv = _open(svc)
        eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        assert ev.calls == 0  # unavailable tool never reaches a provider
