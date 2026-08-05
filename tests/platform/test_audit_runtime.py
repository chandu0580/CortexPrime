"""Durable audit runtime: append-only semantics, chain integrity, recovery.

The property under test throughout: **a chain that has been altered cannot be
made to verify.** Tests are organized by defect class, because an auditor's
question is "what kind of damage would this catch?", not "which method was
called".
"""

from __future__ import annotations

import dataclasses
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.contracts import (
    AuditEvent,
    AuditEventKind,
    PrincipalKind,
    PrincipalRef,
    TenantRef,
    TenantScope,
)
from backend.platform.audit import (
    AUDIT_SCHEMA_VERSION,
    AgeBasedRetention,
    AuditCorruptionError,
    AuditQuery,
    AuditRuntime,
    AuditStore,
    DefectKind,
    InMemoryAuditStore,
    JsonlAuditStore,
    KeepForever,
    export_chain,
    plan_retention,
    verify_chain,
    verify_export,
)

NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def scope() -> TenantScope:
    return TenantScope(tenant=TenantRef(tenant_id="tenant-alpha"))


@pytest.fixture
def actor() -> PrincipalRef:
    return PrincipalRef(principal_id="user-42", kind=PrincipalKind.HUMAN)


@pytest.fixture
def runtime() -> AuditRuntime:
    return AuditRuntime(InMemoryAuditStore())


@pytest.fixture
def durable(tmp_path: Path) -> AuditRuntime:
    return AuditRuntime(JsonlAuditStore(tmp_path / "audit.jsonl"))


def _fill(runtime: AuditRuntime, scope: TenantScope, count: int = 5, **kwargs) -> list:
    return [
        runtime.record(
            AuditEventKind.EXECUTION_REFUSED,
            scope,
            subject_reference=f"wf-{index}",
            detail={"index": index},
            **kwargs,
        )
        for index in range(count)
    ]


class TestAppendOnlySemantics:
    def test_store_protocol_exposes_no_mutation(self) -> None:
        """Append-only is enforced by absence, not by convention."""
        for forbidden in ("update", "delete", "remove", "set", "replace", "truncate"):
            assert not hasattr(AuditStore, forbidden), f"AuditStore exposes {forbidden}"

    def test_records_are_immutable(self, runtime, scope) -> None:
        record = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.sequence = 99  # type: ignore[misc]

    def test_record_detail_is_read_only(self, runtime, scope) -> None:
        record = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope, detail={"a": 1})
        with pytest.raises(TypeError):
            record.detail["a"] = 2  # type: ignore[index]

    def test_sequences_are_contiguous_from_zero(self, runtime, scope) -> None:
        records = _fill(runtime, scope, 10)
        assert [record.sequence for record in records] == list(range(10))

    def test_first_record_has_no_predecessor(self, runtime, scope) -> None:
        record = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        assert record.sequence == 0
        assert record.previous_digest is None
        assert record.is_genesis

    def test_each_record_links_to_its_predecessor(self, runtime, scope) -> None:
        records = _fill(runtime, scope, 5)
        for previous, current in zip(records, records[1:]):
            assert current.links_to(previous)


class TestRequiredFields:
    def test_every_required_field_is_present(self, runtime, scope, actor) -> None:
        record = runtime.record(
            AuditEventKind.EXECUTION_REFUSED,
            scope,
            subject_reference="wf-1",
            actor=actor,
            correlation_id="corr-1",
            detail={"failure": "digest_mismatch"},
        )
        assert record.event_id                      # audit id
        assert record.previous_digest is None       # previous hash (genesis)
        assert record.entry_digest.value            # current hash
        assert record.recorded_at.tzinfo is not None  # timestamp
        assert record.actor is actor                # actor
        assert record.scope.tenant.tenant_id        # tenant
        assert record.correlation_id == "corr-1"    # correlation id
        assert record.kind is AuditEventKind.EXECUTION_REFUSED  # event type
        assert record.detail["schema_version"] == AUDIT_SCHEMA_VERSION  # schema version

    def test_causation_links_records(self, runtime, scope) -> None:
        first = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        second = runtime.record(
            AuditEventKind.EXECUTION_STARTED, scope, causation_id=first.event_id
        )
        assert second.causation_id == first.event_id

    def test_payload_digest_is_recorded_when_supplied(self, runtime, scope) -> None:
        from backend.platform.hashing import compute_digest

        digest = compute_digest({"container": "web-01"})
        record = runtime.record(AuditEventKind.EXECUTION_STARTED, scope, payload_digest=digest)
        assert record.payload_digest == digest

    @pytest.mark.parametrize(
        "kind",
        [
            AuditEventKind.MISSION_TRANSITIONED,
            AuditEventKind.APPROVAL_GRANTED,
            AuditEventKind.EXECUTION_STARTED,
            AuditEventKind.POLICY_EVALUATED,
            AuditEventKind.VERIFICATION_RECORDED,
            AuditEventKind.INTEGRITY_VIOLATION_DETECTED,
            AuditEventKind.REPLAY_ATTEMPT_DETECTED,
            AuditEventKind.CONFIGURATION_CHANGED,
            AuditEventKind.IDENTITY_EVENT,
            AuditEventKind.CONNECTOR_OPERATION,
        ],
    )
    def test_every_required_event_category_is_supported(self, runtime, scope, kind) -> None:
        assert runtime.record(kind, scope).kind is kind


class TestChainVerification:
    def test_clean_chain_verifies(self, runtime, scope) -> None:
        _fill(runtime, scope, 20)
        report = verify_chain(runtime)
        assert report.ok
        assert report.records_checked == 20
        assert report.defects == ()

    def test_empty_chain_verifies(self, runtime) -> None:
        assert verify_chain(runtime).ok

    def test_report_carries_the_head_digest(self, runtime, scope) -> None:
        records = _fill(runtime, scope, 3)
        assert verify_chain(runtime).head_digest == records[-1].entry_digest.value

    def test_large_chain_verifies(self, runtime, scope) -> None:
        _fill(runtime, scope, 2000)
        report = verify_chain(runtime)
        assert report.ok
        assert report.records_checked == 2000


class TestTamperDetection:
    def _tamper(self, runtime, index: int, **changes) -> list:
        records = list(runtime.query())
        records[index] = dataclasses.replace(records[index], **changes)
        return records

    def test_edited_detail_is_detected(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        altered = self._tamper(runtime, 2, detail={"index": 999})
        report = verify_chain(runtime, altered)
        assert not report.ok
        assert report.first_defect.kind == DefectKind.TAMPERED
        assert report.first_defect.sequence == 2

    def test_edited_subject_is_detected(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        altered = self._tamper(runtime, 1, subject_reference="wf-forged")
        assert verify_chain(runtime, altered).first_defect.kind == DefectKind.TAMPERED

    def test_edited_timestamp_is_detected(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        altered = self._tamper(runtime, 3, recorded_at=NOW)
        assert verify_chain(runtime, altered).first_defect.kind == DefectKind.TAMPERED

    def test_edited_actor_is_detected(self, runtime, scope, actor) -> None:
        _fill(runtime, scope, 5)
        altered = self._tamper(runtime, 0, actor=actor)
        assert verify_chain(runtime, altered).first_defect.kind == DefectKind.TAMPERED

    def test_edited_correlation_is_detected(self, runtime, scope) -> None:
        _fill(runtime, scope, 5, correlation_id="corr-1")
        altered = self._tamper(runtime, 2, correlation_id="corr-forged")
        assert verify_chain(runtime, altered).first_defect.kind == DefectKind.TAMPERED

    def test_verification_reports_every_defect_not_just_the_first(self, runtime, scope) -> None:
        """An operator investigating needs the full extent of the damage."""
        _fill(runtime, scope, 6)
        records = list(runtime.query())
        records[1] = dataclasses.replace(records[1], detail={"x": 1})
        records[4] = dataclasses.replace(records[4], detail={"x": 2})
        report = verify_chain(runtime, records)
        tampered = [d for d in report.defects if d.kind == DefectKind.TAMPERED]
        assert len(tampered) == 2


class TestMissingRecordDetection:
    def test_deleted_middle_record_is_detected(self, runtime, scope) -> None:
        """The defect a naive link check misses entirely."""
        _fill(runtime, scope, 6)
        records = list(runtime.query())
        del records[3]
        report = verify_chain(runtime, records)
        assert not report.ok
        kinds = {defect.kind for defect in report.defects}
        assert DefectKind.MISSING_RECORD in kinds

    def test_deleted_record_count_is_reported(self, runtime, scope) -> None:
        _fill(runtime, scope, 10)
        records = list(runtime.query())
        del records[3:6]
        report = verify_chain(runtime, records)
        missing = [d for d in report.defects if d.kind == DefectKind.MISSING_RECORD]
        assert missing and "3 record(s) deleted" in missing[0].detail

    def test_truncated_prefix_is_detected_when_origin_expected(self, runtime, scope) -> None:
        _fill(runtime, scope, 6)
        report = verify_chain(runtime, list(runtime.query())[2:])
        assert not report.ok
        assert report.first_defect.kind == DefectKind.MISSING_RECORD

    def test_truncated_prefix_is_accepted_as_a_slice(self, runtime, scope) -> None:
        """A legitimately archived prefix must not read as tampering."""
        _fill(runtime, scope, 6)
        report = verify_chain(runtime, list(runtime.query())[2:], expect_origin=False)
        assert report.ok

    def test_reordered_records_are_detected(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        records = list(runtime.query())
        records[1], records[2] = records[2], records[1]
        report = verify_chain(runtime, records)
        assert not report.ok
        kinds = {defect.kind for defect in report.defects}
        assert kinds & {DefectKind.OUT_OF_ORDER, DefectKind.BROKEN_LINK}

    def test_substituted_record_breaks_the_link(self, runtime, scope) -> None:
        """Splicing in a record from another chain must not verify."""
        _fill(runtime, scope, 5)
        records = list(runtime.query())

        other = AuditRuntime(InMemoryAuditStore())
        _fill(other, scope, 5)
        foreign = list(other.query())[2]

        records[2] = foreign
        report = verify_chain(runtime, records)
        assert not report.ok
        assert DefectKind.BROKEN_LINK in {defect.kind for defect in report.defects}


class TestDurability:
    def test_records_survive_process_restart(self, tmp_path, scope) -> None:
        path = tmp_path / "audit.jsonl"
        first = AuditRuntime(JsonlAuditStore(path))
        _fill(first, scope, 5)
        head = first.head_digest

        second = AuditRuntime(JsonlAuditStore(path))
        assert second.count() == 5
        assert second.head_digest == head
        assert second.next_sequence == 5

    def test_chain_continues_after_restart(self, tmp_path, scope) -> None:
        """A restart must extend the chain, not fork a second one."""
        path = tmp_path / "audit.jsonl"
        first = AuditRuntime(JsonlAuditStore(path))
        _fill(first, scope, 3)

        second = AuditRuntime(JsonlAuditStore(path))
        _fill(second, scope, 3)

        report = verify_chain(second)
        assert report.ok
        assert report.records_checked == 6
        assert [r.sequence for r in second.query()] == list(range(6))

    def test_file_is_append_only_on_disk(self, tmp_path, scope) -> None:
        path = tmp_path / "audit.jsonl"
        runtime = AuditRuntime(JsonlAuditStore(path))
        _fill(runtime, scope, 3)
        first_bytes = path.read_bytes()

        _fill(runtime, scope, 2)
        second_bytes = path.read_bytes()

        assert second_bytes.startswith(first_bytes), "an earlier region of the file was rewritten"

    def test_one_json_object_per_line(self, tmp_path, scope) -> None:
        path = tmp_path / "audit.jsonl"
        runtime = AuditRuntime(JsonlAuditStore(path))
        _fill(runtime, scope, 4)
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 4
        for line in lines:
            assert json.loads(line)["_contract"] == "cortexprime.audit.event"

    def test_corrupted_line_is_reported_with_its_location(self, tmp_path, scope) -> None:
        """Corruption fails loudly at construction, naming the damaged line.

        Starting a fresh chain instead would leave two chains in one store --
        verifiable as neither -- and quietly discard the prior evidence.
        """
        path = tmp_path / "audit.jsonl"
        runtime = AuditRuntime(JsonlAuditStore(path))
        _fill(runtime, scope, 3)

        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{not valid json\n")

        with pytest.raises(AuditCorruptionError) as excinfo:
            AuditRuntime(JsonlAuditStore(path))
        assert excinfo.value.line_number == 4

    def test_torn_final_line_does_not_destroy_earlier_records(self, tmp_path, scope) -> None:
        """A crash mid-write damages at most the last line."""
        path = tmp_path / "audit.jsonl"
        runtime = AuditRuntime(JsonlAuditStore(path))
        _fill(runtime, scope, 3)

        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

        recovered = AuditRuntime(JsonlAuditStore(path))
        assert recovered.count() == 2
        assert verify_chain(recovered).ok


class TestConcurrency:
    def test_concurrent_appends_produce_one_linear_chain(self, runtime, scope) -> None:
        def worker() -> None:
            for _ in range(100):
                runtime.record(AuditEventKind.EXECUTION_STARTED, scope)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        records = list(runtime.query())
        assert len(records) == 800
        assert [r.sequence for r in records] == list(range(800)), "sequences forked or collided"
        assert verify_chain(runtime).ok

    def test_concurrent_durable_appends_verify(self, tmp_path, scope) -> None:
        runtime = AuditRuntime(JsonlAuditStore(tmp_path / "audit.jsonl"))

        def worker() -> None:
            for _ in range(50):
                runtime.record(AuditEventKind.EXECUTION_STARTED, scope)

        threads = [threading.Thread(target=worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert runtime.count() == 300
        assert verify_chain(runtime).ok

    def test_event_ids_are_unique_under_concurrency(self, runtime, scope) -> None:
        def worker() -> None:
            for _ in range(100):
                runtime.record(AuditEventKind.EXECUTION_STARTED, scope)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        ids = [record.event_id for record in runtime.query()]
        assert len(set(ids)) == len(ids)


class TestQuery:
    def test_filter_by_kind(self, runtime, scope) -> None:
        runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        _fill(runtime, scope, 3)
        results = runtime.query(AuditQuery(kinds=frozenset({AuditEventKind.APPROVAL_GRANTED})))
        assert len(results) == 1

    def test_filter_by_correlation(self, runtime, scope) -> None:
        _fill(runtime, scope, 3, correlation_id="incident-1")
        _fill(runtime, scope, 2, correlation_id="incident-2")
        assert len(runtime.query(AuditQuery(correlation_id="incident-1"))) == 3

    def test_filter_by_security_relevance(self, runtime, scope) -> None:
        runtime.record(AuditEventKind.EXECUTION_STARTED, scope)
        runtime.record(AuditEventKind.INTEGRITY_VIOLATION_DETECTED, scope)
        runtime.record(AuditEventKind.REPLAY_ATTEMPT_DETECTED, scope)
        assert len(runtime.query(AuditQuery(security_relevant_only=True))) == 2

    def test_filter_by_actor(self, runtime, scope, actor) -> None:
        runtime.record(AuditEventKind.APPROVAL_GRANTED, scope, actor=actor)
        runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        assert len(runtime.query(AuditQuery(actor_id="user-42"))) == 1

    def test_filter_by_sequence_range(self, runtime, scope) -> None:
        _fill(runtime, scope, 10)
        assert len(runtime.query(AuditQuery(min_sequence=3, max_sequence=6))) == 4

    def test_filter_by_tenant(self, runtime, scope) -> None:
        other = TenantScope(tenant=TenantRef(tenant_id="tenant-beta"))
        _fill(runtime, scope, 3)
        runtime.record(AuditEventKind.APPROVAL_GRANTED, other)
        assert len(runtime.query(AuditQuery(tenant_id="tenant-beta"))) == 1

    def test_limit_caps_results(self, runtime, scope) -> None:
        _fill(runtime, scope, 20)
        assert len(runtime.query(AuditQuery(limit=5))) == 5

    def test_filter_by_time_window(self, runtime, scope) -> None:
        _fill(runtime, scope, 3)
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        assert len(runtime.query(AuditQuery(since=future))) == 0


class TestExport:
    def test_export_round_trips_and_verifies(self, runtime, scope) -> None:
        _fill(runtime, scope, 10)
        assert verify_export(runtime, export_chain(runtime)).ok

    def test_export_carries_a_manifest(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        manifest = json.loads(export_chain(runtime).splitlines()[0])
        assert manifest["_manifest"] is True
        assert manifest["record_count"] == 5
        assert manifest["head_digest"] == runtime.head_digest.value

    def test_tampered_export_fails_verification(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        exported = export_chain(runtime).replace("wf-2", "wf-forged")
        assert not verify_export(runtime, exported).ok

    def test_export_with_a_deleted_record_fails_the_manifest_check(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        lines = export_chain(runtime).splitlines()
        del lines[3]
        assert not verify_export(runtime, "\n".join(lines) + "\n").ok

    def test_export_missing_its_manifest_fails(self, runtime, scope) -> None:
        _fill(runtime, scope, 3)
        lines = export_chain(runtime).splitlines()[1:]
        assert not verify_export(runtime, "\n".join(lines) + "\n").ok

    def test_empty_export_verifies(self, runtime) -> None:
        assert verify_export(runtime, export_chain(runtime)).ok


class TestRetention:
    def test_keep_forever_retains_everything(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        decision = plan_retention(list(runtime.query()), KeepForever())
        assert decision.retirable_count == 0
        assert decision.safe

    def test_age_based_retires_a_contiguous_prefix(self, runtime, scope) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=400)
        for index in range(3):
            runtime.record(
                AuditEventKind.EXECUTION_STARTED, scope, recorded_at=old + timedelta(seconds=index)
            )
        _fill(runtime, scope, 2)

        decision = plan_retention(list(runtime.query()), AgeBasedRetention(retain_days=30))
        assert decision.safe
        assert decision.retirable_count == 3
        assert decision.retain_from_sequence == 3

    def test_security_records_are_retained_longer(self, runtime, scope) -> None:
        old = datetime.now(timezone.utc) - timedelta(days=400)
        runtime.record(AuditEventKind.INTEGRITY_VIOLATION_DETECTED, scope, recorded_at=old)
        decision = plan_retention(list(runtime.query()), AgeBasedRetention(retain_days=30))
        assert decision.retirable_count == 0, "security evidence was retired early"

    def test_non_contiguous_retirement_is_refused(self, runtime, scope) -> None:
        """Archiving a hole is indistinguishable from tampering."""
        old = datetime.now(timezone.utc) - timedelta(days=400)
        runtime.record(AuditEventKind.EXECUTION_STARTED, scope, recorded_at=old)
        runtime.record(AuditEventKind.EXECUTION_STARTED, scope)
        runtime.record(AuditEventKind.EXECUTION_STARTED, scope, recorded_at=old)

        decision = plan_retention(list(runtime.query()), AgeBasedRetention(retain_days=30))
        assert not decision.safe
        assert "hole in the chain" in decision.reason

    def test_plan_does_not_mutate(self, runtime, scope) -> None:
        _fill(runtime, scope, 5)
        plan_retention(list(runtime.query()), AgeBasedRetention(retain_days=1))
        assert runtime.count() == 5

    def test_security_retention_below_routine_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least retain_days"):
            AgeBasedRetention(retain_days=100, security_retain_days=10)

    def test_zero_retain_days_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least 1"):
            AgeBasedRetention(retain_days=0)


class TestVersionCompatibility:
    def test_records_carry_a_schema_version(self, runtime, scope) -> None:
        record = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        assert record.detail["schema_version"] == AUDIT_SCHEMA_VERSION

    def test_records_without_the_new_optional_fields_still_decode(self, runtime, scope) -> None:
        """PR-05-era entries lack correlation, causation, and payload digest."""
        record = runtime.record(AuditEventKind.APPROVAL_GRANTED, scope)
        wire = dict(record.to_dict())
        for field in ("correlation_id", "causation_id", "payload_digest"):
            wire.pop(field, None)
        restored = AuditEvent.from_dict(wire)
        assert restored.correlation_id is None
        assert restored.payload_digest is None

    def test_stored_records_round_trip_through_the_wire_format(self, runtime, scope, actor) -> None:
        original = runtime.record(
            AuditEventKind.EXECUTION_REFUSED,
            scope,
            actor=actor,
            correlation_id="corr-1",
            subject_reference="wf-1",
            detail={"failure": "digest_mismatch"},
        )
        assert AuditEvent.from_dict(original.to_dict()) == original
