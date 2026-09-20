"""Phase 11.1-K: the reusable connector contract, proven on the Kubernetes connector.

Deterministic: manifest completeness against the REAL catalogs, boot-time
commissioning against a fake registry that reproduces the durable registry's
idempotency rule (identical contract accepted, different contract refused),
the connection scope at the gateway's input stage, schema derivation, and the
health contract's state rules including the Kubernetes probe.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.api.connector_commissioning import commission_connector
from backend.api.connector_health import (
    ConnectorHealth,
    ConnectorHealthMonitor,
    ConnectorHealthState as S,
    HealthCheck,
)
from backend.api.connector_schema import input_schema_for, schema_ref
from backend.api.connector_scope import ConnectionScope, ConnectionScopes, ConnectionScopeValidator
from backend.api.kubernetes_connector import (
    KubernetesConnection,
    kubernetes_manifest,
    permission_review,
)
from backend.contracts.connector_manifest import RetryClass
from backend.contracts.errors import ContractViolation


def _catalogs():
    from backend.api.capability_execution_composition import (
        CONTAINED_KUBERNETES_PROVIDER_ID,
        CONTAINED_ROLLBACK_PROVIDER_ID,
        contained_rollback_worker_catalog,
        contained_worker_catalog,
    )
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_real_read_catalog,
    )

    return {"kubernetes": kubernetes_real_read_catalog(),
            CONTAINED_ROLLBACK_PROVIDER_ID: contained_rollback_worker_catalog(),
            CONTAINED_KUBERNETES_PROVIDER_ID: contained_worker_catalog()}


# -- the manifest ----------------------------------------------------------------

class TestKubernetesManifest:
    def test_every_shipped_capability_exists_in_the_real_catalog_of_its_provider(self):
        catalogs = _catalogs()
        for capability in kubernetes_manifest().capabilities:
            catalog = catalogs[capability.provider]
            assert catalog.get(capability.operation) is not None, capability.capability_id

    def test_exactly_two_writes_and_they_are_never_retried(self):
        writes = [c for c in kubernetes_manifest().capabilities if c.mutates]
        assert sorted(c.operation for c in writes) == [
            "kubernetes.deployment.rollback", "kubernetes.workload.rollout_restart"]
        assert all(c.retry is RetryClass.NEVER for c in writes)
        assert all(c.retry is RetryClass.SAFE for c in kubernetes_manifest().capabilities
                   if not c.mutates)

    def test_no_arbitrary_api_no_shell_no_delete(self):
        operations = {c.operation for c in kubernetes_manifest().capabilities}
        assert not any(word in op for op in operations
                       for word in ("delete", "exec", "shell", "patch_arbitrary", "apply", "scale"))

    def test_every_permission_can_be_asked_of_the_api_server(self):
        for permission in kubernetes_manifest().required_permissions():
            review = permission_review(permission, "ns-a")
            assert review["namespace"] == "ns-a" and review["verb"] and review["resource"]

    def test_writes_declare_independent_verification_and_rollback_its_compensation(self):
        manifest = kubernetes_manifest()
        rollback = manifest.capability("platform.kubernetes.deployment.rollback")
        assert rollback.profile.verification_requirement.value == "independent_readback"
        assert rollback.profile.compensation == "platform.kubernetes.deployment.rollback"
        restart = manifest.capability("platform.kubernetes.workload.rollout_restart")
        assert restart.profile.compensation is None

    def test_every_capability_has_a_description_an_agent_can_choose_by(self):
        for capability in kubernetes_manifest().capabilities:
            assert len(capability.description) > 60, capability.capability_id

    def test_a_capability_without_a_description_does_not_construct(self):
        from backend.contracts.connector_manifest import CapabilityManifest

        profile = kubernetes_manifest().capabilities[0].profile
        with pytest.raises(ContractViolation):
            CapabilityManifest(capability_id="platform.kubernetes.pods.list", version=1,
                               operation="kubernetes.pods.list", provider="kubernetes",
                               description=" ", category="observation", profile=profile)


class TestSchemas:
    def test_the_input_schema_is_derived_from_the_validated_spec(self):
        spec = _catalogs()["kubernetes"].require("kubernetes.pod.logs")
        schema = input_schema_for(spec)
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == {"namespace", "name"}
        assert schema["properties"]["tailLines"]["maximum"] == 500

    def test_the_access_review_only_asks_about_declared_verbs(self):
        spec = _catalogs()["kubernetes"].require("kubernetes.access.review")
        schema = input_schema_for(spec)
        assert set(schema["properties"]["verb"]["enum"]) == {"get", "list", "watch", "patch"}

    def test_a_schema_reference_changes_when_the_schema_changes(self):
        a = schema_ref("x", {"type": "object"})
        b = schema_ref("x", {"type": "object", "additionalProperties": False})
        assert a["digest"] != b["digest"] and a["digest"] == schema_ref("x", {"type": "object"})["digest"]


# -- boot-time commissioning ---------------------------------------------------

class FakeRegistry:
    """Reproduces the durable registry's rule: an identical contract for an
    existing version is accepted; a different one is refused."""

    def __init__(self, preexisting=None):
        self.stored = dict(preexisting or {})
        self.state = {}

    def get(self, ctx, command):
        key = command.capability_id
        if key not in self.stored:
            raise LookupError(key)
        status, trust = self.state.get(key, ("registered", "unverified"))
        return SimpleNamespace(status=SimpleNamespace(value=status), trust=SimpleNamespace(value=trust))

    def register(self, ctx, command):
        key = command.capability_id
        fingerprint = (command.provider, command.input_schema["digest"], command.required_permissions,
                       command.timeout_seconds, command.compensation_capability)
        if key in self.stored and self.stored[key] != fingerprint:
            raise ValueError("a different contract is registered for this version")
        self.stored[key] = fingerprint

    def validate(self, ctx, command):
        self.state[command.capability_id] = ("validated", "unverified")

    def enable(self, ctx, command):
        self.state[command.capability_id] = ("enabled", "unverified")

    def set_trust(self, ctx, command):
        status, _ = self.state[command.capability_id]
        self.state[command.capability_id] = (status, command.trust)


class FakeDirectory:
    def __init__(self, providers):
        self.entries = [SimpleNamespace(worker_id=f"{p}-worker",
                                        implementation=SimpleNamespace(supported_providers=frozenset({p})))
                        for p in providers]
        self.admitted = []

    def all_entries(self, ctx, *, tenant_id):
        return tuple(self.entries)

    def validate(self, ctx, **kw):
        pass

    def enable(self, ctx, **kw):
        pass

    def set_trust(self, ctx, **kw):
        pass

    def set_availability(self, ctx, worker_id, tenant_id, availability):
        self.admitted.append(worker_id)

    def entry(self, ctx, *, worker_id, tenant_id):
        return SimpleNamespace(accepts_work=worker_id in self.admitted)


def _runtime(catalogs, registry=None):
    return SimpleNamespace(
        capabilities=registry or FakeRegistry(),
        connectivity=SimpleNamespace(catalogs=catalogs, directory=FakeDirectory(catalogs)))


class TestCommissioning:
    def test_every_composed_capability_is_registered_enabled_and_trusted(self):
        runtime = _runtime(_catalogs())
        report = commission_connector(runtime, kubernetes_manifest(), environment="production")
        assert report.ok and len(report.commissioned) == 10
        assert all(runtime.capabilities.state[c] == ("enabled", "trusted") for c in report.commissioned)
        assert sorted(report.workers_admitted) == sorted(f"{p}-worker" for p in _catalogs())

    def test_it_is_idempotent_on_every_boot(self):
        runtime = _runtime(_catalogs())
        commission_connector(runtime, kubernetes_manifest(), environment="production")
        again = commission_connector(runtime, kubernetes_manifest(), environment="production")
        assert again.ok and again.commissioned == [] and len(again.already_current) == 10

    def test_a_capability_whose_provider_is_not_composed_is_skipped_not_registered(self):
        catalogs = {"kubernetes": _catalogs()["kubernetes"]}
        runtime = _runtime(catalogs)
        report = commission_connector(runtime, kubernetes_manifest(), environment="production")
        assert "platform.kubernetes.deployment.rollback" in report.skipped
        assert "platform.kubernetes.deployment.rollback" not in runtime.capabilities.stored
        assert len(report.commissioned) == 8

    def test_a_drifted_contract_is_a_conflict_left_as_stored(self):
        registry = FakeRegistry({"platform.kubernetes.pods.list": ("kubernetes", "old", (), 1, None)})
        report = commission_connector(_runtime(_catalogs(), registry), kubernetes_manifest(),
                                      environment="production")
        assert "platform.kubernetes.pods.list" in report.conflicts
        assert registry.stored["platform.kubernetes.pods.list"][1] == "old"
        assert not report.ok

    def test_the_registered_contract_carries_schema_permissions_and_timeout(self):
        seen = {}

        class Capture(FakeRegistry):
            def register(self, ctx, command):
                seen[command.capability_id] = command
                super().register(ctx, command)

        commission_connector(_runtime(_catalogs(), Capture()), kubernetes_manifest(),
                             environment="production")
        rollback = seen["platform.kubernetes.deployment.rollback"]
        assert rollback.required_permissions and rollback.input_schema["digest"]
        assert rollback.retryable is False and rollback.idempotency_supported is False
        assert rollback.supported_environments == ("production",)
        assert seen["platform.kubernetes.pods.list"].retryable is True


# -- the connection scope (tenancy at the gateway input stage) ----------------------

class _Inner:
    def validate(self, binding, payload):
        return ()


def _binding(tenant="t-a", provider="kubernetes"):
    return SimpleNamespace(tenant_id=tenant, provider=provider)


class TestConnectionScope:
    def _validator(self):
        scopes = ConnectionScopes([ConnectionScope(
            tenant_id="t-a", providers=frozenset({"kubernetes", "kubernetes-contained-rollback"}),
            targets=frozenset({"ns-a"}))])
        return ConnectionScopeValidator(_Inner(), scopes)

    def test_a_target_inside_the_connection_passes(self):
        assert self._validator().validate(_binding(), {"namespace": "ns-a"}) == ()

    def test_another_namespace_is_refused(self):
        problems = self._validator().validate(_binding(), {"namespace": "ns-b"})
        assert problems and "outside this tenant" in problems[0]

    def test_another_tenant_has_no_connection(self):
        problems = self._validator().validate(_binding(tenant="t-b"), {"namespace": "ns-a"})
        assert problems and "no connection" in problems[0]

    def test_the_write_worker_is_scoped_too(self):
        problems = self._validator().validate(
            _binding(provider="kubernetes-contained-rollback"), {"namespace": "kube-system"})
        assert problems

    def test_an_unscoped_provider_is_left_to_its_own_rules(self):
        assert self._validator().validate(_binding(provider="prometheus"), {}) == ()

    def test_inner_problems_are_kept(self):
        class Inner:
            def validate(self, binding, payload):
                return ("limit must be <= 500",)

        scopes = ConnectionScopes([ConnectionScope("t-a", frozenset({"kubernetes"}), frozenset({"ns-a"}))])
        problems = ConnectionScopeValidator(Inner(), scopes).validate(_binding(), {"namespace": "ns-b"})
        assert len(problems) == 2

    def test_the_gateway_refuses_a_cross_namespace_target_before_a_credential(self):
        from backend.contexts.execution.domain.invocation import InvocationRefusal, InvocationRefused
        from tests.contexts.execution.test_invocation_gateway_matrix import Fixture

        fx = Fixture(payload={"namespace": "other-ns", "name": "x"})
        inner = fx.gateway._input_validator

        class PassThrough:
            def validate(self, binding, payload):
                return ()

        fx.gateway._input_validator = ConnectionScopeValidator(
            PassThrough() if inner is None else inner,
            ConnectionScopes([ConnectionScope(fx.binding.tenant_id, frozenset({fx.binding.provider}),
                                              frozenset({"my-ns"}))]))
        with pytest.raises(InvocationRefused) as refused:
            fx.gateway.admit(fx.context, fx.request, fx.binding)
        assert refused.value.refusal in (InvocationRefusal.INPUT_INVALID,)
        assert fx.credentials.acquisitions == 0


class TestConnection:
    def test_plaintext_api_is_refused(self):
        with pytest.raises(ContractViolation):
            KubernetesConnection(tenant_id="t", namespace="n", api_url="http://api:6443")

    def test_from_env_needs_both_tenant_and_namespace(self):
        assert KubernetesConnection.from_env({"CORTEX_KUBERNETES_TENANT": "t"}) is None
        connection = KubernetesConnection.from_env({"CORTEX_KUBERNETES_TENANT": "t",
                                                    "CORTEX_KUBERNETES_NAMESPACE": "n"})
        assert connection.api_url == "https://kubernetes.default.svc"


# -- health ------------------------------------------------------------------------

class TestHealthContract:
    def test_all_checks_pass_is_connected(self):
        health = ConnectorHealth.from_checks("k", "t", [HealthCheck("api", True, S.UNAVAILABLE)],
                                             available=("a",))
        assert health.state is S.CONNECTED

    def test_the_worst_failed_check_wins(self):
        health = ConnectorHealth.from_checks("k", "t", [
            HealthCheck("worker", False, S.DEGRADED, "down"),
            HealthCheck("api", False, S.AUTHENTICATION_REQUIRED, "401")])
        assert health.state is S.AUTHENTICATION_REQUIRED

    def test_unavailable_capabilities_degrade_an_otherwise_healthy_connection(self):
        health = ConnectorHealth.from_checks("k", "t", [HealthCheck("api", True, S.UNAVAILABLE)],
                                             unavailable={"x": "missing get pods"})
        assert health.state is S.DEGRADED

    def test_a_probe_that_raises_is_misconfigured_not_healthy(self):
        monitor = ConnectorHealthMonitor()

        def boom():
            raise RuntimeError("secret-bearing message")

        monitor.register("k", boom)
        health = monitor.check("k")
        assert health.state is S.MISCONFIGURED
        assert "secret-bearing" not in str(health.to_dict())

    def test_an_unregistered_connector_is_disabled(self):
        assert ConnectorHealthMonitor().check("nothing").state is S.DISABLED


class TestKubernetesProbe:
    """The probe against a fake runtime; the governed reader is replaced by one
    returning scripted access-review outcomes (the real path is proven live)."""

    def _probe(self, monkeypatch, outcomes, *, report=None, worker_ok=True):
        import backend.api.capability_execution_composition as cec
        import backend.api.kubernetes_connector as k

        class Reader:
            def __init__(self, **kwargs):
                self.calls = 0

            def read(self, ctx, *, operation, payload):
                outcome = outcomes(payload)
                return outcome

        monkeypatch.setattr(cec, "GovernedCapabilityReader", Reader)
        monkeypatch.setattr(k, "_worker_reachable", lambda *a, **kw: (worker_ok, "HTTP 200" if worker_ok else "down"))
        monkeypatch.setenv("CORTEX_ROLLBACK_WORKER_URL", "https://contained-rollback-worker.ns.svc:8080")
        monkeypatch.delenv("CORTEX_RESTART_WORKER_URL", raising=False)
        runtime = SimpleNamespace(
            connector_reports={"kubernetes": report or SimpleNamespace(
                conflicts={}, failed={}, skipped={},
                available=tuple(c.capability_id for c in kubernetes_manifest().capabilities))},
            capabilities=SimpleNamespace(get=lambda ctx, cmd: object()))
        connection = KubernetesConnection(tenant_id="t-a", namespace="ns-a")
        return k.kubernetes_health_probe(runtime, connection, None)()

    @staticmethod
    def _ok(allowed=True):
        return SimpleNamespace(succeeded=True, evidence={"allowed": allowed}, status=201, failure_reason=None)

    def test_every_permission_held_is_connected(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: self._ok())
        assert health.state is S.CONNECTED, health.summary

    def test_one_missing_permission_degrades_and_names_it(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: self._ok(p["resource"] != "events"))
        assert health.state is S.DEGRADED
        assert "platform.kubernetes.events.list" in health.unavailable_capabilities
        assert any("kubernetes:events:list" in c.detail for c in health.checks)

    def test_no_permission_at_all_is_misconfigured(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: self._ok(False))
        assert health.state is S.MISCONFIGURED

    def test_a_rejected_credential_requires_authentication(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: SimpleNamespace(
            succeeded=False, evidence={}, status=401, failure_reason="Unauthorized"))
        assert health.state is S.AUTHENTICATION_REQUIRED

    def test_throttling_is_rate_limited(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: SimpleNamespace(
            succeeded=False, evidence={}, status=None,
            failure_reason="invocation refused at dispatch: rate_limited"))
        assert health.state is S.RATE_LIMITED

    def test_an_unreachable_vault_or_api_is_unavailable(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: SimpleNamespace(
            succeeded=False, evidence={}, status=None, failure_reason="Vault could not be reached (dns)"))
        assert health.state is S.UNAVAILABLE

    def test_a_contract_conflict_is_misconfigured(self, monkeypatch):
        report = SimpleNamespace(conflicts={"platform.kubernetes.pods.list": "drift"}, failed={}, skipped={},
                                 available=())
        health = self._probe(monkeypatch, lambda p: self._ok(), report=report)
        assert health.state is S.MISCONFIGURED

    def test_an_unreachable_worker_degrades_only_its_capability(self, monkeypatch):
        health = self._probe(monkeypatch, lambda p: self._ok(), worker_ok=False)
        assert health.state is S.DEGRADED
        assert "platform.kubernetes.deployment.rollback" in health.unavailable_capabilities
        assert "platform.kubernetes.pods.list" in health.available_capabilities
