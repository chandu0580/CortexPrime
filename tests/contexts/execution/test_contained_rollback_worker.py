"""The CONTAINED rollback worker (ADR-124), exercised as the pure functions it is.

The worker is loaded from its file exactly as the image runs it. Kubernetes is a
fake client that records every call, so each test can assert not only what the
worker answered but that NOTHING was written when it refused -- the property the
real-cluster harness then re-proves against the API server itself.
"""

from __future__ import annotations

import copy
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
UID = "11111111-2222-3333-4444-555555555555"
NS = "cortex-p99b"
NAME = "p114-shop"


@pytest.fixture()
def worker(monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "rollback_worker_under_test", ROOT / "workers" / "contained_k8s_rollback" / "worker.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in (("BIND_TENANT", "tenant-a"),
                        ("BIND_CAPABILITY_ID", "platform.kubernetes.deployment.rollback"),
                        ("BIND_CAPABILITY_VERSION", "1"), ("BIND_PROVIDER", "kubernetes-contained-rollback"),
                        ("BIND_OPERATION", "kubernetes.deployment.rollback"), ("BIND_NAMESPACE", NS),
                        ("IMPLEMENTATION_DIGEST", "impl-digest")):
        monkeypatch.setattr(module, name, value)
    return module


def _template(command: str, *, hash_label: str = "") -> dict:
    labels = {"app": NAME}
    if hash_label:
        labels["pod-template-hash"] = hash_label
    return {"metadata": {"labels": labels, "creationTimestamp": None},
            "spec": {"containers": [{"name": "app", "image": "busybox:1.36", "command": ["sh", "-c", command]}]}}


GOOD = _template("echo good; sleep 3600")
BAD = _template("echo bad; exit 2")


def _deployment(worker, *, template=BAD, generation=4, revision="2", uid=UID, paused=None, history=10):
    spec = {"template": copy.deepcopy(template), "revisionHistoryLimit": history}
    if paused is not None:
        spec["paused"] = paused
    return {"kind": "Deployment",
            "metadata": {"name": NAME, "namespace": NS, "uid": uid, "generation": generation,
                         "resourceVersion": "900", "annotations": {"deployment.kubernetes.io/revision": revision}},
            "spec": spec}


def _rs(name, revision, template, *, owner=UID):
    return {"metadata": {"name": name, "annotations": {"deployment.kubernetes.io/revision": revision},
                         "ownerReferences": [{"kind": "Deployment", "uid": owner, "controller": True,
                                              "name": NAME}]},
            "spec": {"template": copy.deepcopy(template)}}


class FakeClient:
    def __init__(self, worker, *, deployment, replicasets, dry_status=200, write_status=200, write_raises=False):
        self.worker = worker
        self.deployment = deployment
        self.replicasets = replicasets
        self.dry_status = dry_status
        self.write_status = write_status
        self.write_raises = write_raises
        self.calls = []

    def call(self, method, path, *, body=None, content_type=None):
        self.calls.append((method, path, copy.deepcopy(body), content_type))
        if method == "GET" and path.endswith(f"/deployments/{NAME}"):
            return (200, copy.deepcopy(self.deployment)) if self.deployment else (404, {"message": "not found"})
        if method == "GET" and path.endswith("/replicasets"):
            return 200, {"items": copy.deepcopy(self.replicasets)}
        if method == "PATCH":
            dry = "dryRun=All" in path
            if not dry and self.write_raises:
                raise self.worker.Ambiguous("OSError: transport did not complete")
            status = self.dry_status if dry else self.write_status
            if status != 200:
                return status, {"message": "the server rejected our request"}
            patched = copy.deepcopy(self.deployment)
            for op in body:
                if op["op"] == "replace" and op["path"] == "/spec/template":
                    patched["spec"]["template"] = op["value"]
                if op["op"] == "add" and op["path"].startswith("/metadata/annotations/"):
                    patched["metadata"]["annotations"]["cortexprime.io/rolled-back-by-action"] = op["value"]
            if not dry:
                patched["metadata"]["generation"] += 1
            return 200, patched
        raise AssertionError(f"unexpected call {method} {path}")

    @property
    def patches(self):
        return [c for c in self.calls if c[0] == "PATCH"]

    @property
    def writes(self):
        return [c for c in self.patches if "dryRun=All" not in c[1]]


def _envelope(worker, **overrides):
    arguments = {
        "namespace": NS, "name": NAME, "uid": UID, "expected_generation": 4, "expected_revision": 2,
        "expected_template_digest": worker.pod_template_digest(BAD), "target_revision": 1,
        "target_template_digest": worker.pod_template_digest(GOOD), "plan_id": "rplan_abc123",
        "policy_version": "phase114-autonomy/1+phase114-remediation/1+compensable=1",
    }
    arguments.update(overrides.pop("arguments", {}))
    envelope = {
        "tenant": "tenant-a", "execution_id": "exec-1", "capability_id": "platform.kubernetes.deployment.rollback",
        "capability_version": 1, "provider": "kubernetes-contained-rollback",
        "operation": "kubernetes.deployment.rollback", "implementation_digest": "impl-digest",
        "arguments": arguments, "authorization_ref": "authz", "approval_ref": "appr_1",
        "autonomy_decision": "policy-v", "worker_identity": "w", "execution_digest": "sha256:action-digest",
        "idempotency_key": "",
        "authority_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
    }
    envelope.update(overrides)
    return envelope


def _run(worker, client, envelope):
    return worker.handle_envelope(envelope, "Bearer test-token", client_factory=lambda token: client)


def _standard_client(worker, **kwargs):
    return FakeClient(worker, deployment=kwargs.pop("deployment", _deployment(worker)),
                      replicasets=kwargs.pop("replicasets", [_rs("p114-shop-good", "1", GOOD, ),
                                                             _rs("p114-shop-bad", "2", BAD)]), **kwargs)


class TestTheWriteIsExactlyTheApprovedOne:
    def test_a_valid_rollback_reads_dry_runs_then_writes_one_tested_patch(self, worker):
        client = _standard_client(worker)
        answer = _run(worker, client, _envelope(worker))
        assert answer["succeeded"] is True and answer["ambiguous"] is False
        assert [c[0] for c in client.calls] == ["GET", "GET", "PATCH", "PATCH"]
        dry, write = client.patches
        assert "dryRun=All" in dry[1] and "dryRun" not in write[1]
        assert dry[2] == write[2], "the dry run must evaluate exactly the patch that is written"
        ops = write[2]
        assert ops[0] == {"op": "test", "path": "/metadata/uid", "value": UID}
        assert ops[1] == {"op": "test", "path": "/metadata/resourceVersion", "value": "900"}
        assert ops[2]["op"] == "replace" and ops[2]["path"] == "/spec/template"
        assert "pod-template-hash" not in ops[2]["value"]["metadata"]["labels"]
        assert ops[3]["path"] == "/metadata/annotations/cortexprime.io~1rolled-back-by-action"
        assert write[3] == "application/json-patch+json"
        assert answer["evidence"]["templateDigest"] == worker.pod_template_digest(GOOD)
        assert answer["evidence"]["compensationRevision"] == 2

    def test_the_template_written_comes_from_the_deployments_own_replicaset(self, worker):
        foreign = _rs("other-good", "1", GOOD, owner="99999999-2222-3333-4444-555555555555")
        client = _standard_client(worker, replicasets=[foreign, _rs("p114-shop-bad", "2", BAD)])
        answer = _run(worker, client, _envelope(worker))
        assert answer["succeeded"] is False and "target_revision_unavailable" in answer["provider_message"]
        assert client.patches == []

    def test_the_replicaset_hash_label_does_not_change_the_digest(self, worker):
        assert worker.pod_template_digest(_template("x", hash_label="abc")) == worker.pod_template_digest(_template("x"))

    def test_the_worker_and_the_platform_compute_the_same_digest(self, worker):
        from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import pod_template_digest
        for template in (GOOD, BAD, _template("y", hash_label="zz")):
            assert worker.pod_template_digest(template) == pod_template_digest(template)


class TestBindingIsCheckedBeforeTheCredential:
    @pytest.mark.parametrize("overrides, code", [
        ({"surprise": 1}, "envelope_unknown_fields"),
        ({"tenant": "tenant-b"}, "tenant_mismatch"),
        ({"operation": "kubernetes.workload.rollout_restart"}, "operation_mismatch"),
        ({"implementation_digest": "other"}, "implementation_digest_mismatch"),
        ({"arguments": {"namespace": "kube-system"}}, "namespace_out_of_scope"),
        ({"arguments": {"name": "p114-shop,billing-api"}}, "name_not_a_single_target"),
        ({"arguments": {"uid": "not-a-uid"}}, "uid_malformed"),
        ({"arguments": {"target_revision": 2}}, "target_is_current"),
        ({"arguments": {"expected_generation": True}}, "expected_generation_malformed"),
        ({"arguments": {"plan_id": "rm -rf /"}}, "plan_id_malformed"),
        ({"arguments": {"target_template_digest": "zz"}}, "target_template_digest_malformed"),
        ({"approval_ref": ""}, "approval_ref_missing"),
        ({"execution_digest": ""}, "execution_digest_missing"),
        ({"authority_expires_at": ""}, "authority_window_missing"),
        ({"authority_expires_at": "2020-01-01T00:00:00+00:00"}, "authority_expired"),
    ])
    def test_a_bad_envelope_is_refused_and_nothing_is_dialled(self, worker, overrides, code):
        dialled = []
        envelope = _envelope(worker, **overrides)
        answer = worker.handle_envelope(envelope, "Bearer t", client_factory=lambda token: dialled.append(token))
        assert answer["refused"] is True and answer["reason_code"] == code
        assert answer["provider_called"] is False and dialled == []

    def test_an_extra_argument_such_as_a_template_is_refused(self, worker):
        envelope = _envelope(worker)
        envelope["arguments"]["template"] = GOOD
        answer = worker.handle_envelope(envelope, "Bearer t", client_factory=lambda token: None)
        assert answer["reason_code"] == "arguments_unknown_fields"

    def test_no_credential_is_refused_after_binding(self, worker):
        answer = worker.handle_envelope(_envelope(worker), "", client_factory=lambda token: None)
        assert answer["refused"] is True and answer["reason_code"] == "credential_missing"


class TestPreconditionsRefuseDriftWithoutWriting:
    @pytest.mark.parametrize("deployment_kwargs, code", [
        ({"generation": 5}, "generation_changed"),
        ({"revision": "3"}, "revision_changed"),
        ({"uid": "99999999-2222-3333-4444-555555555555"}, "uid_changed"),
        ({"template": _template("echo changed by hand")}, "template_changed"),
        ({"paused": True}, "deployment_paused"),
        ({"history": 0}, "compensation_would_be_discarded"),
    ])
    def test_target_drift_is_refused(self, worker, deployment_kwargs, code):
        client = _standard_client(worker, deployment=_deployment(worker, **deployment_kwargs))
        answer = _run(worker, client, _envelope(worker))
        assert answer["succeeded"] is False and code in answer["provider_message"]
        assert client.writes == []

    def test_a_missing_deployment_is_refused(self, worker):
        client = _standard_client(worker, deployment=None)
        answer = _run(worker, client, _envelope(worker))
        assert "target_absent" in answer["provider_message"] and client.writes == []

    def test_an_unavailable_target_revision_has_no_destructive_fallback(self, worker):
        client = _standard_client(worker, replicasets=[_rs("p114-shop-bad", "2", BAD)])
        answer = _run(worker, client, _envelope(worker))
        assert "target_revision_unavailable" in answer["provider_message"]
        assert client.patches == [], "no substitute revision, no dry run, no write"

    def test_a_drifted_target_revision_is_refused(self, worker):
        client = _standard_client(worker, replicasets=[_rs("p114-shop-good", "1", _template("tampered")),
                                                       _rs("p114-shop-bad", "2", BAD)])
        answer = _run(worker, client, _envelope(worker))
        assert "target_revision_drifted" in answer["provider_message"] and client.patches == []

    def test_a_missing_pre_action_revision_is_not_compensable(self, worker):
        client = _standard_client(worker, replicasets=[_rs("p114-shop-good", "1", GOOD)])
        answer = _run(worker, client, _envelope(worker))
        assert "compensation_unavailable" in answer["provider_message"] and client.patches == []

    def test_a_rejected_dry_run_prevents_the_write(self, worker):
        client = _standard_client(worker, dry_status=422)
        answer = _run(worker, client, _envelope(worker))
        assert "dry_run_conflict" in answer["provider_message"]
        assert len(client.patches) == 1 and client.writes == []

    def test_a_conflict_on_the_write_is_a_refusal_not_an_ambiguity(self, worker):
        client = _standard_client(worker, write_status=422)
        answer = _run(worker, client, _envelope(worker))
        assert answer["ambiguous"] is False and "precondition_changed_during_write" in answer["provider_message"]

    def test_a_transport_failure_on_the_write_is_ambiguous(self, worker):
        client = _standard_client(worker, write_raises=True)
        answer = _run(worker, client, _envelope(worker))
        assert answer["succeeded"] is False and answer["ambiguous"] is True

    def test_already_at_target_is_an_idempotent_no_op(self, worker):
        client = _standard_client(worker, deployment=_deployment(worker, template=GOOD, generation=6, revision="3"))
        answer = _run(worker, client, _envelope(worker))
        assert answer["succeeded"] is True and answer["evidence"]["noop"] == "already_at_target"
        assert client.patches == []

    def test_an_authority_that_lapses_before_the_write_is_fenced(self, worker):
        client = _standard_client(worker)
        target = worker._verify_binding(_envelope(worker))
        later = [datetime.now(timezone.utc), datetime.now(timezone.utc) + timedelta(minutes=10)]
        with pytest.raises(worker.Refused) as refused:
            worker.perform_rollback(target, client, clock=lambda: later.pop(0) if len(later) > 1 else later[0])
        assert refused.value.reason_code == "authority_expired"
        assert client.writes == []


# -- Phase 11.4 run 8: the adapter's failure classification -------------------

def test_a_definite_worker_failure_maps_to_a_real_provider_failure_class():
    """The adapter named ``ProviderFailure.PROVIDER_ERROR`` (never a member):
    a 401, 403 or lost-race 422 raised AttributeError and was recorded as an
    UNKNOWN outcome instead of the definite failure the worker established."""
    from backend.contexts.execution.infrastructure.adapters.contained_worker import _failure_for_status
    from backend.contracts.provider import ProviderFailure as F

    assert _failure_for_status(401) is F.AUTHENTICATION_FAILURE
    assert _failure_for_status(403) is F.AUTHORIZATION_FAILURE
    assert _failure_for_status(422) is F.PRECONDITION_FAILED
    assert _failure_for_status(409) is F.CONFLICT
    assert _failure_for_status(None) is F.PRECONDITION_FAILED
    # a status nobody mapped never claims more certainty than the answer carries
    assert _failure_for_status(500) is F.UNKNOWN_OUTCOME and F.UNKNOWN_OUTCOME.is_ambiguous
    assert _failure_for_status("401") is F.UNKNOWN_OUTCOME


def test_every_provider_failure_the_backend_names_exists():
    """A misspelt enum member is only an AttributeError on the failure path --
    the path least often exercised and the one that must not crash."""
    import pathlib
    import re

    from backend.contracts.provider import ProviderFailure

    root = pathlib.Path(__file__).resolve().parents[3] / "backend"
    named = set()
    for path in root.rglob("*.py"):
        named |= set(re.findall(r"ProviderFailure\.([A-Z][A-Z_]+)\b", path.read_text(encoding="utf-8", errors="ignore")))
    missing = sorted(n for n in named if n not in ProviderFailure.__members__)
    assert not missing, missing
