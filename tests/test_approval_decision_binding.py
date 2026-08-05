"""Adversarial tests for approval decision binding (ADR-014).

PR-04 bound an artifact to a digest stored beside it. Its documented residual
gap: an attacker who can write that file can change the payload and recompute
the digest in one write, producing a self-consistent forgery.

These tests exercise the closure. The decisive one is
``TestTwoStoreForgery::test_forging_both_stores_is_caught_by_the_signature`` --
it performs exactly the attack PR-04 could not stop and asserts it is refused.
"""

from __future__ import annotations

import copy
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.contracts import HashAlgorithm, PayloadDigest
from backend.services.enterprise_approval_action_dispatcher import (
    PendingActionStore,
    handle_approval_event,
)
from backend.services.enterprise_approval_decision import (
    APPROVAL_RECORD_VERSION,
    ApprovalDecisionStore,
    ApprovalFailure,
    ApprovalStatus,
    HmacApprovalSigner,
    UnsignedApprovalSigner,
    resolve_signer,
)
from backend.services.enterprise_approval_integrity import ConsumedLedger, record_digest
from backend.platform.audit import AuditRuntime, InMemoryAuditStore
from backend.services.enterprise_integrity_audit import IntegrityAuditLog

PAYLOAD = {"container_name": "web-01", "ticket_key": "OPS-1"}
ACTION = "docker_health_fix"
KEY = "k" * 32


def _digest(payload=PAYLOAD, workflow_id="wf-1", action=ACTION) -> PayloadDigest:
    return record_digest(workflow_id, action, payload)


@pytest.fixture
def signer() -> HmacApprovalSigner:
    return HmacApprovalSigner(KEY)


@pytest.fixture
def decisions(tmp_path: Path, signer) -> ApprovalDecisionStore:
    return ApprovalDecisionStore(tmp_path / "decisions.json", signer=signer)


@pytest.fixture
def granted(decisions) -> ApprovalDecisionStore:
    """A store holding one granted approval for the standard payload."""
    decisions.record_request("wf-1", ACTION, _digest())
    decisions.record_grant("wf-1", "user-42", "human")
    return decisions


@pytest.fixture
def wired(monkeypatch, tmp_path: Path, signer):
    """A fully wired dispatcher with isolated stores, ledger, and audit."""
    import backend.services.enterprise_approval_action_dispatcher as dispatcher
    import backend.services.enterprise_approval_integrity as integrity

    pending = PendingActionStore(tmp_path / "pending.json")
    decisions = ApprovalDecisionStore(tmp_path / "decisions.json", signer=signer)
    ledger = ConsumedLedger()
    audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))

    monkeypatch.setattr(dispatcher, "pending_action_store", pending)
    monkeypatch.setattr(dispatcher, "approval_decision_store", decisions)
    monkeypatch.setattr(dispatcher, "consumed_ledger", ledger)
    monkeypatch.setattr(dispatcher, "integrity_audit", audit)
    monkeypatch.setattr(integrity, "consumed_ledger", ledger)

    return {"pending": pending, "decisions": decisions, "audit": audit}


@pytest.fixture
def dispatched(monkeypatch) -> list:
    import backend.services.enterprise_approval_action_dispatcher as dispatcher

    calls: list = []

    async def _capture(payload):
        calls.append(payload)

    monkeypatch.setattr(dispatcher, "_DISPATCH_HANDLERS", {ACTION: _capture, "rollback": _capture})
    return calls


def _approved(workflow_id="wf-1", **extra) -> dict:
    return {"workflow_id": workflow_id, "status": "approved", "resolved_by": "user-42", **extra}


# ======================================================================
# The closure: two-store forgery
# ======================================================================


class TestTwoStoreForgery:
    """The attack PR-04 explicitly could not stop."""

    def test_forging_the_artifact_alone_is_caught(self, granted) -> None:
        """Self-consistent artifact forgery -- payload and local digest both
        rewritten -- is caught because the approval record holds the original."""
        forged = _digest({"container_name": "prod-payments-db"})
        verdict = granted.verify_for_execution("wf-1", forged, ACTION)
        assert verdict.refused
        assert verdict.failure is ApprovalFailure.ARTIFACT_MODIFIED

    def test_forging_both_stores_is_caught_by_the_signature(self, granted) -> None:
        """The decisive test. An attacker rewrites the artifact AND the approval
        record's digest. Only the HMAC stops this."""
        forged = _digest({"container_name": "prod-payments-db"})

        record = granted.get("wf-1")
        record["artifact_digest"]["value"] = forged.value
        granted._records["wf-1"] = record

        verdict = granted.verify_for_execution("wf-1", forged, ACTION)
        assert verdict.refused
        assert verdict.failure is ApprovalFailure.APPROVAL_SIGNATURE_INVALID

    def test_unsigned_deployment_still_catches_single_store_forgery(self, tmp_path) -> None:
        """Without a key, separation alone still defeats the PR-04 attack."""
        store = ApprovalDecisionStore(tmp_path / "d.json", signer=UnsignedApprovalSigner())
        store.record_request("wf-1", ACTION, _digest())
        store.record_grant("wf-1", "user-42", "human")

        forged = _digest({"container_name": "prod-payments-db"})
        assert store.verify_for_execution("wf-1", forged, ACTION).failure is (
            ApprovalFailure.ARTIFACT_MODIFIED
        )

    def test_unsigned_deployment_cannot_stop_two_store_forgery(self, tmp_path) -> None:
        """Documents the honest limit of running without a signing key."""
        store = ApprovalDecisionStore(tmp_path / "d.json", signer=UnsignedApprovalSigner())
        store.record_request("wf-1", ACTION, _digest())
        store.record_grant("wf-1", "user-42", "human")

        forged = _digest({"container_name": "prod-payments-db"})
        record = store.get("wf-1")
        record["artifact_digest"]["value"] = forged.value
        store._records["wf-1"] = record

        assert store.verify_for_execution("wf-1", forged, ACTION).ok is True, (
            "unsigned mode provides separation only; set APPROVAL_SIGNING_KEY to close this"
        )

    def test_signature_cannot_be_stripped_to_downgrade(self, granted) -> None:
        """Removing the signature must not make a signed verifier accept."""
        record = granted.get("wf-1")
        record["signature"] = None
        granted._records["wf-1"] = record
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID
        )

    def test_unsigned_verifier_rejects_a_record_carrying_a_signature(self) -> None:
        """An unsigned signer must not wave through what it cannot check."""
        assert UnsignedApprovalSigner().verify(b"x", "deadbeef") is False
        assert UnsignedApprovalSigner().verify(b"x", None) is True


# ======================================================================
# Happy path
# ======================================================================


class TestApprovedArtifactExecutes:
    def test_matching_artifact_verifies(self, granted) -> None:
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).ok is True

    def test_verdict_reports_both_digests(self, granted) -> None:
        verdict = granted.verify_for_execution("wf-1", _digest(), ACTION)
        assert verdict.approved_digest == verdict.current_digest
        assert verdict.approver == "user-42"

    @pytest.mark.asyncio
    async def test_end_to_end_dispatch(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        assert await handle_approval_event(_approved()) == ACTION
        assert dispatched == [PAYLOAD]

    @pytest.mark.asyncio
    async def test_save_records_the_approval_request(self, wired) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        record = wired["decisions"].get("wf-1")
        assert record is not None
        assert record["status"] == ApprovalStatus.PENDING.value
        assert record["artifact_digest"]["value"] == _digest().value

    @pytest.mark.asyncio
    async def test_dispatch_consumes_the_approval(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        await handle_approval_event(_approved())
        assert wired["decisions"].get("wf-1")["status"] == ApprovalStatus.CONSUMED.value


# ======================================================================
# Artifact and approval modification
# ======================================================================


class TestModification:
    @pytest.mark.asyncio
    async def test_modified_artifact_never_dispatches(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)

        stored = wired["pending"].peek("wf-1")
        stored["payload"]["container_name"] = "prod-payments-db"
        new_digest = record_digest("wf-1", ACTION, stored["payload"])
        stored["digest"]["value"] = new_digest.value  # self-consistent forgery
        wired["pending"]._pending["wf-1"] = stored

        assert await handle_approval_event(_approved()) is None
        assert dispatched == [], "a forged artifact reached a dispatch handler"

    @pytest.mark.asyncio
    async def test_forgery_refusal_is_audited_as_tampering(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        stored = wired["pending"].peek("wf-1")
        stored["payload"]["container_name"] = "prod-payments-db"
        stored["digest"]["value"] = record_digest("wf-1", ACTION, stored["payload"]).value
        wired["pending"]._pending["wf-1"] = stored

        await handle_approval_event(_approved())
        entries = [e for e in wired["audit"].entries() if e.detail["execution_refused"]]
        assert len(entries) == 1
        assert entries[0].detail["failure"] == ApprovalFailure.ARTIFACT_MODIFIED.value
        assert entries[0].detail["tamper_evidence"] is True

    def test_action_type_substitution_is_refused(self, granted) -> None:
        assert granted.verify_for_execution(
            "wf-1", _digest(action="rollback"), "rollback"
        ).failure is ApprovalFailure.ACTION_TYPE_MISMATCH

    def test_approver_identity_tampering_invalidates_the_signature(self, granted) -> None:
        record = granted.get("wf-1")
        record["approver_id"] = "attacker"
        granted._records["wf-1"] = record
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID
        )

    def test_expiry_extension_invalidates_the_signature(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest(), ttl_minutes=1)
        decisions.record_grant("wf-1", "user-42", "human")
        record = decisions.get("wf-1")
        record["expires_at"] = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        decisions._records["wf-1"] = record
        assert decisions.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID
        )


# ======================================================================
# Record substitution and cross-mission replay
# ======================================================================


class TestSubstitution:
    def test_approval_for_another_workflow_does_not_apply(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest())
        decisions.record_grant("wf-1", "user-42", "human")
        assert decisions.verify_for_execution("wf-2", _digest(), ACTION).failure is (
            ApprovalFailure.LEGACY_NO_APPROVAL_RECORD
        )

    def test_moving_a_record_to_another_workflow_invalidates_it(self, granted) -> None:
        """Cross-mission replay: copy an approval onto a different workflow."""
        stolen = granted.get("wf-1")
        granted._records["wf-2"] = stolen
        verdict = granted.verify_for_execution("wf-2", _digest(workflow_id="wf-2"), ACTION)
        assert verdict.refused
        assert verdict.failure in {
            ApprovalFailure.ARTIFACT_MODIFIED,
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID,
        }

    @pytest.mark.asyncio
    async def test_cross_workflow_dispatch_is_refused(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        approval = wired["decisions"].get("wf-1")
        wired["decisions"]._records["wf-2"] = approval

        assert await handle_approval_event(_approved("wf-2")) is None
        assert dispatched == []


# ======================================================================
# Replay
# ======================================================================


class TestApprovalReplay:
    def test_consumed_approval_refuses(self, granted) -> None:
        granted.mark_consumed("wf-1")
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_REPLAY
        )

    def test_mark_consumed_is_single_use(self, granted) -> None:
        assert granted.mark_consumed("wf-1") is True
        assert granted.mark_consumed("wf-1") is False

    def test_mark_consumed_is_thread_safe(self, granted) -> None:
        wins: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            result = granted.mark_consumed("wf-1")
            with lock:
                wins.append(result)

        threads = [threading.Thread(target=worker) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(wins) == 1, f"{sum(wins)} threads consumed the same approval"

    @pytest.mark.asyncio
    async def test_replayed_workflow_does_not_execute_twice(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        await handle_approval_event(_approved())
        assert len(dispatched) == 1

        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        await handle_approval_event(_approved())
        assert len(dispatched) == 1, "a replayed approval executed a second time"


# ======================================================================
# Missing, wrong, and expired approvals
# ======================================================================


class TestMissingAndInvalid:
    def test_missing_record_refuses(self, decisions) -> None:
        assert decisions.verify_for_execution("wf-absent", _digest(), ACTION).failure is (
            ApprovalFailure.LEGACY_NO_APPROVAL_RECORD
        )

    def test_ungranted_record_refuses(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest())
        assert decisions.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_NOT_GRANTED
        )

    def test_revoked_record_refuses(self, granted) -> None:
        granted.revoke("wf-1")
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_NOT_GRANTED
        )

    def test_expired_approval_refuses(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest(), ttl_minutes=30)
        decisions.record_grant("wf-1", "user-42", "human")
        future = datetime.now(timezone.utc) + timedelta(hours=2)
        assert decisions.verify_for_execution("wf-1", _digest(), ACTION, now=future).failure is (
            ApprovalFailure.APPROVAL_EXPIRED
        )

    def test_unexpired_approval_verifies(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest(), ttl_minutes=30)
        decisions.record_grant("wf-1", "user-42", "human")
        soon = datetime.now(timezone.utc) + timedelta(minutes=5)
        assert decisions.verify_for_execution("wf-1", _digest(), ACTION, now=soon).ok is True

    def test_version_mismatch_refuses(self, granted) -> None:
        record = granted.get("wf-1")
        record["record_version"] = APPROVAL_RECORD_VERSION + 1
        granted._records["wf-1"] = record
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_VERSION_MISMATCH
        )

    @pytest.mark.parametrize(
        "approver_id,approver_kind",
        [
            (None, "human"),
            ("", "human"),
            ("cortexprime", "platform"),
            ("webhook", "external_system"),
            ("user-42", None),
        ],
    )
    def test_non_human_or_missing_approver_refuses(
        self, decisions, approver_id, approver_kind
    ) -> None:
        """Constitution: the platform must never authorize itself."""
        decisions.record_request("wf-1", ACTION, _digest())
        decisions.record_grant("wf-1", approver_id, approver_kind)
        assert decisions.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_IDENTITY_INVALID
        )

    @pytest.mark.parametrize(
        "bad", [{"algorithm": "md5", "value": "0" * 32}, {"value": "0" * 64}, "not-a-map", None]
    )
    def test_malformed_approved_digest_refuses(self, granted, bad) -> None:
        record = granted.get("wf-1")
        record["artifact_digest"] = bad
        granted._records["wf-1"] = record
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).refused

    def test_grant_on_a_missing_record_is_a_no_op(self, decisions) -> None:
        assert decisions.record_grant("wf-absent", "user-42", "human") is None


# ======================================================================
# Canonicalization
# ======================================================================


class TestCanonicalizationAttacks:
    def test_key_order_does_not_change_the_digest(self, granted) -> None:
        reordered = dict(reversed(list(PAYLOAD.items())))
        assert granted.verify_for_execution("wf-1", _digest(reordered), ACTION).ok is True

    def test_type_substitution_is_detected(self, decisions) -> None:
        decisions.record_request("wf-1", ACTION, _digest({"replicas": 1}))
        decisions.record_grant("wf-1", "user-42", "human")
        for substitute in ("1", 1.0, True):
            assert decisions.verify_for_execution(
                "wf-1", _digest({"replicas": substitute}), ACTION
            ).failure is ApprovalFailure.ARTIFACT_MODIFIED

    def test_nested_modification_is_detected(self, decisions) -> None:
        original = {"target": {"env": "staging"}}
        decisions.record_request("wf-1", ACTION, _digest(original))
        decisions.record_grant("wf-1", "user-42", "human")
        assert decisions.verify_for_execution(
            "wf-1", _digest({"target": {"env": "production"}}), ACTION
        ).failure is ApprovalFailure.ARTIFACT_MODIFIED

    def test_signature_covers_the_digest_algorithm(self, granted) -> None:
        record = granted.get("wf-1")
        record["artifact_digest"]["algorithm"] = HashAlgorithm.SHA512.value
        granted._records["wf-1"] = record
        assert granted.verify_for_execution("wf-1", _digest(), ACTION).refused


# ======================================================================
# Concurrency
# ======================================================================


class TestConcurrentVerification:
    def test_parallel_verification_is_consistent(self, granted) -> None:
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            outcomes = [granted.verify_for_execution("wf-1", _digest(), ACTION).ok for _ in range(50)]
            with lock:
                results.extend(outcomes)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert all(results) and len(results) == 400

    def test_parallel_verification_of_a_forgery_never_passes(self, granted) -> None:
        forged = _digest({"container_name": "prod-payments-db"})
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            outcomes = [granted.verify_for_execution("wf-1", forged, ACTION).ok for _ in range(50)]
            with lock:
                results.extend(outcomes)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not any(results)


# ======================================================================
# Signing configuration
# ======================================================================


class TestSignerConfiguration:
    def test_hmac_signer_round_trips(self, signer) -> None:
        payload = b"approval"
        assert signer.verify(payload, signer.sign(payload)) is True

    def test_hmac_signer_rejects_a_wrong_signature(self, signer) -> None:
        assert signer.verify(b"approval", "0" * 64) is False
        assert signer.verify(b"approval", None) is False

    def test_short_key_is_refused(self) -> None:
        with pytest.raises(ValueError, match="at least 32 characters"):
            HmacApprovalSigner("too-short")

    def test_resolve_signer_uses_hmac_when_a_key_is_set(self, monkeypatch) -> None:
        monkeypatch.setenv("APPROVAL_SIGNING_KEY", KEY)
        assert resolve_signer().algorithm == "hmac-sha256"

    def test_resolve_signer_falls_back_to_unsigned(self, monkeypatch) -> None:
        monkeypatch.delenv("APPROVAL_SIGNING_KEY", raising=False)
        assert resolve_signer().algorithm == "none"

    def test_strict_mode_refuses_unsigned_records(self, monkeypatch, tmp_path) -> None:
        store = ApprovalDecisionStore(tmp_path / "d.json", signer=UnsignedApprovalSigner())
        store.record_request("wf-1", ACTION, _digest())
        store.record_grant("wf-1", "user-42", "human")

        monkeypatch.setenv("APPROVAL_REQUIRE_SIGNATURE", "true")
        assert store.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_UNSIGNED_REJECTED
        )

    def test_record_states_which_algorithm_sealed_it(self, granted) -> None:
        """An auditor must be able to tell signed records from unsigned ones."""
        assert granted.get("wf-1")["signature_algorithm"] == "hmac-sha256"


# ======================================================================
# Migration
# ======================================================================


class TestMigration:
    @pytest.mark.asyncio
    async def test_artifact_without_an_approval_record_never_dispatches(
        self, wired, dispatched
    ) -> None:
        """A PR-04-era artifact has no decision record and must not execute."""
        record = wired["pending"].save("wf-1", ACTION, PAYLOAD)
        wired["decisions"].discard("wf-1")  # simulate a pre-PR-05 stash

        assert await handle_approval_event(_approved()) is None
        assert dispatched == []

    @pytest.mark.asyncio
    async def test_legacy_refusal_is_classified_explicitly(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        wired["decisions"].discard("wf-1")
        await handle_approval_event(_approved())

        entries = [e for e in wired["audit"].entries() if e.detail["execution_refused"]]
        assert entries[0].detail["failure"] == ApprovalFailure.LEGACY_NO_APPROVAL_RECORD.value

    def test_legacy_absence_is_not_flagged_as_tampering(self) -> None:
        assert ApprovalFailure.LEGACY_NO_APPROVAL_RECORD.is_tamper_evidence is False
        assert ApprovalFailure.ARTIFACT_MODIFIED.is_tamper_evidence is True

    def test_records_survive_a_store_reload(self, tmp_path, signer) -> None:
        path = tmp_path / "decisions.json"
        first = ApprovalDecisionStore(path, signer=signer)
        first.record_request("wf-1", ACTION, _digest())
        first.record_grant("wf-1", "user-42", "human")

        reloaded = ApprovalDecisionStore(path, signer=HmacApprovalSigner(KEY))
        assert reloaded.verify_for_execution("wf-1", _digest(), ACTION).ok is True

    def test_a_different_key_invalidates_existing_records(self, tmp_path, signer) -> None:
        """Key rotation must invalidate rather than silently accept."""
        path = tmp_path / "decisions.json"
        first = ApprovalDecisionStore(path, signer=signer)
        first.record_request("wf-1", ACTION, _digest())
        first.record_grant("wf-1", "user-42", "human")

        rotated = ApprovalDecisionStore(path, signer=HmacApprovalSigner("z" * 32))
        assert rotated.verify_for_execution("wf-1", _digest(), ACTION).failure is (
            ApprovalFailure.APPROVAL_SIGNATURE_INVALID
        )

    @pytest.mark.asyncio
    async def test_rejected_workflow_revokes_the_approval(self, wired, dispatched) -> None:
        wired["pending"].save("wf-1", ACTION, PAYLOAD)
        await handle_approval_event({"workflow_id": "wf-1", "status": "rejected"})
        assert wired["decisions"].get("wf-1")["status"] == ApprovalStatus.REVOKED.value
        assert dispatched == []
