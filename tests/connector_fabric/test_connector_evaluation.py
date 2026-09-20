"""Phase 11.1-K: the reusable connector evaluation suite, applied to Kubernetes
and proven sensitive to each rule it enforces."""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.api.connector_evaluation import evaluate_connector


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


def _manifest():
    from backend.api.kubernetes_connector import kubernetes_manifest

    return kubernetes_manifest()


def _with(capability_id, **changes):
    manifest = _manifest()
    caps = tuple(replace(c, **changes) if c.capability_id == capability_id else c for c in manifest.capabilities)
    return replace(manifest, capabilities=caps)


def test_kubernetes_passes_the_suite():
    report = evaluate_connector(_manifest(), _catalogs())
    assert report.passed, report.to_dict()
    assert report.capabilities == 10


@pytest.mark.parametrize("capability,changes,rule", [
    ("platform.kubernetes.pods.list", {"description": "Lists pods."}, "EVAL-DESCRIBED"),
    ("platform.kubernetes.pods.list", {"required_permissions": ()}, "EVAL-PERMISSION"),
    ("platform.kubernetes.pods.list", {"target_parameter": "cluster"}, "EVAL-TARGET"),
    ("platform.kubernetes.deployment.rollback", {"provider": "kubernetes"}, "EVAL-WRITE-CONTAINED"),
])
def test_each_rule_catches_its_violation(capability, changes, rule):
    report = evaluate_connector(_with(capability, **changes), _catalogs())
    assert rule in {f.rule for f in report.findings}, report.to_dict()


def _duck(manifest, capability_id, **changes):
    """A manifest-shaped object the pure contracts would refuse to construct --
    the suite must still catch it (a connector could ship its own manifest type)."""
    from types import SimpleNamespace

    def copy(c):
        fields = {k: getattr(c, k) for k in ("capability_id", "version", "operation", "provider", "description",
                                             "category", "profile", "required_permissions", "target_parameter",
                                             "mutates", "retry")}
        if c.capability_id == capability_id:
            fields.update(changes)
        return SimpleNamespace(**fields)

    return SimpleNamespace(connector_id=manifest.connector_id,
                           capabilities=tuple(copy(c) for c in manifest.capabilities))


def test_the_pure_contracts_already_refuse_duplicates_and_mismatched_profiles():
    from backend.contracts.errors import ContractViolation

    manifest = _manifest()
    with pytest.raises(ContractViolation):
        replace(manifest, capabilities=manifest.capabilities + (manifest.capabilities[0],))
    with pytest.raises(ContractViolation):
        _with("platform.kubernetes.pods.list", operation="kubernetes.pods.exec")


def test_a_duplicate_capability_is_caught():
    manifest = _manifest()
    duck = _duck(manifest, "")
    duck.capabilities = duck.capabilities + (duck.capabilities[0],)
    assert "EVAL-UNIQUE" in {f.rule for f in evaluate_connector(duck, _catalogs()).findings}


def test_a_forbidden_or_uncomposed_operation_is_caught():
    report = evaluate_connector(_duck(_manifest(), "platform.kubernetes.pods.list", operation="kubernetes.pods.exec"),
                                _catalogs())
    rules = {f.rule for f in report.findings}
    assert {"EVAL-FORBIDDEN", "EVAL-COMPOSED"} <= rules


def test_a_retried_write_is_caught():
    from backend.contracts.connector_manifest import RetryClass

    report = evaluate_connector(_duck(_manifest(), "platform.kubernetes.deployment.rollback", retry=RetryClass.SAFE),
                                _catalogs())
    assert "EVAL-WRITE-RETRY" in {f.rule for f in report.findings}


def test_a_too_small_response_budget_is_caught():
    catalogs = _catalogs()
    from backend.contexts.execution.domain.provider_operation import OperationCatalog

    reads = catalogs["kubernetes"]
    shrunk = [replace(reads.get(op), max_response_bytes=64 * 1024) if op == "kubernetes.access.review"
              else reads.get(op) for op in reads.operations]
    catalogs["kubernetes"] = OperationCatalog("kubernetes", shrunk)
    report = evaluate_connector(_manifest(), catalogs)
    assert [f.capability for f in report.findings if f.rule == "EVAL-BUDGET"] == ["platform.kubernetes.access.review"]
