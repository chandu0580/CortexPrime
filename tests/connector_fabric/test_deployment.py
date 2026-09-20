"""Phase 11.1-K -- the deployable: chart/worker agreement, env validation, DSN.

Deterministic. The real install is proven by
scripts/phase111k_kubernetes_connector_harness.py.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VALUES = (REPO / "helm" / "cortexprime-governed" / "values.yaml").read_text(encoding="utf-8")


def _digest_in_values(worker: str) -> str:
    block = VALUES.split(f"\n  {worker}:\n", 1)[1]
    return re.search(r"digest:\s*([0-9a-f]{64})", block).group(1)


@pytest.mark.parametrize("worker,source", [
    ("rollback", "workers/contained_k8s_rollback/worker.py"),
    ("restart", "workers/contained_k8s_restart/worker.py"),
])
def test_chart_pins_the_shipped_worker_code(worker, source):
    """The digest the platform checks on every execution is the shipped code's."""
    shipped = hashlib.sha256((REPO / source).read_bytes()).hexdigest()
    assert _digest_in_values(worker) == shipped


class TestDsn:
    def test_production_sslmode_reaches_asyncpg_as_ssl(self, monkeypatch):
        from backend.database.engine import _build_dsn, _sync_dsn

        monkeypatch.setenv("POSTGRES_URL", "postgresql://u:p@db:5432/x?sslmode=require")
        assert _build_dsn() == "postgresql+asyncpg://u:p@db:5432/x?ssl=require"
        assert _sync_dsn() == "postgresql://u:p@db:5432/x?sslmode=require"

    def test_sslmode_after_other_parameters(self, monkeypatch):
        from backend.database.engine import _build_dsn, _sync_dsn

        monkeypatch.setenv("POSTGRES_URL", "postgresql://u:p@db/x?application_name=a&sslmode=verify-full")
        assert _build_dsn().endswith("?application_name=a&ssl=verify-full")
        assert _sync_dsn().endswith("?application_name=a&sslmode=verify-full")

    def test_url_without_tls_parameters_is_unchanged(self, monkeypatch):
        from backend.database.engine import _build_dsn, _sync_dsn

        monkeypatch.setenv("POSTGRES_URL", "postgresql://u:p@db/x")
        assert _build_dsn() == "postgresql+asyncpg://u:p@db/x"
        assert _sync_dsn() == "postgresql://u:p@db/x"


def _env(**overrides):
    env = {"CORTEX_DURABLE_URL": "postgresql://u:p@db/x?sslmode=require", "CORTEX_DURABLE_ENV": "production",
           "JWT_SECRET_KEY": "k" * 48, "CORTEX_KUBERNETES_TENANT": "tenant-a",
           "CORTEX_KUBERNETES_NAMESPACE": "shop", "CORTEX_VAULT_ADDR": "https://vault:8200",
           "CORTEX_VAULT_AUTH_ROLE": "cortexprime"}
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


class TestGovernedEnvironment:
    def test_coherent_configuration_has_no_problems(self):
        from backend.api.governed_plane import validate_governed_environment

        assert validate_governed_environment(_env()) == []

    @pytest.mark.parametrize("overrides,named", [
        ({"CORTEX_DURABLE_URL": None}, "CORTEX_DURABLE_URL"),
        ({"JWT_SECRET_KEY": "short"}, "JWT_SECRET_KEY"),
        ({"CORTEX_KUBERNETES_NAMESPACE": None}, "CORTEX_KUBERNETES_NAMESPACE"),
        ({"CORTEX_VAULT_ADDR": None}, "CORTEX_VAULT_ADDR"),
        ({"CORTEX_VAULT_AUTH_ROLE": None}, "CORTEX_VAULT_AUTH_ROLE"),
        ({"CORTEX_KUBERNETES_CREDENTIALS": "static"}, "static is refused in production"),
        ({"CORTEX_ROLLBACK_WORKER_URL": "https://w"}, "CORTEX_ROLLBACK_IMPL_DIGEST"),
        ({"CORTEX_SIGNAL_NAMESPACE": "other"}, "CORTEX_SIGNAL_NAMESPACE"),
        ({"CORTEX_VAULT_CA_BUNDLE": "/nonexistent/ca.crt"}, "CORTEX_VAULT_CA_BUNDLE"),
        ({"CORTEX_DURABLE_ENV": "prod"}, "CORTEX_DURABLE_ENV"),
    ])
    def test_each_problem_names_the_variable_to_fix(self, overrides, named):
        from backend.api.governed_plane import validate_governed_environment

        problems = validate_governed_environment(_env(**overrides))
        assert problems and any(named in p for p in problems), problems

    def test_static_credentials_allowed_outside_production(self):
        from backend.api.governed_plane import validate_governed_environment

        assert validate_governed_environment(_env(CORTEX_DURABLE_ENV="development",
                                                  CORTEX_KUBERNETES_CREDENTIALS="static")) == []

    def test_connection_defaults_fill_only_what_is_unset(self):
        from backend.api.governed_plane import apply_connection_defaults

        env = _env(CORTEX_REMEDIATION_ENVIRONMENT="staging")
        applied = apply_connection_defaults(env)
        assert env["CORTEX_SIGNAL_TENANT_ID"] == "tenant-a"
        assert env["CORTEX_SIGNAL_NAMESPACE"] == "shop"
        assert env["CORTEX_REMEDIATION_ENVIRONMENT"] == "staging"      # operator's explicit value kept
        assert "CORTEX_REMEDIATION_ENVIRONMENT" not in applied


class TestImageAndChartHygiene:
    def test_image_build_context_excludes_secrets_and_state(self):
        ignore = (REPO / "deploy" / "governed-runtime" / "Dockerfile.dockerignore").read_text(encoding="utf-8")
        for pattern in (".env", "cortex_memory", "*.sqlite"):
            assert pattern in ignore

    def test_image_has_the_migration_dependencies(self):
        requirements = (REPO / "deploy" / "governed-runtime" / "requirements.txt").read_text(encoding="utf-8")
        for package in ("alembic", "asyncpg", "psycopg2-binary", "pgvector"):
            assert package in requirements

    def test_chart_never_grants_cluster_wide_rights(self):
        templates = (REPO / "helm" / "cortexprime-governed" / "templates")
        text = "\n".join(p.read_text(encoding="utf-8") for p in templates.glob("*.yaml"))
        assert "kind: ClusterRole" not in text
        assert "cluster-admin" not in text
        assert 'verbs: ["*"]' not in text and "resources: [\"*\"]" not in text

    def test_production_is_the_default_environment(self):
        assert re.search(r"^environment:\s*production\s*$", VALUES, re.M)


class TestGovernedReaderEnvironment:
    """Phase 11.1-K: a reader asks for its DEPLOYMENT's environment.

    It defaulted to DEVELOPMENT, so in a production deployment every read by
    connector health, the signal worker and the investigator was refused
    ``environment_not_permitted`` (found by the installed runtime).
    """

    def _read(self, runtime_environment, monkeypatch, durable_env=None):
        from types import SimpleNamespace

        from backend.api.capability_execution_composition import GovernedCapabilityReader
        from backend.contexts.connectivity.domain.identifiers import CapabilityRef
        from backend.contracts.identity import PrincipalKind, PrincipalRef

        if durable_env is None:
            monkeypatch.delenv("CORTEX_DURABLE_ENV", raising=False)
        else:
            monkeypatch.setenv("CORTEX_DURABLE_ENV", durable_env)
        asked = {}

        class Authorization:
            def authorize(self, context, request):
                asked["environment"] = request.environment
                return SimpleNamespace(allowed=False, reason_codes=("stop",), effect=None)

        definition = SimpleNamespace(
            reference=CapabilityRef.parse("platform.kubernetes.pods.list@1"), digest="d" * 64,
            contract=SimpleNamespace(side_effect_class=SimpleNamespace(mutates=False, value="read")))
        runtime = SimpleNamespace(environment=runtime_environment, authorization=Authorization())
        reader = GovernedCapabilityReader(runtime=runtime, capability_definitions={"k.op": definition},
                                          principal=PrincipalRef(principal_id="p", kind=PrincipalKind.PLATFORM))
        outcome = reader.read(SimpleNamespace(tenant_id="tenant-a"), operation="k.op", payload={})
        assert not outcome.succeeded
        return asked["environment"].value

    def test_production_runtime_reads_as_production(self, monkeypatch):
        from backend.contracts.execution import ExecutionEnvironment

        assert self._read(ExecutionEnvironment.PRODUCTION, monkeypatch) == "production"

    def test_without_a_runtime_environment_the_durable_env_decides(self, monkeypatch):
        assert self._read(None, monkeypatch, durable_env="staging") == "staging"

    def test_development_remains_the_default_when_nothing_is_declared(self, monkeypatch):
        assert self._read(None, monkeypatch) == "development"


def test_every_shipped_operation_budget_admits_a_transport_policy():
    """A per-operation response budget below the transport frame budget makes the
    connection policy refuse to construct -- every read of that operation fails
    (the access review shipped at 64 KiB; found by the installed runtime)."""
    from backend.api.kubernetes_connector import kubernetes_manifest
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        kubernetes_real_read_catalog,
    )
    from backend.platform.transport.policy import ResourceBudget

    frame = ResourceBudget().max_frame_bytes
    catalog = kubernetes_real_read_catalog()
    for capability in kubernetes_manifest().capabilities:
        if capability.provider != "kubernetes":
            continue
        spec = catalog.get(capability.operation)
        assert spec.max_response_bytes >= frame, capability.operation


def test_a_half_configured_model_is_refused_at_start_naming_what_is_missing():
    from backend.api.governed_plane import validate_governed_environment

    problems = validate_governed_environment(_env(CORTEX_REMEDIATION_MODEL_PROVIDER="openai-compatible",
                                                  LLM_API_KEY="k", LLM_BASE_URL="https://m"))
    assert any("LLM_MODEL" in p for p in problems), problems
    assert validate_governed_environment(_env(CORTEX_REMEDIATION_MODEL_PROVIDER="openai-compatible",
                                              LLM_API_KEY="k", LLM_BASE_URL="https://m", LLM_MODEL="m")) == []


def test_chart_gives_the_model_adapter_its_model_name():
    runtime = (REPO / "helm" / "cortexprime-governed" / "templates" / "runtime.yaml").read_text(encoding="utf-8")
    assert "LLM_MODEL: {{ .Values.model.name" in runtime


def test_an_incoherent_rate_limit_is_reported_at_start_not_as_a_crash_loop():
    """Phase 11.1-K: a per-capability budget above the tenant budget is refused
    by the policy -- deep inside composition, so the runtime crash-looped with a
    traceback instead of naming the variables."""
    from backend.api.governed_plane import validate_governed_environment

    problems = validate_governed_environment(_env(CORTEX_RATE_LIMIT_TENANT_PER_MINUTE="3"))
    assert any("CORTEX_RATE_LIMIT_" in p for p in problems), problems
    assert validate_governed_environment(_env(CORTEX_RATE_LIMIT_TENANT_PER_MINUTE="3",
                                              CORTEX_RATE_LIMIT_CAPABILITY_PER_MINUTE="2")) == []


def test_the_chart_refuses_workers_without_their_egress_endpoint():
    """A contained worker's egress NetworkPolicy names the API server endpoint.
    The chart discovers it, but a lookup that returns nothing (dry run,
    restricted RBAC) silently dropped the policy and deployed a worker that
    could reach anything; it now fails closed (Phase 11.1-K)."""
    workers = (REPO / "helm" / "cortexprime-governed" / "templates" / "workers.yaml").read_text(encoding="utf-8")
    assert "fail \"workers.apiServerEndpoint is required" in workers
    # and the policy is no longer conditional on the discovery succeeding
    assert "{{- if $endpoint }}" not in workers
