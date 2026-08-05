"""Serialization, deserialization, round-trip correctness, and versioning."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from backend.contracts import (
    ENVELOPE_CONTRACT_KEY,
    ENVELOPE_VERSION_KEY,
    ActionRef,
    ApprovalArtifact,
    AuditEvent,
    AuditEventKind,
    Contract,
    ContractVersionError,
    ContractViolation,
    EvidenceItem,
    EvidenceKind,
    ExecutionContract,
    ExecutionScope,
    MissionState,
    MissionTransition,
    PayloadDigest,
    SideEffectClass,
    contract_registry,
    decode_envelope,
)
from tests.contracts.conftest import NOW


class TestEnvelope:
    def test_to_dict_carries_contract_name_and_version(self, execution_contract) -> None:
        wire = execution_contract.to_dict()
        assert wire[ENVELOPE_CONTRACT_KEY] == "cortexprime.execution.contract"
        assert wire[ENVELOPE_VERSION_KEY] == 1

    def test_decode_envelope_resolves_type_without_prior_knowledge(self, execution_contract) -> None:
        decoded = decode_envelope(execution_contract.to_dict())
        assert isinstance(decoded, ExecutionContract)
        assert decoded == execution_contract

    def test_decode_envelope_rejects_unknown_contract(self) -> None:
        with pytest.raises(ContractViolation, match="unknown contract"):
            decode_envelope({ENVELOPE_CONTRACT_KEY: "cortexprime.not.real", ENVELOPE_VERSION_KEY: 1})

    def test_from_dict_rejects_mismatched_contract_name(self, execution_contract) -> None:
        wire = dict(execution_contract.to_dict())
        wire[ENVELOPE_CONTRACT_KEY] = "cortexprime.approval.artifact"
        with pytest.raises(ContractViolation, match="envelope declares"):
            ExecutionContract.from_dict(wire)


class TestRoundTrip:
    """Every registered contract must survive to_dict -> from_dict unchanged."""

    def test_all_registered_contracts_are_discoverable(self) -> None:
        registry = contract_registry()
        assert len(registry) >= 30
        for name, contract_type in registry.items():
            assert issubclass(contract_type, Contract)
            assert contract_type.CONTRACT_NAME == name

    @pytest.mark.parametrize(
        "fixture_name",
        [
            "tenant",
            "organization",
            "project",
            "scope",
            "human",
            "security_context",
            "reversible_action",
            "execution_scope",
            "execution_contract",
            "digest",
            "approval_artifact",
            "citation",
        ],
    )
    def test_round_trip_preserves_equality(self, request, fixture_name: str) -> None:
        original = request.getfixturevalue(fixture_name)
        restored = type(original).from_dict(original.to_dict())
        assert restored == original

    def test_round_trip_through_json(self, approval_artifact) -> None:
        """Serialized form must be JSON-safe -- it crosses process boundaries."""
        encoded = json.dumps(approval_artifact.to_dict())
        restored = ApprovalArtifact.from_dict(json.loads(encoded))
        assert restored == approval_artifact

    def test_nested_contracts_round_trip(self, approval_artifact) -> None:
        restored = ApprovalArtifact.from_dict(approval_artifact.to_dict())
        assert restored.execution.action.parameters["container"] == "web-01"
        assert restored.scope.project is not None
        assert restored.scope.project.project_id == "proj-checkout"

    def test_optional_field_absent_round_trips_as_none(self, execution_scope) -> None:
        read_only = ExecutionContract(
            execution_key="inspect-web-01",
            action=ActionRef("docker.inspect", {"container": "web-01"}),
            scope=execution_scope,
            side_effect_class=SideEffectClass.READ,
            verification_criteria=("inspect returned",),
        )
        restored = ExecutionContract.from_dict(read_only.to_dict())
        assert restored.inverse is None
        assert restored == read_only

    def test_empty_tuple_round_trips_as_tuple_not_list(self, human, scope) -> None:
        from backend.contracts import SecurityContext

        context = SecurityContext(principal=human, scope=scope)
        restored = SecurityContext.from_dict(context.to_dict())
        assert restored.capabilities == ()
        assert isinstance(restored.capabilities, tuple)


class TestDeterminism:
    """to_dict output feeds canonical hashing (PR-02); it must be stable."""

    def test_repeated_serialization_is_identical(self, execution_contract) -> None:
        assert execution_contract.to_dict() == execution_contract.to_dict()

    def test_equal_contracts_serialize_identically(self, execution_scope, reversible_action) -> None:
        def build() -> ExecutionContract:
            return ExecutionContract(
                execution_key="k",
                action=reversible_action,
                scope=execution_scope,
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                inverse=reversible_action,
                verification_criteria=("ok",),
            )

        assert build().to_dict() == build().to_dict()

    def test_field_order_follows_declaration_order(self, execution_scope) -> None:
        wire = execution_scope.to_dict()
        keys = [key for key in wire if not key.startswith("_")]
        assert keys == ["system", "resources", "environment"]

    def test_datetime_is_normalized_to_utc_iso8601(self) -> None:
        from datetime import timedelta

        offset = timezone(timedelta(hours=5, minutes=30))
        local = datetime(2030, 1, 1, 17, 30, tzinfo=offset)
        transition = MissionTransition(
            mission=__import__(
                "backend.contracts", fromlist=["MissionRef"]
            ).MissionRef("m-1"),
            from_state=MissionState.RECEIVED,
            to_state=MissionState.INTERPRETED,
            reason="parsed",
            occurred_at=local,
            sequence=0,
        )
        assert transition.to_dict()["occurred_at"] == "2030-01-01T12:00:00+00:00"


class TestVersionCompatibility:
    def test_payload_from_a_newer_version_is_refused(self, execution_contract) -> None:
        wire = dict(execution_contract.to_dict())
        wire[ENVELOPE_VERSION_KEY] = ExecutionContract.CONTRACT_VERSION + 1
        with pytest.raises(ContractVersionError, match="understands at most"):
            ExecutionContract.from_dict(wire)

    def test_payload_from_an_older_version_is_accepted(self, execution_contract) -> None:
        """Evolution is additive-only, so older payloads are a valid subset."""
        wire = dict(execution_contract.to_dict())
        wire[ENVELOPE_VERSION_KEY] = 0
        assert ExecutionContract.from_dict(wire) == execution_contract

    def test_unknown_field_in_payload_is_ignored(self, execution_scope) -> None:
        """Forward compatibility: a newer peer may send fields we do not know."""
        wire = dict(execution_scope.to_dict())
        wire["field_added_in_a_later_release"] = "value"
        assert ExecutionScope.from_dict(wire) == execution_scope

    def test_missing_required_field_is_refused(self, execution_scope) -> None:
        wire = dict(execution_scope.to_dict())
        del wire["system"]
        with pytest.raises(ContractViolation, match="missing required field"):
            ExecutionScope.from_dict(wire)

    def test_envelope_version_must_be_an_integer(self, execution_scope) -> None:
        wire = dict(execution_scope.to_dict())
        wire[ENVELOPE_VERSION_KEY] = "1"
        with pytest.raises(ContractViolation, match="must be an integer"):
            ExecutionScope.from_dict(wire)


class TestDecodingRejectsMalformedInput:
    def test_wrong_scalar_type_is_refused(self, execution_scope) -> None:
        wire = dict(execution_scope.to_dict())
        wire["system"] = 42
        with pytest.raises(ContractViolation, match="expected str"):
            ExecutionScope.from_dict(wire)

    def test_invalid_enum_value_is_refused(self, execution_contract) -> None:
        wire = dict(execution_contract.to_dict())
        wire["side_effect_class"] = "catastrophic"
        with pytest.raises(ContractViolation, match="not a valid SideEffectClass"):
            ExecutionContract.from_dict(wire)

    def test_naive_datetime_string_is_refused(self, citation) -> None:
        wire = dict(citation.to_dict())
        wire["observed_at"] = "2030-01-01T12:00:00"
        with pytest.raises(ContractViolation, match="must carry a timezone"):
            type(citation).from_dict(wire)

    def test_non_mapping_input_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="expected a mapping"):
            ExecutionScope.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_naive_datetime_cannot_be_serialized(self, execution_scope) -> None:
        """Guards the encoder as well as the decoder."""
        audit = AuditEvent(
            event_id="e-1",
            kind=AuditEventKind.EXECUTION_REFUSED,
            scope=__import__("backend.contracts", fromlist=["TenantScope"]).TenantScope(
                tenant=__import__("backend.contracts", fromlist=["TenantRef"]).TenantRef("t")
            ),
            recorded_at=NOW,
            sequence=0,
            entry_digest=PayloadDigest(
                algorithm=__import__(
                    "backend.contracts", fromlist=["HashAlgorithm"]
                ).HashAlgorithm.SHA256,
                value="c" * 64,
            ),
        )
        object.__setattr__(audit, "recorded_at", datetime(2030, 1, 1, 12, 0))
        with pytest.raises(ContractViolation, match="naive datetime"):
            audit.to_dict()


class TestEvidenceSerialization:
    def test_evidence_item_round_trips(self, citation) -> None:
        item = EvidenceItem(
            kind=EvidenceKind.METRIC,
            citation=citation,
            excerpt="error_rate=0.12",
            summary="error rate 12%",
        )
        assert EvidenceItem.from_dict(item.to_dict()) == item
