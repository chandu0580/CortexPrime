"""Phase 9.5 (ADR-085): the read-only incident investigator — unit evidence.

What these prove without a cluster:

- The tool registry refuses a WRITE capability **at construction**, so no
  investigation can ever select one. Read-only is a property of assembly, not a
  check somebody has to remember at call time.
- A tool naming an operation no catalog declares is refused, and so is a subject
  reference of the wrong shape — before any provider is contacted.
- The evidence port refuses a URL, a shell fragment, an unknown tool and a
  non-read request, and contacts nothing while doing so.
- The five CrashLoopBackOff hypotheses are seeded OPEN with stated gaps. None of
  them is a finding, and none carries a number.
- The declared projections extract only what the instrument reported, and return
  None — "not observed" — rather than a default, when it reported nothing.
- ``settle`` and the report preserve residual uncertainty, name what eliminated
  what, and never claim Assurance verified something it did not.

The real-cluster legs live in ``scripts/phase95_incident_investigator_harness.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.world import HypothesisStatus
from backend.api.governed_evidence_acquisition import (
    GovernedEvidenceAcquisition, InvestigationTool, ToolRegistry,
)
from backend.api.incident_investigation import (
    CRASHLOOP_HYPOTHESES, H_CONFIG, H_DEPENDENCY, H_REGRESSION, H_RESOURCE,
    H_STARTUP, assemble_report, crashloop_hypotheses, crashloop_tools,
)
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    kubernetes_read_catalog,
)
from backend.contexts.execution.infrastructure.adapters.connectors.prometheus import (
    prometheus_read_catalog,
)

NS = "cortex-p95"
POD_SUBJECT = f"kubernetes:pod:{NS}/payments-api-x"
DEPLOY_SUBJECT = f"kubernetes:deployment:{NS}/payments-api"


def _catalogs():
    return {"kubernetes": kubernetes_read_catalog(),
            "prometheus": prometheus_read_catalog(namespace=NS)}


def _registry():
    return ToolRegistry(tools=crashloop_tools(memory_limit_bytes=67108864),
                        catalogs=_catalogs())


# ---------------------------------------------------------------------------
# Read-only, structurally
# ---------------------------------------------------------------------------

class TestReadOnlyByConstruction:
    def test_the_frozen_allowlist_is_exactly_five_read_tools(self):
        registry = _registry()
        assert registry.keys == (
            "k8s.deployment_revision", "k8s.pod_state", "k8s.pod_termination",
            "metrics.pod_memory", "metrics.pod_restarts")

    def test_every_tool_binds_a_read_capability(self):
        from backend.contracts.execution import SideEffectClass
        catalogs = _catalogs()
        for tool in crashloop_tools(memory_limit_bytes=1):
            spec = next(c.get(tool.operation) for c in catalogs.values()
                        if c.get(tool.operation) is not None)
            assert spec.side_effect_class is SideEffectClass.READ

    def test_a_tool_naming_a_write_capability_is_refused_at_construction(self):
        from backend.contexts.execution.infrastructure.adapters.connectors.grafana import (
            grafana_catalog,
        )
        # The counterexample has to be built from a catalog that HAS a write, and
        # neither investigation catalog does — which is the stronger fact.
        with pytest.raises(ContractViolation, match="does not act"):
            ToolRegistry(tools=(InvestigationTool(
                key="grafana.create_folder", operation="folder.create_folder",
                subject_kind="grafana:folder:", predicate="created",
                describes="a write", project=lambda e: {},
                source_ref="connector:grafana", payload_from_subject=lambda s: {}),),
                catalogs={"grafana": grafana_catalog()})

    def test_a_tool_naming_an_undeclared_operation_is_refused(self):
        with pytest.raises(ContractViolation, match="no composed catalog declares"):
            ToolRegistry(tools=(InvestigationTool(
                key="k8s.delete_pod", operation="kubernetes.pod.delete",
                subject_kind="kubernetes:pod:", predicate="deleted",
                describes="a write that does not exist", project=lambda e: {},
                source_ref="connector:kubernetes", payload_from_subject=lambda s: {}),),
                catalogs=_catalogs())

    def test_an_empty_registry_is_refused(self):
        with pytest.raises(ContractViolation, match="observe nothing"):
            ToolRegistry(tools=(), catalogs=_catalogs())

    def test_a_duplicate_tool_key_is_refused(self):
        tools = crashloop_tools(memory_limit_bytes=1)
        with pytest.raises(ContractViolation, match="declared twice"):
            ToolRegistry(tools=tools + (tools[0],), catalogs=_catalogs())


# ---------------------------------------------------------------------------
# The evidence port's refusals
# ---------------------------------------------------------------------------

class _NeverReads:
    """A reader that fails the test if it is ever called."""

    def __init__(self): self.calls = 0

    def read(self, *a, **kw):
        self.calls += 1
        raise AssertionError("a refused request must never reach a provider")


class _Request:
    def __init__(self, tool, subject_ref, predicate="p", read_only=True):
        self.tool, self.subject_ref = tool, subject_ref
        self.predicate, self.read_only = predicate, read_only


def _port(reader=None):
    return GovernedEvidenceAcquisition(
        reader=reader or _NeverReads(), observer=object(), derivation=None,
        registry=_registry(), context=object())


class TestEvidencePortRefusals:
    def _refused(self, request):
        reader = _NeverReads()
        result = _port(reader).acquire(tenant=object(), request=request,
                                        now=datetime.now(timezone.utc))
        assert result.ok is False
        assert reader.calls == 0, "a refusal contacted a provider"
        return result.reason

    def test_an_unknown_tool_is_refused_and_contacts_nothing(self):
        reason = self._refused(_Request("prometheus.raw_query", POD_SUBJECT))
        assert "frozen read-only allowlist" in reason

    def test_a_url_subject_is_refused_and_contacts_nothing(self):
        reason = self._refused(_Request("k8s.pod_state",
                                        "https://10.0.0.1:6443/api/v1/secrets"))
        assert "is not one" in reason

    def test_a_shell_fragment_subject_is_refused(self):
        assert self._refused(_Request("k8s.pod_state", "$(cat /etc/shadow)"))

    def test_a_deployment_tool_refuses_a_pod_subject(self):
        # Not a formality: a read that answered about the wrong object would be
        # confidently wrong, which is worse than refusing.
        reason = self._refused(_Request("k8s.deployment_revision", POD_SUBJECT))
        assert "observes" in reason

    def test_a_non_read_request_is_refused(self):
        reason = self._refused(_Request("k8s.pod_state", POD_SUBJECT, read_only=False))
        assert "does not act" in reason

    def test_a_malformed_pod_reference_is_refused(self):
        assert self._refused(_Request("k8s.pod_state", "kubernetes:pod:no-slash"))


# ---------------------------------------------------------------------------
# The differential
# ---------------------------------------------------------------------------

class TestCrashLoopDifferential:
    def test_five_competing_hypotheses_are_seeded_open(self):
        seeded = crashloop_hypotheses(subject_ref=POD_SUBJECT)
        assert {h.hypothesis_ref for h in seeded} == {
            H_STARTUP, H_CONFIG, H_DEPENDENCY, H_RESOURCE, H_REGRESSION}
        assert all(h.status is HypothesisStatus.OPEN for h in seeded)

    def test_none_of_them_is_a_finding(self):
        from backend.contracts.intelligence import TemporalFit
        for hypothesis in crashloop_hypotheses(subject_ref=POD_SUBJECT):
            # Temporal fit stays UNKNOWN until an observation says otherwise:
            # asserting a hypothesis fits the timeline before observing the
            # timeline is the assumption this apparatus exists to avoid.
            assert hypothesis.temporal_fit is TemporalFit.UNKNOWN
            assert hypothesis.evidence_for == ()
            assert hypothesis.evidence_against == ()

    def test_every_hypothesis_states_why_it_is_unresolved(self):
        for hypothesis in crashloop_hypotheses(subject_ref=POD_SUBJECT):
            assert hypothesis.missing_evidence

    def test_no_hypothesis_carries_a_number(self):
        blob = json.dumps([h.to_dict() for h in
                           crashloop_hypotheses(subject_ref=POD_SUBJECT)], default=str)
        assert "confidence" not in blob.lower()
        assert "probability" not in blob.lower()
        assert "%" not in blob

    def test_the_hypothesis_set_is_pinned(self):
        # Pinned so the differential does not silently narrow: an investigation
        # that stops considering an explanation stops being one.
        assert len(CRASHLOOP_HYPOTHESES) == 5


# ---------------------------------------------------------------------------
# The declared projections
# ---------------------------------------------------------------------------

def _tool(key):
    return next(t for t in crashloop_tools(memory_limit_bytes=67108864)
                if t.key == key)


class TestProjections:
    def test_termination_needs_both_halves_or_neither(self):
        project = _tool("k8s.pod_termination").project
        assert project({"lastExitCode": 1, "lastTerminationReason": "Error"}) == {
            "exitCode": 1, "reason": "Error"}
        # Half an answer about why a process died gets read as the whole one.
        assert project({"lastExitCode": 1}) is None
        assert project({"lastTerminationReason": "Error"}) is None
        assert project({}) is None

    def test_an_oom_kill_projects_distinctly_from_an_application_failure(self):
        project = _tool("k8s.pod_termination").project
        oom = project({"lastExitCode": 137, "lastTerminationReason": "OOMKilled"})
        app = project({"lastExitCode": 1, "lastTerminationReason": "Error"})
        assert oom != app, "the two must be distinguishable or H4 cannot be tested"

    def test_memory_pressure_is_categorical_not_a_percentage(self):
        project = _tool("metrics.pod_memory").project
        below = project({"series": [{"value": "2736128"}]})
        above = project({"series": [{"value": "70000000"}]})
        assert below == {"atOrAboveLimit": False}
        assert above == {"atOrAboveLimit": True}
        # A number here would be a confidence score in disguise.
        assert set(below) == {"atOrAboveLimit"}

    def test_memory_takes_the_PEAK_across_series_not_the_first(self):
        project = _tool("metrics.pod_memory").project
        assert project({"series": [{"value": "1000"}, {"value": "70000000"}]}) == {
            "atOrAboveLimit": True}

    def test_a_projection_returns_none_when_nothing_was_observed(self):
        for key in ("k8s.pod_state", "k8s.deployment_revision",
                    "metrics.pod_memory", "metrics.pod_restarts"):
            assert _tool(key).project({}) is None, key

    def test_deployment_revision_needs_both_revision_and_image(self):
        project = _tool("k8s.deployment_revision").project
        assert project({"revision": "2", "image": "busybox:1.36"}) == {
            "revision": "2", "image": "busybox:1.36"}
        assert project({"revision": "2"}) is None

    def test_the_metric_restart_count_keeps_the_9_4_proposition_shape(self):
        # Same shape as the Kubernetes side, or corroboration compares two
        # digests and calls agreement a contradiction.
        assert _tool("metrics.pod_restarts").project(
            {"series": [{"value": "7"}]}) == {"restartCount": 7}


# ---------------------------------------------------------------------------
# The explainable report
# ---------------------------------------------------------------------------

class _Investigation:
    def __init__(self, differential, conclusion=None):
        self.differential = tuple(differential)
        self.conclusion = conclusion
        self.incident_ref = "incident:ns/pod:crashloopbackoff"
        self.investigation_ref = "winv_x"


def _hypothesis(ref, status, *, for_=(), against=()):
    from dataclasses import replace
    base = next(h for h in crashloop_hypotheses(subject_ref=POD_SUBJECT)
                if h.hypothesis_ref == ref)
    return replace(base, status=status, evidence_for=tuple(for_),
                   evidence_against=tuple(against))


class TestInvestigationReport:
    def _report(self, **kw):
        return assemble_report(investigation=_Investigation([
            _hypothesis(H_RESOURCE, HypothesisStatus.REFUTED, against=("wobs_1",)),
            _hypothesis(H_REGRESSION, HypothesisStatus.SUPPORTED, for_=("wobs_2",)),
            _hypothesis(H_STARTUP, HypothesisStatus.OPEN),
            _hypothesis(H_CONFIG, HypothesisStatus.OPEN),
            _hypothesis(H_DEPENDENCY, HypothesisStatus.OPEN),
        ]), **kw)

    def test_it_names_what_was_eliminated_and_by_what(self):
        document = self._report().to_dict()
        assert document["hypotheses"]["eliminated"] == [H_RESOURCE]
        assert document["why_eliminated"][H_RESOURCE] == ["wobs_1"]

    def test_it_names_what_is_supported_and_by_what(self):
        document = self._report().to_dict()
        assert document["hypotheses"]["supported"] == [H_REGRESSION]
        assert document["why_supported"][H_REGRESSION] == ["wobs_2"]

    def test_it_keeps_the_still_open_alternatives_visible(self):
        document = self._report().to_dict()
        assert set(document["hypotheses"]["still_open"]) == {
            H_STARTUP, H_CONFIG, H_DEPENDENCY}

    def test_residual_uncertainty_names_the_alternatives_not_eliminated(self):
        residual = self._report().residual_uncertainty
        assert "not eliminated" in residual
        assert H_STARTUP in residual

    def test_without_assurance_the_report_says_so_rather_than_omitting_it(self):
        report = self._report()
        assert report.assurance is None
        assert "not been independently verified" in report.residual_uncertainty

    def test_it_never_states_a_percentage_or_a_confidence(self):
        blob = json.dumps(self._report().to_dict(), default=str).lower()
        assert "%" not in blob and "confidence" not in blob

    def test_it_declares_itself_read_only(self):
        assert self._report().to_dict()["read_only"] is True

    def test_the_rendering_is_traceable_to_fields(self):
        rendered = self._report().render()
        assert H_REGRESSION in rendered and H_RESOURCE in rendered
        assert "RESIDUAL" in rendered and "STILL OPEN" in rendered

    def test_two_supported_hypotheses_produce_no_single_diagnosis(self):
        report = assemble_report(investigation=_Investigation([
            _hypothesis(H_REGRESSION, HypothesisStatus.SUPPORTED, for_=("wobs_1",)),
            _hypothesis(H_CONFIG, HypothesisStatus.SUPPORTED, for_=("wobs_2",)),
        ]))
        assert report.diagnosis is None
        assert report.conclusion == "conflicted"
        assert "competing" in report.residual_uncertainty


# ---------------------------------------------------------------------------
# The Intelligence Plane still cannot reach a provider
# ---------------------------------------------------------------------------

class TestIntelligenceCannotReachAProvider:
    def test_no_intelligence_module_imports_a_connector_or_http_client(self):
        import os
        import backend.intelligence as intel
        offenders = []
        for root, _dirs, files in os.walk(os.path.dirname(intel.__file__)):
            for name in files:
                if not name.endswith(".py"):
                    continue
                text = open(os.path.join(root, name), encoding="utf-8").read()
                if ("adapters.connectors" in text or "import httpx" in text
                        or "backend.connectors" in text):
                    offenders.append(name)
        assert offenders == []

    def test_the_evidence_request_contract_has_no_write_field(self):
        import dataclasses
        from backend.intelligence.application.proposal import EvidenceRequest
        fields = {f.name for f in dataclasses.fields(EvidenceRequest)}
        assert fields == {"tool", "subject_ref", "predicate", "read_only"}

    def test_the_acquisition_port_holds_no_provider(self):
        assert set(GovernedEvidenceAcquisition.__slots__) == {
            "_reader", "_observer", "_derivation", "_registry", "_context", "_clock"}

    def test_the_model_schema_rejects_every_authority_field(self):
        import pydantic
        from backend.intelligence.application.model_boundary import (
            InvestigationProposalSchema,
        )
        for smuggled in ("verified", "confidence", "autonomy_level", "provider",
                         "tenant", "url", "command", "success", "status"):
            with pytest.raises(pydantic.ValidationError):
                InvestigationProposalSchema(**{"interpretation": "x", smuggled: "v"})
