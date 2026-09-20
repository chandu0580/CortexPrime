"""Phase 9.1 — the governed capability bridge + Kubernetes READ contract.

Kubernetes becomes a governed capability by REUSE: a CapabilityProfile binds each
governed operation to its Phase-8 risk/reversibility/verification/autonomy_ceiling
(no second capability model). The K8s catalog is read-only by construction, every
read preserves resourceVersion in its evidence, and the bridge produces the Phase-8
Capability the AutonomyPolicy already consumes. In-memory contracts; the
real-Postgres governed read + observation is the phase91 harness.
"""

from __future__ import annotations

import pytest

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.policy import RiskClassification, RiskFactors, RiskLevel
from backend.contracts.intelligence import (
    AutonomyLevel, Capability, CapabilityProfile, VerificationRequirement,
)
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    KUBERNETES_PROVIDER_ID, KUBERNETES_READ_OPERATIONS, kubernetes_read_catalog,
    kubernetes_read_profiles,
)


def _risk(sec=SideEffectClass.READ, reversible=True):
    return RiskClassification(
        level=RiskLevel.LOW, rationale="test",
        factors=RiskFactors(side_effect_class=sec, environment="development",
                            resource_count=1, reversible=reversible))


def _profile(sec, ceiling, verification, reversible=True):
    return CapabilityProfile(
        capability_ref="platform.x.op", provider="x", operation="op", side_effect_class=sec,
        effect_semantics=EffectSemantics.READ_ONLY if sec is SideEffectClass.READ
        else EffectSemantics.NON_IDEMPOTENT_WRITE,
        risk=_risk(sec, reversible), autonomy_ceiling=ceiling,
        verification_requirement=verification, resource_scope="pod", reversible=reversible,
        timeout_seconds=10.0, policy_version="v1")


# ======================================================================
# The bridge (Part B) — reuse, four distinct concepts
# ======================================================================

class TestBridge:
    def test_profile_bridges_to_phase8_capability(self):
        p = _profile(SideEffectClass.READ, AutonomyLevel.A1_INVESTIGATE, VerificationRequirement.NONE)
        cap = p.to_capability()
        assert isinstance(cap, Capability)
        assert cap.side_effect_class is SideEffectClass.READ and cap.reversible is True

    def test_reuses_existing_risk_and_autonomy_types(self):
        p = _profile(SideEffectClass.READ, AutonomyLevel.A1_INVESTIGATE, VerificationRequirement.NONE)
        assert isinstance(p.risk, RiskClassification) and isinstance(p.autonomy_ceiling, AutonomyLevel)

    def test_capability_not_a_number(self):
        d = _profile(SideEffectClass.READ, AutonomyLevel.A1_INVESTIGATE, VerificationRequirement.NONE).to_dict()
        assert "autonomy_ceiling" in d and not any("score" in k for k in d)


# ======================================================================
# Read-only guarantee (Part D) — construction-time invariant
# ======================================================================

class TestReadOnlyGuarantee:
    def test_read_with_action_ceiling_rejected(self):
        for ceiling in (AutonomyLevel.A2_RECOMMEND, AutonomyLevel.A3_APPROVED_ACTION,
                        AutonomyLevel.A4_AUTONOMOUS):
            with pytest.raises(ContractViolation):
                _profile(SideEffectClass.READ, ceiling, VerificationRequirement.NONE)

    def test_read_requiring_verification_rejected(self):
        with pytest.raises(ContractViolation):
            _profile(SideEffectClass.READ, AutonomyLevel.A1_INVESTIGATE,
                     VerificationRequirement.INDEPENDENT_READBACK)

    def test_read_a1_none_accepted(self):
        p = _profile(SideEffectClass.READ, AutonomyLevel.A1_INVESTIGATE, VerificationRequirement.NONE)
        assert p.is_read_only

    def test_mutating_without_verification_rejected(self):
        with pytest.raises(ContractViolation):
            _profile(SideEffectClass.REVERSIBLE_WRITE, AutonomyLevel.A3_APPROVED_ACTION,
                     VerificationRequirement.NONE)

    def test_mutating_with_verification_accepted(self):
        p = _profile(SideEffectClass.REVERSIBLE_WRITE, AutonomyLevel.A3_APPROVED_ACTION,
                     VerificationRequirement.INDEPENDENT_READBACK)
        assert not p.is_read_only


# ======================================================================
# The Kubernetes catalog (Part C/D/F)
# ======================================================================

class TestKubernetesCatalog:
    def test_catalog_declares_the_smallest_read_set(self):
        cat = kubernetes_read_catalog()
        assert set(cat.operations) == set(KUBERNETES_READ_OPERATIONS)
        # Six reads for the first incident vertical (9.1), plus the WATCH that
        # continues the list (9.3), the ReplicaSet lineage read (11.3) that
        # answers "what changed, and when", and the connection's own permission
        # check (11.1-K) that connector health asks the cluster. Pinned so a
        # tenth does not appear by habit.
        assert len(KUBERNETES_READ_OPERATIONS) == 9
        assert "kubernetes.replicasets.list" in KUBERNETES_READ_OPERATIONS
        assert "kubernetes.access.review" in KUBERNETES_READ_OPERATIONS

    def test_catalog_is_read_only_by_construction(self):
        cat = kubernetes_read_catalog()
        for op in cat.operations:
            spec = cat.require(op)
            assert spec.side_effect_class is SideEffectClass.READ
            assert spec.effect_semantics is EffectSemantics.READ_ONLY
            if op == "kubernetes.access.review":
                # The ONE read that is an HTTP POST, and only because the
                # Kubernetes API asks a SelfSubjectAccessReview that way: the
                # API server evaluates the question and stores nothing (11.1-K).
                # Held to the exact endpoint so "a read may POST" cannot spread.
                assert spec.method == "POST"
                assert spec.path_template == (
                    "/apis/authorization.k8s.io/v1/selfsubjectaccessreviews")
            else:
                assert spec.method == "GET"

    def test_only_the_access_review_may_be_a_posting_read(self):
        """The exception above, stated as its own invariant."""
        cat = kubernetes_read_catalog()
        posting = {op for op in cat.operations if cat.require(op).method != "GET"}
        assert posting == {"kubernetes.access.review"}

    def test_no_write_operation_present(self):
        cat = kubernetes_read_catalog()
        forbidden = {"create", "update", "patch", "delete", "scale", "restart",
                     "rollout", "exec", "apply", "replace"}
        assert not any(any(w in op for w in forbidden) for op in cat.operations)

    def test_resourceversion_preserved_in_evidence(self):
        cat = kubernetes_read_catalog()
        # every LIST/GET keeps resourceVersion in its bounded evidence (Part F);
        # only the log op (no envelope) legitimately omits it.
        for op in cat.operations:
            spec = cat.require(op)
            if op in ("kubernetes.pod.logs", "kubernetes.access.review"):
                # Neither answers with an object envelope: a log has none, and a
                # review answers only allowed/denied/reason (11.1-K).
                assert "resourceVersion" not in spec.response_evidence_fields
            elif op == "kubernetes.pods.watch":
                # A watch window has no single envelope version: the position is
                # the LAST event's, and each event keeps its own. Both are
                # declared, so continuity still survives into evidence (9.3).
                assert "lastResourceVersion" in spec.response_evidence_fields
                assert "resourceVersion" in spec.response_evidence_records.fields
            else:
                assert "resourceVersion" in spec.response_evidence_fields
                assert "resourceVersion" in spec.response_required_fields

    def test_profiles_are_read_only_a1(self):
        profs = kubernetes_read_profiles()
        assert set(profs) == set(KUBERNETES_READ_OPERATIONS)
        for p in profs.values():
            assert p.is_read_only
            assert p.autonomy_ceiling is AutonomyLevel.A1_INVESTIGATE
            assert p.verification_requirement is VerificationRequirement.NONE
            assert p.provider == KUBERNETES_PROVIDER_ID

    def test_profile_bridges_each_op_to_a_capability(self):
        for op, p in kubernetes_read_profiles().items():
            cap = p.to_capability()
            assert cap.operation == op and cap.side_effect_class is SideEffectClass.READ


# ======================================================================
# The governed K8s module reaches no provider directly (Part E) — structural
# ======================================================================

class TestNoDirectProvider:
    def test_module_imports_no_sdk_httpx_or_v1_connector(self):
        import ast
        import inspect
        import backend.contexts.execution.infrastructure.adapters.connectors.kubernetes as m
        tree = ast.parse(inspect.getsource(m))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        # the governed catalog declares the contract; it imports no client / V1 / creds
        assert not any(i == "kubernetes" or i.startswith("kubernetes.") for i in imported)
        assert "httpx" not in imported and "requests" not in imported and "os" not in imported
        assert not any(i.startswith("backend.connectors") for i in imported)  # no V1 dep (Part R)

    def test_existing_fitness_rules_fence_the_governed_plane(self):
        from pathlib import Path
        from backend.platform.architecture.boundary_rules import (
            ProviderSdkImportRule, DirectProviderHttpRule)
        from backend.platform.architecture.rules import ModuleGraph
        graph = ModuleGraph.build(Path(__file__).resolve().parents[2] / "backend")
        assert ProviderSdkImportRule().evaluate(graph).passed      # no k8s SDK in the module
        assert DirectProviderHttpRule().evaluate(graph).passed     # no httpx in contexts
