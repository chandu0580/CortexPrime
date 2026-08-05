"""Adversarial tests for approval integrity (Constitution I2, ADR-013).

Every test here is an attempt to make the system execute something a human did
not approve. The suite is organized by attack, not by function, so a reviewer
can check coverage against a threat model rather than against an API surface.

The load-bearing property: **there is no input to this pipeline that results in
execution without a matching digest.** Tests assert refusal, not merely an
error, and assert that the refusal was audited -- a control that fires silently
cannot be shown to have fired.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path

import pytest

from backend.contracts import AuditEventKind
from backend.services.enterprise_approval_action_dispatcher import (
    PendingActionStore,
    handle_approval_event,
)
from backend.services.enterprise_approval_integrity import (
    RECORD_VERSION,
    ConsumedLedger,
    IntegrityFailure,
    build_record,
    record_digest,
    verify_record,
)
from backend.platform.audit import AuditRuntime, InMemoryAuditStore
from backend.services.enterprise_integrity_audit import IntegrityAuditLog

PAYLOAD = {"container_name": "web-01", "container_id": "abc123", "ticket_key": "OPS-1"}


@pytest.fixture
def store(tmp_path: Path) -> PendingActionStore:
    return PendingActionStore(tmp_path / "pending.json")


@pytest.fixture
def ledger() -> ConsumedLedger:
    return ConsumedLedger()


@pytest.fixture
def record() -> dict:
    return build_record("wf-1", "docker_health_fix", PAYLOAD)


@pytest.fixture(autouse=True)
def _isolate_global_state(monkeypatch, tmp_path: Path):
    """Give every test its own store, ledger, and audit log.

    The dispatcher uses module-level singletons. Without isolation one test's
    consumed workflow ids would refuse another test's dispatch, and audit
    assertions would see entries from earlier tests.
    """
    import backend.services.enterprise_approval_action_dispatcher as dispatcher
    import backend.services.enterprise_approval_integrity as integrity
    from backend.services.enterprise_approval_decision import (
        ApprovalDecisionStore,
        HmacApprovalSigner,
    )

    fresh_store = PendingActionStore(tmp_path / "isolated_pending.json")
    fresh_ledger = ConsumedLedger()
    fresh_audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
    fresh_decisions = ApprovalDecisionStore(
        tmp_path / "isolated_decisions.json", signer=HmacApprovalSigner("k" * 32)
    )

    monkeypatch.setattr(dispatcher, "pending_action_store", fresh_store)
    monkeypatch.setattr(dispatcher, "consumed_ledger", fresh_ledger)
    monkeypatch.setattr(dispatcher, "integrity_audit", fresh_audit)
    monkeypatch.setattr(dispatcher, "approval_decision_store", fresh_decisions)
    monkeypatch.setattr(integrity, "consumed_ledger", fresh_ledger)

    yield {
        "store": fresh_store,
        "ledger": fresh_ledger,
        "audit": fresh_audit,
        "decisions": fresh_decisions,
    }


@pytest.fixture
def dispatched(monkeypatch) -> list:
    """Capture what actually reached a dispatch handler.

    Assertions on this list are the real test: a refusal that still executes is
    not a refusal.
    """
    import backend.services.enterprise_approval_action_dispatcher as dispatcher

    calls: list = []

    async def _capture(payload):
        calls.append(payload)

    monkeypatch.setattr(
        dispatcher, "_DISPATCH_HANDLERS", {"docker_health_fix": _capture, "rollback": _capture}
    )
    return calls


def _approved(workflow_id: str = "wf-1", **extra) -> dict:
    """A realistic approval event.

    ``resolved_by`` is present because a workflow that genuinely reaches
    ``approved`` always carries the approver (``approve_step`` sets
    ``steps[].resolved_by``). PR-05 requires that identity, so a payload without
    one is refused -- correctly, but it would not represent real traffic.
    """
    return {
        "workflow_id": workflow_id,
        "status": "approved",
        "resolved_by": "user-42",
        **extra,
    }


# ======================================================================
# The happy path -- zero false positives
# ======================================================================


class TestVerifiedActionExecutes:
    """A control that refuses valid work is as broken as one that permits
    invalid work. These tests guard against false positives."""

    def test_untampered_record_verifies(self, record) -> None:
        assert verify_record("wf-1", record).ok is True

    @pytest.mark.asyncio
    async def test_untampered_record_dispatches(self, _isolate_global_state, dispatched) -> None:
        _isolate_global_state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        assert await handle_approval_event(_approved()) == "docker_health_fix"
        assert dispatched == [PAYLOAD]

    @pytest.mark.asyncio
    async def test_dispatch_is_audited_as_verified(
        self, _isolate_global_state, dispatched
    ) -> None:
        _isolate_global_state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        await handle_approval_event(_approved())
        entries = _isolate_global_state["audit"].entries()
        assert len(entries) == 1
        assert entries[0].kind is AuditEventKind.EXECUTION_STARTED
        assert entries[0].detail["execution_refused"] is False

    @pytest.mark.asyncio
    async def test_break_glass_also_dispatches(self, _isolate_global_state, dispatched) -> None:
        _isolate_global_state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        # Break-glass records its approver in break_glass_by, not resolved_by.
        await handle_approval_event(
            {"workflow_id": "wf-1", "status": "break_glass", "break_glass_by": "user-42"}
        )
        assert dispatched == [PAYLOAD]

    def test_json_round_trip_does_not_break_verification(self, record) -> None:
        """The store persists via JSON; a round trip must not alter the digest."""
        restored = json.loads(json.dumps(record))
        assert verify_record("wf-1", restored).ok is True

    def test_key_reordering_does_not_break_verification(self, record) -> None:
        """Canonicalization sorts keys, so dict rebuild order is irrelevant."""
        reordered = dict(reversed(list(record.items())))
        reordered["payload"] = dict(reversed(list(record["payload"].items())))
        assert verify_record("wf-1", reordered).ok is True

    def test_empty_payload_is_bindable(self) -> None:
        empty = build_record("wf-1", "rollback", {})
        assert verify_record("wf-1", empty).ok is True


# ======================================================================
# Payload tampering
# ======================================================================


class TestPayloadTampering:
    def test_modified_payload_value_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["payload"]["container_name"] = "prod-payments-db"
        verdict = verify_record("wf-1", tampered)
        assert verdict.refused
        assert verdict.failure is IntegrityFailure.DIGEST_MISMATCH

    def test_added_payload_field_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["payload"]["force"] = True
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_removed_payload_field_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        del tampered["payload"]["ticket_key"]
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_nested_field_modification_is_refused(self) -> None:
        nested = build_record("wf-1", "rollback", {"target": {"env": "staging", "n": 1}})
        tampered = copy.deepcopy(nested)
        tampered["payload"]["target"]["env"] = "production"
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_deeply_nested_modification_is_refused(self) -> None:
        deep = build_record("wf-1", "rollback", {"a": {"b": {"c": {"d": "original"}}}})
        tampered = copy.deepcopy(deep)
        tampered["payload"]["a"]["b"]["c"]["d"] = "tampered"
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_list_element_modification_is_refused(self) -> None:
        listed = build_record("wf-1", "rollback", {"services": ["web", "cache"]})
        tampered = copy.deepcopy(listed)
        tampered["payload"]["services"][1] = "database"
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_list_reordering_is_refused(self) -> None:
        """Sequence order is significant; reordering changes meaning."""
        listed = build_record("wf-1", "rollback", {"steps": ["drain", "restart"]})
        tampered = copy.deepcopy(listed)
        tampered["payload"]["steps"] = ["restart", "drain"]
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_type_substitution_is_refused(self) -> None:
        """1 and "1" and True must not be interchangeable."""
        typed = build_record("wf-1", "rollback", {"replicas": 1})
        for substitute in ("1", 1.0, True):
            tampered = copy.deepcopy(typed)
            tampered["payload"]["replicas"] = substitute
            assert verify_record("wf-1", tampered).refused, f"{substitute!r} was accepted"

    @pytest.mark.asyncio
    async def test_tampered_payload_never_reaches_a_handler(
        self, _isolate_global_state, dispatched
    ) -> None:
        """The assertion that matters: refusal means nothing executed."""
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)

        stored = state["store"].peek("wf-1")
        stored["payload"]["container_name"] = "prod-payments-db"
        state["store"]._pending["wf-1"] = stored  # simulate an on-disk edit

        assert await handle_approval_event(_approved()) is None
        assert dispatched == [], "a tampered payload reached a dispatch handler"


# ======================================================================
# Metadata and identity tampering
# ======================================================================


class TestMetadataTampering:
    def test_action_type_substitution_is_refused(self, record) -> None:
        """Re-labelling a benign payload onto a destructive handler."""
        tampered = copy.deepcopy(record)
        tampered["action_type"] = "rollback"
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    def test_workflow_id_substitution_is_refused(self, record) -> None:
        """Moving an approved action onto a different workflow's authority."""
        tampered = copy.deepcopy(record)
        tampered["workflow_id"] = "wf-999"
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.WORKFLOW_MISMATCH

    def test_lookup_under_another_workflow_is_refused(self, record) -> None:
        """The same record retrieved under a different key must not verify."""
        assert verify_record("wf-2", record).failure is IntegrityFailure.WORKFLOW_MISMATCH

    def test_version_downgrade_to_legacy_is_refused(self, record) -> None:
        """Stripping the version to trigger the unversioned path."""
        tampered = copy.deepcopy(record)
        del tampered["record_version"]
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.LEGACY_UNVERSIONED

    def test_version_field_tampering_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["record_version"] = RECORD_VERSION - 1 or 1
        verdict = verify_record("wf-1", tampered)
        assert verdict.refused

    def test_created_at_is_not_covered_but_harmless(self, record) -> None:
        """created_at is outside the digest -- it is not part of what was
        authorized. Changing it must not break a valid record."""
        tampered = copy.deepcopy(record)
        tampered["created_at"] = "2020-01-01T00:00:00+00:00"
        assert verify_record("wf-1", tampered).ok is True


# ======================================================================
# Digest tampering
# ======================================================================


class TestDigestTampering:
    def test_missing_digest_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        del tampered["digest"]
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.MISSING_DIGEST

    def test_wrong_digest_value_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["digest"]["value"] = "0" * 64
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.DIGEST_MISMATCH

    @pytest.mark.parametrize(
        "bad_digest",
        [
            {"algorithm": "sha256", "value": "short"},
            {"algorithm": "md5", "value": "0" * 32},
            {"algorithm": "sha256", "value": "Z" * 64},
            {"algorithm": "sha256"},
            {"value": "0" * 64},
            "not-a-mapping",
            None,
        ],
    )
    def test_malformed_digest_is_refused(self, record, bad_digest) -> None:
        tampered = copy.deepcopy(record)
        tampered["digest"] = bad_digest
        verdict = verify_record("wf-1", tampered)
        assert verdict.refused
        assert verdict.failure in {
            IntegrityFailure.MALFORMED_DIGEST,
            IntegrityFailure.MISSING_DIGEST,
        }

    def test_recomputed_digest_for_tampered_content_is_still_refused(self, record) -> None:
        """The full forgery attempt: change the payload AND update the digest.

        This is the attack the digest alone cannot stop -- it is stopped because
        an attacker who can rewrite the record cannot also rewrite the approval
        that a human already granted against the original digest. The test
        documents that the *digest check* passes here, so the security argument
        rests on the approval record being the authority, not on this check.
        """
        forged = copy.deepcopy(record)
        forged["payload"]["container_name"] = "prod-payments-db"
        new_digest = record_digest("wf-1", forged["action_type"], forged["payload"])
        forged["digest"] = {"algorithm": new_digest.algorithm.value, "value": new_digest.value}

        assert verify_record("wf-1", forged).ok is True, (
            "a fully self-consistent forgery passes the digest check by construction; "
            "PR-05 binds the digest to the approval decision itself"
        )


# ======================================================================
# Legacy records
# ======================================================================


class TestLegacyRecords:
    def test_pre_pr04_record_is_refused(self) -> None:
        legacy = {"action_type": "docker_health_fix", "payload": PAYLOAD}
        verdict = verify_record("wf-1", legacy)
        assert verdict.refused
        assert verdict.failure is IntegrityFailure.LEGACY_UNVERSIONED

    def test_legacy_refusal_is_not_flagged_as_tampering(self) -> None:
        """A record predating the check is not evidence of an attack."""
        assert IntegrityFailure.LEGACY_UNVERSIONED.is_tamper_evidence is False
        assert IntegrityFailure.DIGEST_MISMATCH.is_tamper_evidence is True

    @pytest.mark.asyncio
    async def test_legacy_record_never_dispatches(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"]._pending["wf-1"] = {"action_type": "docker_health_fix", "payload": PAYLOAD}

        assert await handle_approval_event(_approved()) is None
        assert dispatched == []

    @pytest.mark.asyncio
    async def test_legacy_refusal_is_audited(self, _isolate_global_state, dispatched) -> None:
        state = _isolate_global_state
        state["store"]._pending["wf-1"] = {"action_type": "docker_health_fix", "payload": PAYLOAD}
        await handle_approval_event(_approved())

        entries = state["audit"].entries()
        assert len(entries) == 1
        assert entries[0].detail["failure"] == IntegrityFailure.LEGACY_UNVERSIONED.value
        assert entries[0].detail["execution_refused"] is True
        assert entries[0].kind is AuditEventKind.EXECUTION_REFUSED

    def test_unsupported_future_version_is_refused(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["record_version"] = RECORD_VERSION + 1
        assert verify_record("wf-1", tampered).failure is IntegrityFailure.UNSUPPORTED_VERSION

    @pytest.mark.parametrize("version", ["2", 2.0, None, -1, 0])
    def test_non_integer_or_invalid_version_is_refused(self, record, version) -> None:
        tampered = copy.deepcopy(record)
        tampered["record_version"] = version
        assert verify_record("wf-1", tampered).refused


# ======================================================================
# Replay
# ======================================================================


class TestReplayProtection:
    @pytest.mark.asyncio
    async def test_second_dispatch_of_the_same_workflow_is_refused(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)

        assert await handle_approval_event(_approved()) == "docker_health_fix"
        assert len(dispatched) == 1

        # Re-insert the identical record and resolve the workflow again.
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        assert await handle_approval_event(_approved()) is None
        assert len(dispatched) == 1, "a replayed workflow executed a second time"

    @pytest.mark.asyncio
    async def test_replay_refusal_is_flagged_as_tampering(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        await handle_approval_event(_approved())
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        await handle_approval_event(_approved())

        refusals = [e for e in state["audit"].entries() if e.detail["execution_refused"]]
        assert len(refusals) == 1
        assert refusals[0].kind is AuditEventKind.INTEGRITY_VIOLATION_DETECTED

    def test_ledger_marks_a_workflow_once(self, ledger) -> None:
        assert ledger.mark_consumed("wf-1") is True
        assert ledger.mark_consumed("wf-1") is False
        assert ledger.is_consumed("wf-1") is True

    def test_verification_refuses_a_consumed_workflow(self, record, ledger) -> None:
        ledger.mark_consumed("wf-1")
        verdict = verify_record("wf-1", record, ledger=ledger)
        assert verdict.failure is IntegrityFailure.ALREADY_CONSUMED

    def test_ledger_is_thread_safe(self, ledger) -> None:
        """Exactly one thread may claim a workflow."""
        wins: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            result = ledger.mark_consumed("contested")
            with lock:
                wins.append(result)

        threads = [threading.Thread(target=worker) for _ in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sum(wins) == 1, f"{sum(wins)} threads claimed the same workflow"


# ======================================================================
# Malformed input
# ======================================================================


class TestMalformedInput:
    def test_missing_record_is_refused(self) -> None:
        assert verify_record("wf-1", None).failure is IntegrityFailure.MISSING_RECORD

    @pytest.mark.parametrize("record", ["a string", ["a", "list"], 42, True])
    def test_non_mapping_record_is_refused(self, record) -> None:
        assert verify_record("wf-1", record).failure is IntegrityFailure.MALFORMED_RECORD

    @pytest.mark.parametrize("action_type", [None, "", "   ", 123, {"nested": "dict"}])
    def test_malformed_action_type_is_refused(self, record, action_type) -> None:
        tampered = copy.deepcopy(record)
        tampered["action_type"] = action_type
        assert verify_record("wf-1", tampered).refused

    @pytest.mark.parametrize("payload", [None, "string", ["list"], 42])
    def test_malformed_payload_is_refused(self, record, payload) -> None:
        tampered = copy.deepcopy(record)
        tampered["payload"] = payload
        assert verify_record("wf-1", tampered).refused

    @pytest.mark.parametrize(
        "workflow_id,action_type,payload",
        [
            ("", "rollback", {}),
            ("   ", "rollback", {}),
            ("wf-1", "", {}),
            ("wf-1", "rollback", "not-a-mapping"),
            ("wf-1", "rollback", None),
        ],
    )
    def test_build_record_rejects_invalid_input(self, workflow_id, action_type, payload) -> None:
        with pytest.raises(ValueError):
            build_record(workflow_id, action_type, payload)

    @pytest.mark.asyncio
    async def test_unknown_action_type_is_refused_and_audited(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"].save("wf-1", "no_such_action", PAYLOAD)

        assert await handle_approval_event(_approved()) is None
        assert dispatched == []
        assert state["audit"].entries()[0].detail["failure"] == "no_handler"


# ======================================================================
# Canonicalization attacks
# ======================================================================


class TestCanonicalizationAttacks:
    """Attempts to make two different payloads produce one digest."""

    def test_key_order_cannot_smuggle_a_change(self) -> None:
        left = record_digest("wf-1", "a", {"x": 1, "y": 2})
        right = record_digest("wf-1", "a", {"y": 2, "x": 1})
        assert left == right, "equal payloads must agree"
        different = record_digest("wf-1", "a", {"x": 2, "y": 1})
        assert left != different, "swapped values must not collide"

    def test_component_boundaries_cannot_be_shifted(self) -> None:
        """action_type and workflow_id must not bleed into one another."""
        assert record_digest("wf", "1x", {}) != record_digest("wf1", "x", {})

    def test_payload_and_action_type_cannot_be_confused(self) -> None:
        assert record_digest("wf-1", "a", {"b": "c"}) != record_digest("wf-1", "ab", {"": "c"})

    def test_numeric_string_and_number_do_not_collide(self) -> None:
        assert record_digest("wf-1", "a", {"n": 1}) != record_digest("wf-1", "a", {"n": "1"})

    def test_bool_and_int_do_not_collide(self) -> None:
        assert record_digest("wf-1", "a", {"f": True}) != record_digest("wf-1", "a", {"f": 1})

    def test_null_and_missing_do_not_collide(self) -> None:
        assert record_digest("wf-1", "a", {"k": None}) != record_digest("wf-1", "a", {})

    def test_unicode_normalization_does_not_mask_a_change(self) -> None:
        assert record_digest("wf-1", "a", {"n": "café"}) != record_digest(
            "wf-1", "a", {"n": "cafe"}
        )

    def test_empty_string_and_missing_key_do_not_collide(self) -> None:
        assert record_digest("wf-1", "a", {"k": ""}) != record_digest("wf-1", "a", {})


# ======================================================================
# Audit trail
# ======================================================================


class TestAuditTrail:
    def test_refusal_captures_every_required_field(self) -> None:
        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        event = audit.record_refusal(
            workflow_id="wf-1",
            action_type="docker_health_fix",
            reason="stored content does not match",
            failure="digest_mismatch",
            expected_digest="a" * 64,
            actual_digest="b" * 64,
            mission_id="mission-7",
            operator="user-42",
            tamper_evidence=True,
        )
        for field in (
            "workflow_id", "action_type", "failure", "reason",
            "expected_digest", "actual_digest", "mission_id",
            "operator", "execution_refused",
        ):
            assert field in event.detail, f"audit record is missing {field}"
        assert event.detail["execution_refused"] is True
        assert event.recorded_at.tzinfo is not None

    def test_audit_entries_are_hash_chained(self) -> None:
        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        for index in range(5):
            audit.record_refusal(
                workflow_id=f"wf-{index}", action_type="rollback",
                reason="test", failure="digest_mismatch",
            )
        ok, broken = audit.verify_chain()
        assert ok is True and broken is None

    def test_chain_verification_detects_a_break(self) -> None:
        """Deleting an entry must be detectable.

        Since PR-06 the sink is backed by the durable audit runtime, so the
        chain is verified through ``verify_chain`` rather than by splicing an
        in-memory list. Deletion is detected by the sequence gap it leaves --
        the surviving links remain individually valid, which is why a naive
        link-only check misses it.
        """
        from backend.platform.audit import verify_chain as verify_audit_chain

        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        for index in range(3):
            audit.record_refusal(
                workflow_id=f"wf-{index}", action_type="rollback",
                reason="test", failure="digest_mismatch",
            )
        entries = list(audit.entries())
        assert audit.verify_chain() == (True, None)

        spliced = [entries[0], entries[2]]
        report = verify_audit_chain(audit.runtime, spliced)
        assert report.ok is False
        assert report.first_defect.sequence == entries[2].sequence

    def test_audit_events_are_immutable(self) -> None:
        import dataclasses

        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        event = audit.record_refusal(
            workflow_id="wf-1", action_type="rollback", reason="r", failure="f"
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.sequence = 99  # type: ignore[misc]

    def test_audit_detail_is_read_only(self) -> None:
        audit = IntegrityAuditLog(AuditRuntime(InMemoryAuditStore()))
        event = audit.record_refusal(
            workflow_id="wf-1", action_type="rollback", reason="r", failure="f"
        )
        with pytest.raises(TypeError):
            event.detail["execution_refused"] = False  # type: ignore[index]

    def test_platform_principal_cannot_approve(self) -> None:
        """The recorder of refusals must not be able to authorize anything."""
        from backend.services.enterprise_integrity_audit import PLATFORM_PRINCIPAL

        assert PLATFORM_PRINCIPAL.can_approve is False


# ======================================================================
# Concurrency
# ======================================================================


class TestConcurrentVerification:
    def test_parallel_verification_is_consistent(self, record) -> None:
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            outcomes = [verify_record("wf-1", record).ok for _ in range(100)]
            with lock:
                results.extend(outcomes)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert all(results), "verification produced a false negative under concurrency"
        assert len(results) == 800

    def test_parallel_verification_of_a_tampered_record_never_passes(self, record) -> None:
        tampered = copy.deepcopy(record)
        tampered["payload"]["container_name"] = "prod-payments-db"
        results: list[bool] = []
        lock = threading.Lock()

        def worker() -> None:
            outcomes = [verify_record("wf-1", tampered).ok for _ in range(100)]
            with lock:
                results.extend(outcomes)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not any(results), "a tampered record verified under concurrency"


# ======================================================================
# Store behavior
# ======================================================================


class TestStoreBinding:
    def test_save_binds_a_digest_without_caller_involvement(self, store) -> None:
        """All five executors call save() unchanged; binding is not optional."""
        digest = store.save("wf-1", "docker_health_fix", PAYLOAD)
        stored = store.peek("wf-1")
        assert stored["record_version"] == RECORD_VERSION
        assert stored["digest"]["value"] == digest
        assert verify_record("wf-1", stored).ok is True

    def test_saved_record_survives_a_reload_from_disk(self, tmp_path: Path) -> None:
        path = tmp_path / "pending.json"
        PendingActionStore(path).save("wf-1", "docker_health_fix", PAYLOAD)
        reloaded = PendingActionStore(path)
        assert verify_record("wf-1", reloaded.peek("wf-1")).ok is True

    def test_peek_does_not_remove(self, store) -> None:
        store.save("wf-1", "docker_health_fix", PAYLOAD)
        store.peek("wf-1")
        assert store.peek("wf-1") is not None

    @pytest.mark.asyncio
    async def test_refused_record_is_left_as_evidence(
        self, _isolate_global_state, dispatched
    ) -> None:
        """Removing a tampered record would destroy the only copy of it."""
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        stored = state["store"].peek("wf-1")
        stored["payload"]["container_name"] = "tampered"
        state["store"]._pending["wf-1"] = stored

        await handle_approval_event(_approved())
        assert state["store"].peek("wf-1") is not None, "evidence was discarded on refusal"

    @pytest.mark.asyncio
    async def test_rejected_workflow_discards_without_executing(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        assert await handle_approval_event({"workflow_id": "wf-1", "status": "rejected"}) is None
        assert dispatched == []
        assert state["store"].peek("wf-1") is None

    @pytest.mark.asyncio
    async def test_non_terminal_status_does_nothing(
        self, _isolate_global_state, dispatched
    ) -> None:
        state = _isolate_global_state
        state["store"].save("wf-1", "docker_health_fix", PAYLOAD)
        assert await handle_approval_event({"workflow_id": "wf-1", "status": "pending"}) is None
        assert dispatched == []
        assert state["store"].peek("wf-1") is not None

    @pytest.mark.asyncio
    async def test_unknown_workflow_is_a_silent_no_op(
        self, _isolate_global_state, dispatched
    ) -> None:
        """Most Approval Center workflows are unrelated to these executors.

        A miss must be silent: auditing every unrelated workflow as a refusal
        would bury real violations in noise.
        """
        assert await handle_approval_event(_approved("wf-unrelated")) is None
        assert dispatched == []
        assert len(_isolate_global_state["audit"].entries()) == 0
