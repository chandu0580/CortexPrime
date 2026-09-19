"""A delegated approval authorizes only a compensable capability (ADR-124).

Phase 11.4 records an earned-autonomy decision in the ONE approval authority as
an approval decided by ``policy:autonomy/...``. The rule that keeps that from
becoming a way around L10 lives in authorization, below every caller: a
non-human decider's approval is valid only for a capability whose contract
declares a compensation and that is not DESTRUCTIVE. For the rollout restart --
irreversible, no compensation -- it authorizes nothing, however valid the rest
of the approval is.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.contexts.connectivity.application.authorization import ApprovalFacts, CapabilityAuthorizationService
from backend.contexts.connectivity.domain.authorization import AuthorizationRequest, CapabilityOperation
from backend.contexts.connectivity.domain.identifiers import CapabilityRef
from backend.contracts.approval import ApprovalOutcome
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.identity import PrincipalKind, PrincipalRef

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)


class _Lookup:
    def __init__(self, facts):
        self.facts = facts

    def find(self, context, artifact_id):
        return self.facts


def _definition(*, compensation, side_effect=SideEffectClass.IRREVERSIBLE_WRITE, ref="platform.kubernetes.deployment.rollback@1"):
    contract = SimpleNamespace(side_effect_class=side_effect, effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
                               supported_environments=(), required_permissions=(),
                               compensation_capability=compensation)
    return SimpleNamespace(digest="capdigest", status=None, trust=None, owner=SimpleNamespace(principal_id="owner"),
                           tenancy=SimpleNamespace(value="platform"),
                           source=SimpleNamespace(value="internal", is_self_declared=False),
                           contract=contract, reference=CapabilityRef.parse(ref))


def _facts(decided_by):
    return ApprovalFacts(artifact_id="appr_1", outcome=ApprovalOutcome.GRANTED, bound_digest="capdigest",
                         scope_tenant_id="tenant-a", bound_action_digest="approval-digest", operation="invoke",
                         expires_at=NOW + timedelta(minutes=10), decided_by=decided_by)


def _snapshot(facts, definition):
    service = CapabilityAuthorizationService(registry=None, approvals=_Lookup(facts))
    request = AuthorizationRequest(
        tenant_id="tenant-a", principal=PrincipalRef(principal_id="remediation-runtime", kind=PrincipalKind.PLATFORM),
        capability_ref=definition.reference, operation=CapabilityOperation.INVOKE, expected_digest="capdigest",
        approval_artifact_id="appr_1")
    context = SimpleNamespace(tenant_id="tenant-a", identity=SimpleNamespace(capabilities=("capability:invoke",)))
    return service._snapshot(context, request, definition, NOW)


@pytest.mark.parametrize("decider", ["human:approver@example.com", None])
def test_a_human_decided_approval_is_valid_for_any_capability_it_covers(decider):
    restart = _definition(compensation=None, ref="platform.kubernetes.workload.rollout_restart@1")
    assert _snapshot(_facts(decider), restart).approval_valid is True


def test_a_policy_decided_approval_is_valid_for_a_compensable_capability():
    rollback = _definition(compensation="platform.kubernetes.deployment.rollback")
    snapshot = _snapshot(_facts("policy:autonomy/phase114-autonomy/1"), rollback)
    assert snapshot.approval_valid is True and snapshot.approval_bound_digest == "approval-digest"


def test_a_policy_decided_approval_authorizes_nothing_for_an_irreversible_capability():
    restart = _definition(compensation=None, ref="platform.kubernetes.workload.rollout_restart@1")
    snapshot = _snapshot(_facts("policy:autonomy/phase114-autonomy/1"), restart)
    assert snapshot.approval_present is True and snapshot.approval_valid is False


def test_a_policy_decided_approval_authorizes_nothing_for_a_destructive_capability():
    destructive = _definition(compensation="platform.something.restore", side_effect=SideEffectClass.DESTRUCTIVE)
    assert _snapshot(_facts("policy:autonomy/phase114-autonomy/1"), destructive).approval_valid is False


def test_the_delegation_flag_is_derived_from_the_stored_decider():
    assert _facts("policy:autonomy/x").is_delegated is True
    assert _facts("human:someone").is_delegated is False
    assert _facts(None).is_delegated is False


def test_a_service_composed_without_an_approval_store_says_so():
    """F-4: a process whose authorization has no approval store refuses every
    approval. That must be observable, so a remediator never starts on it."""
    assert CapabilityAuthorizationService(registry=None).has_approval_authority is False
    assert CapabilityAuthorizationService(registry=None, approvals=_Lookup(None)).has_approval_authority is True


def test_without_an_approval_store_a_valid_human_approval_is_not_found():
    restart = _definition(compensation=None, ref="platform.kubernetes.workload.rollout_restart@1")
    service = CapabilityAuthorizationService(registry=None)
    request = AuthorizationRequest(
        tenant_id="tenant-a", principal=PrincipalRef(principal_id="remediation-runtime", kind=PrincipalKind.PLATFORM),
        capability_ref=restart.reference, operation=CapabilityOperation.INVOKE, expected_digest="capdigest",
        approval_artifact_id="appr_1")
    context = SimpleNamespace(tenant_id="tenant-a", identity=SimpleNamespace(capabilities=("capability:invoke",)))
    snapshot = service._snapshot(context, request, restart, NOW)
    assert snapshot.approval_present is False and snapshot.approval_valid is False


@pytest.mark.parametrize("decider", ["human:approver@example.com", "policy:autonomy/v1+compensable=1"])
def test_a_consumed_approval_authorizes_nothing_again(decider):
    """Phase 11.4 run 10: consumption was recorded and never enforced, so a
    single-use approval stayed valid for every replay until it expired. Single
    use now lives in the approval contract, for human and delegated alike."""
    from dataclasses import replace

    rollback = _definition(compensation="platform.kubernetes.deployment.rollback")
    fresh = _facts(decider)
    assert _snapshot(fresh, rollback).approval_valid is True
    used = replace(fresh, consumed_by_execution="exec-1")
    assert _snapshot(used, rollback).approval_valid is False
