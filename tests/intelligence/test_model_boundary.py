"""Phase 8.3 — the live governed model boundary + the model-output firewall.

The model proposes through harness.GovernedModelBoundary with a strict schema;
malformed/smuggled output fails closed; provider/model come from the platform;
model/trace/provider failures are classified (never success). In-memory trace
recorder; the durable trace + end-to-end slice is the phase83 harness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.contracts.tenant import TenantRef
from backend.contracts.world import HypothesisStatus
from backend.contracts.intelligence import InvestigationConclusion, InvestigationStatus
from backend.harness.llm_boundary import GovernedModelBoundary, TraceEvidenceMissing
from backend.harness.trace import InMemoryTraceRecorder
from backend.harness.version import CURRENT_HARNESS_VERSION
from backend.intelligence.application import (
    ContextAssembler, EvidenceResult, EvidenceSelectionPolicy, GovernedModelProposalPort,
    InvestigationBudget, InvestigationEngine, InvestigationProposalSchema,
    InvestigationService, ModelSchemaRejected, ScriptedModelPort, StepOutcome,
)

ACME = TenantRef(tenant_id="acme")
CAUSE = {"cause": "rollout"}
SUBJECT, PREDICATE = "deployment/payments", "state"


def _t(m):
    return datetime(2026, 8, 12, 10, m, tzinfo=timezone.utc)


# ======================================================================
# The model-output firewall (Part C/E/M)
# ======================================================================

class TestSchemaFirewall:
    @pytest.mark.parametrize("payload", [
        {"interpretation": "x", "success": True},          # completion claim
        {"interpretation": "x", "verified": True},         # verification claim
        {"interpretation": "x", "autonomy": "A4"},         # autonomy promotion
        {"interpretation": "x", "status": "completed"},    # status mutation
        {"interpretation": "x", "provider": "openai"},     # provider injection
        {"interpretation": "x", "model": "gpt-x"},         # identity self-report
        {"interpretation": "x", "outcome": {"ok": True}},  # outcome creation
        {"interpretation": "x", "fact": {"v": 1}},         # fact creation
        {"interpretation": "x", "hypotheses": [{"ref": "h", "proposition": "p",
                                                "subject_ref": "s", "extra": 1}]},  # nested extra
    ])
    def test_smuggled_authority_fields_rejected(self, payload):
        with pytest.raises(ValidationError):
            InvestigationProposalSchema.model_validate(payload)

    def test_test_with_shell_command_arguments_rejected(self):
        # the classic malicious proposal: tool=shell + arguments.command + flags
        malicious = {"interpretation": "x", "test": {
            "discriminates": "h1", "tool": "shell", "subject_ref": "s", "predicate": "p",
            "evidence_expected": "e", "supports_if": "a", "contradicts_if": "b",
            "residual_uncertainty": "c", "arguments": {"command": "terraform apply -auto-approve"},
            "success": True, "verified": True, "autonomy": "A4"}}
        with pytest.raises(ValidationError):
            InvestigationProposalSchema.model_validate(malicious)

    def test_valid_minimal_proposal_parses(self):
        ok = InvestigationProposalSchema.model_validate({"interpretation": "ok"})
        assert ok.test is None and ok.hypotheses == []


# ======================================================================
# The governed port: platform identity + failure classification
# ======================================================================

def _boundary(responder, *, recorder=None):
    return GovernedModelBoundary(
        model_port=ScriptedModelPort(responder), recorder=recorder or InMemoryTraceRecorder(),
        harness_version=CURRENT_HARNESS_VERSION)


def _svc():
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
    return InvestigationService(repository=MemRepo())


def _open(svc):
    inv = svc.create(tenant=ACME, incident_ref="incident:latency", policy_ref="pol/1",
                     harness_version="h/1", now=_t(0))
    return svc.transition(investigation=inv, to_status=InvestigationStatus.INVESTIGATING,
                          cause="triage", now=_t(1))


def _responder(prompt: str) -> str:
    """Scripted investigator: reads the assembled-context prompt, proposes the
    differential then a discriminating test for the next OPEN hypothesis."""
    ctx = json.loads(prompt)
    hyps = next((s["content"] for s in ctx["sections"] if s["section_type"] == "hypotheses"), [])
    if not hyps:
        return json.dumps({
            "interpretation": "propose the differential",
            "hypotheses": [
                {"ref": "h1", "proposition": "rollout", "subject_ref": SUBJECT, "temporal_fit": "consistent"},
                {"ref": "h2", "proposition": "db saturation", "subject_ref": SUBJECT, "temporal_fit": "unknown"},
                {"ref": "h3", "proposition": "network", "subject_ref": SUBJECT, "temporal_fit": "unknown"}],
            "test": _test("h1")})
    target = next((h["hypothesis_ref"] for h in hyps if h["status"] == "open"), None)
    return json.dumps({"interpretation": "discriminate", "hypotheses": [],
                       "test": _test(target) if target else None})


def _test(ref):
    return {"discriminates": ref, "tool": "deploy.history", "subject_ref": SUBJECT,
            "predicate": PREDICATE, "evidence_expected": "cause", "supports_if": "matches",
            "contradicts_if": "differs", "residual_uncertainty": "timing",
            "supports_value": CAUSE if ref == "h1" else {"cause": "other"},
            "contradicts_value": {"cause": "other"} if ref == "h1" else CAUSE}


class _Evidence:
    reads = 0
    def acquire(self, *, tenant, request, now):
        _Evidence.reads += 1
        return EvidenceResult(ok=True, subject_ref=request.subject_ref, predicate=request.predicate,
                              observation_ref=f"wobs-{_Evidence.reads}", observed_value=CAUSE,
                              source_ref="connector:kubernetes")


class _World:
    def evidence_for(self, *, tenant, subject_ref, predicate, now):
        return {"subject_ref": subject_ref, "value": CAUSE, "status": "affirmed"}


def _engine(model_port, evidence=None):
    svc = _svc()
    return svc, InvestigationEngine(
        service=svc, assembler=ContextAssembler(), model_port=model_port,
        evidence_port=evidence or _Evidence(), world_read_port=_World(),
        policy=EvidenceSelectionPolicy(), harness_version="h/1",
        available_tools=("deploy.history",))


class TestGovernedPort:
    def test_provider_identity_from_platform_not_model(self):
        port = GovernedModelProposalPort(boundary=_boundary(_responder))
        svc = _svc()
        inv = _open(svc)
        eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                  evidence_port=_Evidence(), world_read_port=_World(),
                                  policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                  available_tools=("deploy.history",))
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        assert res.provider == "scripted"  # from the ModelInvocation, not the model JSON

    def test_full_loop_via_live_boundary_resolves(self):
        port = GovernedModelProposalPort(boundary=_boundary(_responder))
        _Evidence.reads = 0
        svc = _svc()
        inv = _open(svc)
        eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                  evidence_port=_Evidence(), world_read_port=_World(),
                                  policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                  available_tools=("deploy.history",))
        final = eng.run(investigation=inv, budget=InvestigationBudget(), clock=lambda i: _t(2 + i))
        assert final.status is InvestigationStatus.COMPLETED
        assert final.conclusion is InvestigationConclusion.RESOLVED

    def test_malformed_output_fails_closed_no_success(self):
        port = GovernedModelProposalPort(boundary=_boundary(lambda p: "not json {{{"))
        svc = _svc()
        inv = _open(svc)
        eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                  evidence_port=_Evidence(), world_read_port=_World(),
                                  policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                  available_tools=("deploy.history",))
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        assert res.outcome is StepOutcome.TEST_REJECTED
        assert res.investigation.conclusion is None  # no fabricated success
        assert res.investigation.status is InvestigationStatus.INVESTIGATING

    def test_smuggled_success_field_fails_closed(self):
        # the model returns valid-looking JSON but with a smuggled authority field
        port = GovernedModelProposalPort(boundary=_boundary(
            lambda p: json.dumps({"interpretation": "x", "success": True, "autonomy": "A4"})))
        svc = _svc()
        inv = _open(svc)
        eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                  evidence_port=_Evidence(), world_read_port=_World(),
                                  policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                  available_tools=("deploy.history",))
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        assert res.outcome is StepOutcome.TEST_REJECTED  # extra=forbid rejected it
        assert res.investigation.conclusion is None
        assert res.investigation.autonomy_level.value == "a1_investigate"  # not promoted

    def test_trace_failure_fails_closed_blocked(self):
        class FailingRecorder:
            def record(self, span):
                raise RuntimeError("disk full")
        port = GovernedModelProposalPort(boundary=_boundary(_responder, recorder=FailingRecorder()))
        svc = _svc()
        inv = _open(svc)
        eng = InvestigationEngine(service=svc, assembler=ContextAssembler(), model_port=port,
                                  evidence_port=_Evidence(), world_read_port=_World(),
                                  policy=EvidenceSelectionPolicy(), harness_version="h/1",
                                  available_tools=("deploy.history",))
        res = eng.step(investigation=inv, budget=InvestigationBudget(), now=_t(2))
        # pre-action trace failure -> BLOCKED (L14), never advances to a read
        assert res.investigation.conclusion is InvestigationConclusion.BLOCKED
        assert res.investigation.status is InvestigationStatus.FAILED
