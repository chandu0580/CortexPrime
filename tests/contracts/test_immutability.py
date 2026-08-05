"""Contracts are immutable.

Mutability in a shared vocabulary means one context can alter a value another
context is relying on. In the approval path specifically, a mutable payload is
the difference between a binding and a suggestion (Constitution I2).
"""

from __future__ import annotations

import dataclasses

import pytest

from backend.contracts import (
    ActionRef,
    ContractViolation,
    ExecutionScope,
    SecurityContext,
    contract_registry,
    freeze_mapping,
)


class TestFrozenDataclasses:
    @pytest.mark.parametrize(
        "contract_type", list(contract_registry().values()), ids=lambda t: t.CONTRACT_NAME
    )
    def test_every_contract_is_a_frozen_dataclass(self, contract_type) -> None:
        assert dataclasses.is_dataclass(contract_type), f"{contract_type.__name__} is not a dataclass"
        params = contract_type.__dataclass_params__
        assert params.frozen, f"{contract_type.__name__} must be declared frozen=True"

    def test_assigning_to_a_field_raises(self, execution_scope: ExecutionScope) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            execution_scope.system = "kubernetes"  # type: ignore[misc]

    def test_deleting_a_field_raises(self, execution_scope: ExecutionScope) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            del execution_scope.system  # type: ignore[misc]

    def test_contracts_are_hashable(self, execution_scope: ExecutionScope) -> None:
        """Frozen dataclasses hash by value, so contracts work as dict keys."""
        assert {execution_scope: "ok"}[execution_scope] == "ok"

    def test_contracts_carrying_an_opaque_mapping_are_hashable(self) -> None:
        """Regression: MappingProxyType is not hashable, which silently made every
        mapping-bearing contract unhashable despite being frozen. Found in PR-03;
        fixed by returning a hashable FrozenDict from freeze_mapping."""
        action = ActionRef(action_type="docker.restart", parameters={"container": "web-01"})
        assert {action: "ok"}[action] == "ok"
        assert len({action, ActionRef("docker.restart", {"container": "web-01"})}) == 1

    def test_opaque_mapping_hash_ignores_key_insertion_order(self) -> None:
        left = ActionRef("a", {"x": 1, "y": 2})
        right = ActionRef("a", {"y": 2, "x": 1})
        assert left == right
        assert hash(left) == hash(right)

    def test_nested_structures_in_an_opaque_mapping_are_hashable(self) -> None:
        action = ActionRef("a", {"nested": {"b": [1, 2]}, "list": [{"c": 3}]})
        assert isinstance(hash(action), int)

    def test_equality_is_by_value(self) -> None:
        left = ExecutionScope(system="docker", resources=("a",), environment="production")
        right = ExecutionScope(system="docker", resources=("a",), environment="production")
        assert left == right
        assert hash(left) == hash(right)


class TestCollectionsAreImmutable:
    def test_sequence_fields_reject_lists(self) -> None:
        with pytest.raises(ContractViolation, match="must be a tuple"):
            SecurityContext(
                principal=__import__("backend.contracts", fromlist=["PrincipalRef"]).PrincipalRef(
                    principal_id="p",
                    kind=__import__(
                        "backend.contracts", fromlist=["PrincipalKind"]
                    ).PrincipalKind.HUMAN,
                ),
                scope=__import__("backend.contracts", fromlist=["TenantScope"]).TenantScope(
                    tenant=__import__("backend.contracts", fromlist=["TenantRef"]).TenantRef("t")
                ),
                capabilities=["mission:create"],  # type: ignore[arg-type]
            )

    def test_sequence_fields_cannot_be_appended_to(self, execution_scope: ExecutionScope) -> None:
        with pytest.raises(AttributeError):
            execution_scope.resources.append("web-02")  # type: ignore[attr-defined]

    def test_opaque_mapping_is_frozen_on_construction(self) -> None:
        mutable = {"container": "web-01"}
        action = ActionRef(action_type="docker.restart", parameters=mutable)
        with pytest.raises(TypeError):
            action.parameters["container"] = "web-02"  # type: ignore[index]

    def test_mutating_the_source_dict_does_not_affect_the_contract(self) -> None:
        """Construction copies -- a caller keeping a reference cannot reach in."""
        source = {"container": "web-01"}
        action = ActionRef(action_type="docker.restart", parameters=source)
        source["container"] = "web-99"
        assert action.parameters["container"] == "web-01"

    def test_decoded_mapping_is_also_frozen(self) -> None:
        action = ActionRef(action_type="docker.restart", parameters={"container": "web-01"})
        restored = ActionRef.from_dict(action.to_dict())
        with pytest.raises(TypeError):
            restored.parameters["container"] = "web-02"  # type: ignore[index]


class TestFreezeMapping:
    def test_none_normalizes_to_empty_mapping(self) -> None:
        frozen = freeze_mapping(None)
        assert dict(frozen) == {}
        with pytest.raises(TypeError):
            frozen["k"] = "v"  # type: ignore[index]

    def test_rejects_non_mapping(self) -> None:
        with pytest.raises(ContractViolation, match="expected a mapping"):
            freeze_mapping(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_already_frozen_mapping_is_returned_as_is(self) -> None:
        frozen = freeze_mapping({"a": 1})
        assert freeze_mapping(frozen) is frozen
