"""Phase 9.2 (ADR-082): the REAL governed Kubernetes read adapter — unit evidence.

What these tests prove without a network:

- The normalizer lifts ``metadata.resourceVersion`` to the top level EXACTLY as
  returned (opaque string, never coerced, never fabricated) and computes the
  declared list counts — the code the 9.1 docstring promised.
- The generic ``ConnectorAdapter`` applies the normalizer only on classified
  success, refuses an envelope it cannot understand as MALFORMED_RESPONSE, and
  refuses a response with no resourceVersion rather than inventing one (Part N:
  reject, never synthesize).
- Kubernetes failure statuses classify as PROVIDER failures (401/403/404), kept
  distinct from CortexPrime authorization (Part L).
- The real exposure is exactly ONE operation (Part E), the channel refuses
  plaintext, and the factory refuses the scripted/real dual path (Part U).
- ``provider_evidence`` survives onto the published ``ExecutionResult`` (Part H).

The real-cluster legs live in ``scripts/phase92_kubernetes_real_harness.py``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from backend.contracts.provider import ProviderDelivery, ProviderFailure
from backend.contexts.execution.infrastructure.adapters.channel import ProviderExchange
from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
    KUBERNETES_REAL_READ_OPERATIONS,
    KubernetesReadNormalizer,
    KubernetesResponseTranslator,
    kubernetes_read_catalog,
    kubernetes_real_read_catalog,
)


def _pods_list_spec():
    return kubernetes_real_read_catalog().require("kubernetes.pods.list")


def _pod_list_body(rv="424242", items=None):
    return {
        "kind": "PodList",
        "apiVersion": "v1",
        "metadata": {"resourceVersion": rv} if rv is not None else {},
        "items": items if items is not None else [],
    }


def _crashloop_pod(restarts=7):
    return {
        "metadata": {"name": "payments-abc", "namespace": "payments"},
        "status": {
            "phase": "Running",
            "containerStatuses": [
                {"restartCount": restarts,
                 "state": {"waiting": {"reason": "CrashLoopBackOff"}}}
            ],
        },
    }


def _running_pod():
    return {
        "metadata": {"name": "web-1", "namespace": "payments"},
        "status": {"phase": "Running",
                   "containerStatuses": [{"restartCount": 0, "state": {"running": {}}}]},
    }


class TestNormalizer:
    def test_lifts_resource_version_exactly(self):
        # Opaque: leading zeros and non-numeric shapes survive byte-for-byte.
        for rv in ("424242", "00123", "9a8b7c"):
            out = KubernetesReadNormalizer().normalize(_pods_list_spec(), _pod_list_body(rv=rv))
            assert out["resourceVersion"] == rv
            assert isinstance(out["resourceVersion"], str)

    def test_never_fabricates_resource_version(self):
        out = KubernetesReadNormalizer().normalize(_pods_list_spec(), _pod_list_body(rv=None))
        assert "resourceVersion" not in out
        # ...and the spec then refuses the shape: reject, never synthesize.
        assert _pods_list_spec().response_problems(out)

    def test_counts_and_crashloop_signal(self):
        body = _pod_list_body(items=[_crashloop_pod(), _running_pod(), _running_pod()])
        out = KubernetesReadNormalizer().normalize(_pods_list_spec(), body)
        assert out["podCount"] == 3
        assert out["crashLoopCount"] == 1

    def test_evidence_contract_after_normalization(self):
        body = _pod_list_body(items=[_running_pod()])
        out = KubernetesReadNormalizer().normalize(_pods_list_spec(), body)
        evidence = _pods_list_spec().evidence(out)
        # The declared scalars, unchanged since 9.2...
        assert {k: v for k, v in evidence.items() if k != "pods"} == {
            "resourceVersion": "424242", "kind": "PodList", "apiVersion": "v1",
            "podCount": 1, "crashLoopCount": 0,
        }
        # ...plus the per-pod records 9.4 added (ADR-084). Counts alone are enough
        # to notice something is wrong and not enough to say anything about a
        # PARTICULAR pod, so a list could not corroborate a metric that names one.
        assert [record["name"] for record in evidence["pods"]] == ["web-1"]

    def test_raw_kubernetes_body_fails_shape_without_normalizer(self):
        # The lift is load-bearing: the raw envelope does not satisfy the
        # declared contract, so nothing can quietly skip normalization.
        assert _pods_list_spec().response_problems(_pod_list_body())

    def test_pod_get_and_deployment_get_lifts(self):
        full = kubernetes_read_catalog()
        pod = KubernetesReadNormalizer().normalize(
            full.require("kubernetes.pod.get"),
            {"kind": "Pod", "apiVersion": "v1",
             "metadata": {"name": "payments-abc", "namespace": "payments",
                          "resourceVersion": "77"},
             "status": {"phase": "Running", "containerStatuses": [
                 {"restartCount": 7, "state": {"waiting": {"reason": "CrashLoopBackOff"}}}]}})
        assert (pod["resourceVersion"], pod["name"], pod["namespace"]) == ("77", "payments-abc", "payments")
        assert (pod["phase"], pod["restartCount"], pod["waitingReason"]) == ("Running", 7, "CrashLoopBackOff")

        deploy = KubernetesReadNormalizer().normalize(
            full.require("kubernetes.deployment.get"),
            {"kind": "Deployment", "apiVersion": "apps/v1",
             "metadata": {"name": "payments", "namespace": "payments", "resourceVersion": "88"},
             "spec": {"replicas": 3}, "status": {"readyReplicas": 0, "availableReplicas": 0}})
        assert (deploy["resourceVersion"], deploy["replicas"]) == ("88", 3)
        assert (deploy["readyReplicas"], deploy["availableReplicas"]) == (0, 0)

    def test_non_mapping_body_is_refused_not_invented(self):
        with pytest.raises(ValueError):
            KubernetesReadNormalizer().normalize(_pods_list_spec(), "not-an-envelope")


class _AdapterHarness:
    """The real ConnectorAdapter with a real catalog and normalizer, driven at
    the ``_normalise`` seam with constructed exchanges — no channel, no network."""

    def __init__(self):
        from backend.contracts.connector import IsolationTier
        from backend.contracts.provider import ProviderRef
        from backend.contexts.execution import WorkerInterface, WorkerScope
        from backend.contracts.execution import ExecutionEnvironment
        from backend.contexts.execution.domain.worker import WorkerKind
        from backend.contexts.execution.domain.worker_directory import WorkerImplementation
        from backend.contexts.execution.infrastructure.adapters.connector import ConnectorAdapter

        catalog = kubernetes_real_read_catalog()
        implementation = WorkerImplementation(
            worker_id="kubernetes-connector", worker_kind=WorkerKind.CONNECTOR,
            interface=WorkerInterface.CONNECTOR,
            implementation="ConnectorAdapter+connectors.kubernetes",
            implementation_version="1.0.0", isolation=IsolationTier.CONTAINED,
            scope=WorkerScope.PLATFORM,
            supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
            supported_effects=frozenset(
                {catalog.require(op).effect_semantics for op in catalog.operations}),
            supported_providers=frozenset({"kubernetes"}),
            supported_operations=frozenset(catalog.operations),
            supports_provider_idempotency=False)
        self.adapter = ConnectorAdapter(
            implementation=implementation,
            provider=ProviderRef(provider_id="kubernetes"),
            catalog=catalog,
            translator=KubernetesResponseTranslator(),
            normalizer=KubernetesReadNormalizer(),
        )
        self.spec = catalog.require("kubernetes.pods.list")

    def normalise(self, *, status=200, body):
        payload = json.dumps(body).encode() if not isinstance(body, bytes) else body
        exchange = ProviderExchange(
            delivery=ProviderDelivery.DELIVERED, status_code=status,
            body=payload, response_digest="d")
        return self.adapter._normalise(self.spec, _authority_stub(), exchange)


def _authority_stub():
    class _A:
        operation = "kubernetes.pods.list"
        idempotency_key = None
    return _A()


class TestConnectorAdapterNormalization:
    def test_success_lifts_evidence_through_the_real_adapter(self):
        outcome = _AdapterHarness().normalise(
            body=_pod_list_body(items=[_crashloop_pod(), _running_pod()]))
        assert outcome.succeeded
        assert outcome.evidence["resourceVersion"] == "424242"
        assert outcome.evidence["podCount"] == 2
        assert outcome.evidence["crashLoopCount"] == 1

    def test_missing_resource_version_is_malformed_not_fabricated(self):
        outcome = _AdapterHarness().normalise(body=_pod_list_body(rv=None))
        assert not outcome.succeeded
        assert outcome.ambiguous
        assert outcome.provider_failure is ProviderFailure.MALFORMED_RESPONSE
        assert not outcome.evidence

    def test_ununderstood_envelope_is_refused(self):
        outcome = _AdapterHarness().normalise(body=b'"just-a-string"')
        assert not outcome.succeeded
        assert outcome.provider_failure is ProviderFailure.MALFORMED_RESPONSE

    def test_provider_status_classification_stays_provider_side(self):
        # Part L: a cluster 401/403/404 is a PROVIDER failure with the cluster's
        # own bounded message — never a CortexPrime authorization outcome and
        # never a success.
        harness = _AdapterHarness()
        status_body = {"kind": "Status", "apiVersion": "v1", "status": "Failure",
                       "message": 'pods is forbidden: User "system:serviceaccount:x:y" '
                                  'cannot list resource "pods"', "code": 403}
        for status, expected in ((401, ProviderFailure.AUTHENTICATION_FAILURE),
                                 (403, ProviderFailure.AUTHORIZATION_FAILURE),
                                 (404, ProviderFailure.NOT_FOUND)):
            outcome = harness.normalise(status=status, body={**status_body, "code": status})
            assert not outcome.succeeded
            assert outcome.provider_failure is expected
            assert "forbidden" in (outcome.error_message or "")

    def test_undeclared_2xx_is_not_a_success(self):
        outcome = _AdapterHarness().normalise(status=201, body=_pod_list_body())
        assert not outcome.succeeded


class TestRealExposure:
    def test_the_real_exposure_grows_only_deliberately(self):
        # Each exposure was added for a named reason, and the set is pinned so a
        # sixth does not appear by habit: 9.2 the list, 9.3 the watch that
        # continues it, 9.5 the two reads a CrashLoopBackOff differential turns
        # on (how the container died; what revision is deployed). The other two
        # declared operations stay contract-only.
        # Phase 11.3 (ADR-123) added the three reads an evidence-first
        # investigation discriminates on beyond state and revision: what the
        # container SAID (logs, from the kubelet), what the control plane
        # RECORDED (events), and what CHANGED (the ReplicaSet lineage). The
        # deployments list stays contract-only: nothing discriminates on it.
        catalog = kubernetes_real_read_catalog()
        assert set(catalog.operations) == set(KUBERNETES_REAL_READ_OPERATIONS)
        # Phase 11.1-K (ADR-125) added the eighth, and only the eighth: the
        # connection's own permission check, which connector health asks the
        # cluster so a missing RBAC rule is named instead of guessed. It reads
        # nothing about workloads and changes nothing.
        assert set(KUBERNETES_REAL_READ_OPERATIONS) == {
            "kubernetes.pods.list", "kubernetes.pods.watch",
            "kubernetes.pod.get", "kubernetes.deployment.get",
            "kubernetes.pod.logs", "kubernetes.events.list",
            "kubernetes.replicasets.list", "kubernetes.access.review"}
        assert set(kubernetes_read_catalog().operations) - set(
            KUBERNETES_REAL_READ_OPERATIONS) == {"kubernetes.deployments.list"}

    def test_real_specs_are_the_declared_contract(self):
        full, real = kubernetes_read_catalog(), kubernetes_real_read_catalog()
        for op in real.operations:
            assert real.require(op).digest == full.require(op).digest

    def test_channel_refuses_plaintext(self):
        from backend.contracts.execution import ExecutionEnvironment
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
            build_kubernetes_channel)
        with pytest.raises(Exception):
            build_kubernetes_channel(
                broker=None, policy=None,
                environment=ExecutionEnvironment.DEVELOPMENT,
                base_url="http://127.0.0.1:8080")

    def test_factory_contributes_nothing_without_configuration(self, monkeypatch):
        from backend.api.kubernetes_provider_factory import kubernetes_real_extension
        from backend.contracts.execution import ExecutionEnvironment
        for var in ("CORTEX_KUBERNETES_URL", "CORTEX_KUBERNETES_TOKEN",
                    "CORTEX_KUBERNETES_SCRIPTED"):
            monkeypatch.delenv(var, raising=False)
        assert kubernetes_real_extension(ExecutionEnvironment.DEVELOPMENT) is None
        monkeypatch.setenv("CORTEX_KUBERNETES_URL", "https://127.0.0.1:6443")
        assert kubernetes_real_extension(ExecutionEnvironment.DEVELOPMENT) is None

    def test_factory_refuses_the_dual_path(self, monkeypatch):
        # Part U: scripted and real must never compose together — a dual path
        # is a fallback.
        from backend.api.kubernetes_provider_factory import kubernetes_real_extension
        from backend.contracts.execution import ExecutionEnvironment
        monkeypatch.setenv("CORTEX_KUBERNETES_URL", "https://127.0.0.1:6443")
        monkeypatch.setenv("CORTEX_KUBERNETES_TOKEN", "sa-token")
        monkeypatch.setenv("CORTEX_KUBERNETES_SCRIPTED", "1")
        with pytest.raises(RuntimeError):
            kubernetes_real_extension(ExecutionEnvironment.DEVELOPMENT)


class TestProviderEvidenceSurfacing:
    """Part H: the one-key lift onto the published ExecutionResult."""

    def _project(self, detail):
        from backend.contexts.execution.application.worker_runtime import WorkerRuntime
        from backend.contexts.execution.domain.worker_contract import (
            WorkerExecutionRequest, WorkerExecutionResult, WorkerOutcome)
        now = datetime.now(timezone.utc)
        request = _RequestStub()
        result = WorkerExecutionResult(
            outcome=WorkerOutcome.SUCCESS, binding_id="b", attempt_id="a",
            started_at=now, completed_at=now, detail=detail, result_digest="d")
        return WorkerRuntime.to_execution_result(request, result)

    def test_provider_evidence_survives_to_the_aggregate(self):
        projected = self._project(
            {"provider_evidence": {"resourceVersion": "424242", "podCount": 2},
             "provider_status": 200})
        assert projected.detail["provider_evidence"] == {
            "resourceVersion": "424242", "podCount": 2}
        # Two keys, deliberately. ``provider_status`` joined it in 9.3 (ADR-083):
        # a failed provider answer carries no evidence, so without the status the
        # only thing separating an expired watch position (410) from a refused
        # one (403) would be substring-matching a message. The rest of the
        # adapter detail still stays on the attempt record.
        assert projected.detail["provider_status"] == 200
        assert "provider_delivery" not in projected.detail

    def test_absent_evidence_stays_absent(self):
        projected = self._project({"provider_status": 200})
        assert "provider_evidence" not in projected.detail

    def test_a_non_integer_status_is_not_lifted(self):
        projected = self._project({"provider_status": "200"})
        assert "provider_status" not in projected.detail

    def test_non_mapping_evidence_is_not_lifted(self):
        projected = self._project({"provider_evidence": "not-a-dict"})
        assert "provider_evidence" not in projected.detail


class _RequestStub:
    execution_key = "k"
    node_id = "n"
