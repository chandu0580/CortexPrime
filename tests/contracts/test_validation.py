"""Constitutional rules enforced at construction.

Each test here corresponds to a numbered rule in the Architecture Constitution.
These are the tests that make the contracts package load-bearing rather than
decorative: a rule enforced in ``__post_init__`` cannot be forgotten by a caller,
because the value will not construct without satisfying it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from backend.contracts import (
    ActionRef,
    ApprovalDecision,
    ApprovalOutcome,
    ApprovalRequest,
    AuditEvent,
    AuditEventKind,
    ConnectorRef,
    ContractViolation,
    EnvironmentDeclaration,
    EvidenceSet,
    ExecutionContract,
    ExecutionResult,
    ExecutionScope,
    ExecutionStatus,
    HashAlgorithm,
    IsolationTier,
    KnowledgeAuthority,
    KnowledgeItem,
    KnowledgeKind,
    MissionRef,
    MissionState,
    MissionTransition,
    PayloadDigest,
    PolicyDecision,
    PolicyEffect,
    RiskClassification,
    RiskFactors,
    RiskLevel,
    SideEffectClass,
    SourceOutcome,
    SourceStatus,
    TenantRef,
    TenantScope,
    ToolDescriptor,
    Verdict,
    VerificationResult,
    VerificationTarget,
    VerifierIdentity,
    is_legal_transition,
)
from backend.contracts.configuration import ConfigurationSource
from tests.contracts.conftest import LATER, NOW


class TestP2ReversibilityPrecedesAction:
    """Constitution P2: an action may not be proposed without a defined inverse."""

    def test_reversible_write_without_inverse_is_refused(self, execution_scope) -> None:
        with pytest.raises(ContractViolation, match="must declare its inverse"):
            ExecutionContract(
                execution_key="k",
                action=ActionRef("docker.restart", {"container": "web-01"}),
                scope=execution_scope,
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                verification_criteria=("running",),
            )

    def test_irreversible_write_without_inverse_is_permitted(self, execution_scope) -> None:
        """The documented escape hatch: classify honestly instead of pretending."""
        contract = ExecutionContract(
            execution_key="k",
            action=ActionRef("db.drop_index", {"index": "idx_orders"}),
            scope=execution_scope,
            side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
            verification_criteria=("index absent",),
        )
        assert contract.inverse is None
        assert contract.requires_approval_by_default

    def test_read_action_must_not_declare_an_inverse(self, execution_scope) -> None:
        with pytest.raises(ContractViolation, match="read action must not declare an inverse"):
            ExecutionContract(
                execution_key="k",
                action=ActionRef("docker.inspect", {}),
                scope=execution_scope,
                side_effect_class=SideEffectClass.READ,
                inverse=ActionRef("docker.inspect", {}),
                verification_criteria=("ok",),
            )


class TestVerificationCriteriaDeclaredUpFront:
    """Constitution S4: success is declared before execution, never after."""

    def test_empty_verification_criteria_is_refused(self, execution_scope) -> None:
        with pytest.raises(ContractViolation, match="verification_criteria must not be empty"):
            ExecutionContract(
                execution_key="k",
                action=ActionRef("docker.inspect", {}),
                scope=execution_scope,
                side_effect_class=SideEffectClass.READ,
                verification_criteria=(),
            )


class TestP9BlastRadiusIsDeclared:
    """Constitution P9: every execution declares its scope before it runs."""

    def test_scope_with_no_resources_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="must declare what it touches"):
            ExecutionScope(system="docker", resources=(), environment="production")


class TestI2ApprovalBindingIsCryptographic:
    """Constitution I2: the executed payload is the approved payload, by hash."""

    def test_matching_digest_verifies(self, approval_artifact, digest) -> None:
        assert approval_artifact.verify(digest) is True

    def test_substituted_digest_fails_verification(self, approval_artifact, other_digest) -> None:
        assert approval_artifact.verify(other_digest) is False

    def test_digest_across_algorithms_never_matches(self) -> None:
        sha256 = PayloadDigest(algorithm=HashAlgorithm.SHA256, value="a" * 64)
        sha512 = PayloadDigest(algorithm=HashAlgorithm.SHA512, value="a" * 128)
        assert sha256.matches(sha512) is False

    @pytest.mark.parametrize(
        "algorithm,value,reason",
        [
            (HashAlgorithm.SHA256, "a" * 63, "wrong length"),
            (HashAlgorithm.SHA256, "A" * 64, "uppercase"),
            (HashAlgorithm.SHA256, "z" * 64, "non-hexadecimal"),
            (HashAlgorithm.SHA512, "a" * 64, "sha256 length for sha512"),
        ],
    )
    def test_malformed_digest_is_refused(self, algorithm, value, reason) -> None:
        with pytest.raises(ContractViolation):
            PayloadDigest(algorithm=algorithm, value=value)

    def test_artifact_has_no_separately_supplied_summary_field(self, approval_artifact) -> None:
        """The rendering must derive from the artifact, never accompany it.

        A caller-supplied summary is the exact vector that defeated
        human-in-the-loop review in published penetration testing.
        """
        import dataclasses

        field_names = {field.name for field in dataclasses.fields(approval_artifact)}
        assert "summary" not in field_names
        assert "rendered_text" not in field_names
        assert "description" not in field_names


class TestPlatformCannotAuthorizeItself:
    """The Constitution names this as one of two catastrophic failure modes."""

    def test_platform_principal_cannot_grant_approval(self, platform_principal) -> None:
        with pytest.raises(ContractViolation, match="never authorize itself"):
            ApprovalDecision(
                request_id="r-1",
                artifact_id="a-1",
                outcome=ApprovalOutcome.GRANTED,
                decided_at=NOW,
                decided_by=platform_principal,
            )

    def test_human_principal_may_grant_approval(self, human) -> None:
        decision = ApprovalDecision(
            request_id="r-1",
            artifact_id="a-1",
            outcome=ApprovalOutcome.GRANTED,
            decided_at=NOW,
            decided_by=human,
        )
        assert decision.outcome.authorizes_execution

    def test_grant_without_an_approver_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="must record who granted it"):
            ApprovalDecision(
                request_id="r-1",
                artifact_id="a-1",
                outcome=ApprovalOutcome.GRANTED,
                decided_at=NOW,
            )

    def test_denial_without_a_reason_is_refused(self, human) -> None:
        with pytest.raises(ContractViolation, match="must record a reason"):
            ApprovalDecision(
                request_id="r-1",
                artifact_id="a-1",
                outcome=ApprovalOutcome.DENIED,
                decided_at=NOW,
                decided_by=human,
            )


class TestApprovalsExpire:
    def test_expiry_must_follow_request(self, approval_artifact) -> None:
        with pytest.raises(ContractViolation, match="expires_at must be after"):
            ApprovalRequest(
                request_id="r-1",
                artifact=approval_artifact,
                requested_at=LATER,
                expires_at=NOW,
            )

    def test_expiry_is_evaluated_against_a_supplied_moment(self, approval_artifact) -> None:
        request = ApprovalRequest(
            request_id="r-1", artifact=approval_artifact, requested_at=NOW, expires_at=LATER
        )
        assert request.is_expired_at(NOW) is False
        assert request.is_expired_at(LATER) is True
        assert request.is_expired_at(LATER + timedelta(seconds=1)) is True


class TestI7ExperienceMayProposeButNeverAuthorize:
    """Constitution I7, and the guard against memory-driven error propagation."""

    def test_experiential_knowledge_cannot_be_authoritative(self) -> None:
        with pytest.raises(ContractViolation, match="never authorize"):
            KnowledgeItem(
                item_id="k-1",
                kind=KnowledgeKind.EXPERIENTIAL,
                authority=KnowledgeAuthority.AUTHORITATIVE,
                content="last time we restarted the pod and it worked",
                recorded_at=NOW,
            )

    def test_experiential_knowledge_may_be_advisory(self) -> None:
        item = KnowledgeItem(
            item_id="k-1",
            kind=KnowledgeKind.EXPERIENTIAL,
            authority=KnowledgeAuthority.ADVISORY,
            content="last time we restarted the pod and it worked",
            recorded_at=NOW,
            confidence=0.6,
        )
        assert item.authority is KnowledgeAuthority.ADVISORY

    def test_procedural_knowledge_may_be_authoritative(self) -> None:
        item = KnowledgeItem(
            item_id="k-2",
            kind=KnowledgeKind.PROCEDURAL,
            authority=KnowledgeAuthority.AUTHORITATIVE,
            content="runbook: drain node before patching",
            recorded_at=NOW,
        )
        assert item.confidence is None

    def test_advisory_knowledge_must_carry_confidence(self) -> None:
        with pytest.raises(ContractViolation, match="must carry a confidence"):
            KnowledgeItem(
                item_id="k-3",
                kind=KnowledgeKind.EXPERIENTIAL,
                authority=KnowledgeAuthority.ADVISORY,
                content="something happened once",
                recorded_at=NOW,
            )

    def test_authoritative_knowledge_must_not_carry_confidence(self) -> None:
        with pytest.raises(ContractViolation, match="must not carry a confidence"):
            KnowledgeItem(
                item_id="k-4",
                kind=KnowledgeKind.PROCEDURAL,
                authority=KnowledgeAuthority.AUTHORITATIVE,
                content="runbook",
                recorded_at=NOW,
                confidence=0.9,
            )


class TestP5VerificationIsIndependent:
    """Constitution P5: the producer of a conclusion may not be its sole judge."""

    def test_verifier_sharing_the_producer_path_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="shares a reasoning path"):
            VerificationResult(
                target=VerificationTarget.CLAIM,
                subject_reference="claim-1",
                producer_reasoning_path_id="path-a",
                verifier=VerifierIdentity(verifier_id="v-1", reasoning_path_id="path-a"),
                verdict=Verdict.SUPPORTED,
                rationale="the metrics support it",
                verified_at=NOW,
                citation_ids=("cite-1",),
            )

    def test_independent_verifier_is_accepted(self) -> None:
        result = VerificationResult(
            target=VerificationTarget.CLAIM,
            subject_reference="claim-1",
            producer_reasoning_path_id="path-a",
            verifier=VerifierIdentity(verifier_id="v-1", reasoning_path_id="path-b"),
            verdict=Verdict.SUPPORTED,
            rationale="the metrics support it",
            verified_at=NOW,
            citation_ids=("cite-1",),
        )
        assert result.verdict.permits_autonomous_action

    def test_supported_verdict_must_cite_evidence(self) -> None:
        with pytest.raises(ContractViolation, match="must cite the evidence"):
            VerificationResult(
                target=VerificationTarget.CLAIM,
                subject_reference="claim-1",
                producer_reasoning_path_id="path-a",
                verifier=VerifierIdentity(verifier_id="v-1", reasoning_path_id="path-b"),
                verdict=Verdict.SUPPORTED,
                rationale="trust me",
                verified_at=NOW,
            )

    def test_insufficient_evidence_does_not_permit_autonomous_action(self) -> None:
        assert Verdict.INSUFFICIENT_EVIDENCE.permits_autonomous_action is False
        assert Verdict.UNSUPPORTED.permits_autonomous_action is False


class TestRiskIsDeclaredNotInferred:
    """Compliance report V7: criticality comes from declaration, never a name."""

    def test_risk_factors_has_no_field_that_accepts_a_resource_name(self) -> None:
        """Structural guarantee: the input required to guess is simply absent."""
        import dataclasses

        field_names = {field.name for field in dataclasses.fields(RiskFactors)}
        for forbidden in ("resource_name", "name", "container_name", "identifier"):
            assert forbidden not in field_names

    def test_undeclared_criticality_is_distinguishable_from_low(self) -> None:
        undeclared = RiskFactors(
            side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
            environment="production",
            resource_count=1,
            reversible=True,
        )
        declared_low = RiskFactors(
            side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
            environment="production",
            resource_count=1,
            reversible=True,
            resource_criticality=RiskLevel.LOW,
        )
        assert undeclared.criticality_declared is False
        assert declared_low.criticality_declared is True

    def test_declaration_lookup_returns_none_when_undeclared(self, scope) -> None:
        from backend.contracts import DeclarationSet, ResourceDeclaration

        declarations = DeclarationSet(
            scope=scope,
            version="v1",
            resources=(
                ResourceDeclaration(
                    system="docker",
                    resource_id="prod-payments-api",
                    criticality=RiskLevel.CRITICAL,
                    source=ConfigurationSource.OPERATOR,
                ),
            ),
        )
        assert declarations.criticality_for("docker", "prod-payments-api") is RiskLevel.CRITICAL
        assert declarations.criticality_for("docker", "unknown-service") is None

    def test_production_cannot_declare_a_low_baseline(self) -> None:
        with pytest.raises(ContractViolation, match="cannot declare a baseline criticality below"):
            EnvironmentDeclaration(
                environment="production",
                is_production=True,
                baseline_criticality=RiskLevel.LOW,
                source=ConfigurationSource.OPERATOR,
            )

    def test_risk_levels_are_ordered(self) -> None:
        assert RiskLevel.LOW < RiskLevel.MEDIUM < RiskLevel.HIGH < RiskLevel.CRITICAL


class TestPolicyDecisionsAreAuditable:
    def _classification(self) -> RiskClassification:
        return RiskClassification(
            level=RiskLevel.MEDIUM,
            factors=RiskFactors(
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                environment="production",
                resource_count=1,
                reversible=True,
                resource_criticality=RiskLevel.MEDIUM,
            ),
            rationale="reversible write against a declared-medium resource",
        )

    def test_classification_requires_a_rationale(self) -> None:
        with pytest.raises(ContractViolation, match="rationale must explain"):
            RiskClassification(
                level=RiskLevel.HIGH,
                factors=self._classification().factors,
                rationale="   ",
            )

    def test_denial_requires_a_reason(self) -> None:
        with pytest.raises(ContractViolation, match="denial must state a reason"):
            PolicyDecision(
                decision_id="d-1",
                execution_key="k",
                effect=PolicyEffect.DENY,
                risk=self._classification(),
                decided_at=NOW,
                policy_version="v1",
            )

    def test_policy_version_is_required(self) -> None:
        with pytest.raises(ContractViolation, match="policy_version must identify"):
            PolicyDecision(
                decision_id="d-1",
                execution_key="k",
                effect=PolicyEffect.ALLOW,
                risk=self._classification(),
                decided_at=NOW,
                policy_version="",
            )

    def test_obligations_may_only_qualify_an_allow(self) -> None:
        from backend.contracts import Obligation, ObligationKind

        with pytest.raises(ContractViolation, match="attach them to ALLOW decisions only"):
            PolicyDecision(
                decision_id="d-1",
                execution_key="k",
                effect=PolicyEffect.REQUIRE_APPROVAL,
                risk=self._classification(),
                decided_at=NOW,
                policy_version="v1",
                obligations=(Obligation(kind=ObligationKind.NOTIFY_OWNER),),
            )


class TestMissionStateMachine:
    """Constitution S4 transition rules."""

    def test_execution_cannot_reach_concluded_without_verification(self) -> None:
        assert is_legal_transition(MissionState.EXECUTING, MissionState.CONCLUDED) is False
        assert is_legal_transition(MissionState.EXECUTING, MissionState.VERIFYING) is True
        assert is_legal_transition(MissionState.VERIFYING, MissionState.CONCLUDED) is True

    def test_awaiting_decision_is_reachable_mid_execution(self) -> None:
        """New evidence can raise risk after execution has begun."""
        assert is_legal_transition(MissionState.EXECUTING, MissionState.AWAITING_DECISION) is True

    def test_compensating_is_a_first_class_path_to_conclusion(self) -> None:
        assert is_legal_transition(MissionState.COMPENSATING, MissionState.CONCLUDED) is True

    def test_blocked_is_not_terminal(self) -> None:
        """"Prefer blocked over wrong" only works if blocked can resume."""
        assert MissionState.BLOCKED.is_terminal is False
        assert is_legal_transition(MissionState.BLOCKED, MissionState.EXECUTING) is True

    def test_terminal_states_have_no_outgoing_transitions(self) -> None:
        for state in (MissionState.CONCLUDED, MissionState.ABANDONED, MissionState.FAILED):
            assert state.is_terminal
            for target in MissionState:
                assert is_legal_transition(state, target) is False

    def test_illegal_transition_cannot_be_recorded(self) -> None:
        with pytest.raises(ContractViolation, match="illegal mission transition"):
            MissionTransition(
                mission=MissionRef("m-1"),
                from_state=MissionState.EXECUTING,
                to_state=MissionState.CONCLUDED,
                reason="skipping verification",
                occurred_at=NOW,
                sequence=1,
            )

    def test_transition_requires_a_reason(self) -> None:
        with pytest.raises(ContractViolation, match="no state is exited without recording why"):
            MissionTransition(
                mission=MissionRef("m-1"),
                from_state=MissionState.RECEIVED,
                to_state=MissionState.INTERPRETED,
                reason="",
                occurred_at=NOW,
                sequence=0,
            )

    def test_every_state_appears_in_the_transition_table(self) -> None:
        from backend.contracts import LEGAL_TRANSITIONS

        assert set(LEGAL_TRANSITIONS) == set(MissionState)


class TestI3AuditChaining:
    def _digest(self, char: str) -> PayloadDigest:
        return PayloadDigest(algorithm=HashAlgorithm.SHA256, value=char * 64)

    def _event(self, sequence: int, entry: str, previous: str | None) -> AuditEvent:
        return AuditEvent(
            event_id=f"e-{sequence}",
            kind=AuditEventKind.EXECUTION_STARTED,
            scope=TenantScope(tenant=TenantRef("t")),
            recorded_at=NOW,
            sequence=sequence,
            entry_digest=self._digest(entry),
            previous_digest=self._digest(previous) if previous else None,
        )

    def test_genesis_entry_has_no_predecessor(self) -> None:
        genesis = self._event(0, "a", None)
        assert genesis.is_genesis

    def test_genesis_entry_may_not_declare_a_predecessor(self) -> None:
        with pytest.raises(ContractViolation, match="first entry in a chain must have no"):
            self._event(0, "a", "b")

    def test_non_genesis_entry_must_declare_a_predecessor(self) -> None:
        with pytest.raises(ContractViolation, match="only the first entry may omit"):
            self._event(1, "b", None)

    def test_correctly_chained_entries_link(self) -> None:
        genesis = self._event(0, "a", None)
        second = self._event(1, "b", "a")
        assert second.links_to(genesis) is True

    def test_broken_chain_is_detected(self) -> None:
        genesis = self._event(0, "a", None)
        tampered = self._event(1, "b", "c")
        assert tampered.links_to(genesis) is False

    def test_out_of_order_sequence_breaks_the_link(self) -> None:
        genesis = self._event(0, "a", None)
        skipped = self._event(2, "b", "a")
        assert skipped.links_to(genesis) is False

    def test_mixed_algorithms_are_refused(self) -> None:
        with pytest.raises(ContractViolation, match="must use one algorithm"):
            AuditEvent(
                event_id="e-1",
                kind=AuditEventKind.EXECUTION_STARTED,
                scope=TenantScope(tenant=TenantRef("t")),
                recorded_at=NOW,
                sequence=1,
                entry_digest=PayloadDigest(algorithm=HashAlgorithm.SHA256, value="a" * 64),
                previous_digest=PayloadDigest(algorithm=HashAlgorithm.SHA512, value="b" * 128),
            )

    def test_refusals_are_security_relevant(self) -> None:
        assert AuditEventKind.EXECUTION_REFUSED.is_security_relevant
        assert AuditEventKind.INTEGRITY_VIOLATION_DETECTED.is_security_relevant


class TestEvidenceUnavailabilityIsAValue:
    """Constitution BC-2: a failed source and an empty source are different facts."""

    def test_unavailable_source_must_state_why(self) -> None:
        with pytest.raises(ContractViolation, match="must state why"):
            SourceOutcome(source_system="prometheus", status=SourceStatus.UNAVAILABLE)

    def test_empty_and_unavailable_are_distinguishable(self) -> None:
        empty = SourceOutcome(source_system="loki", status=SourceStatus.RETURNED_EMPTY)
        unavailable = SourceOutcome(
            source_system="prometheus", status=SourceStatus.UNAVAILABLE, detail="connection refused"
        )
        assert empty.status.is_informative is True
        assert unavailable.status.is_informative is False

    def test_evidence_set_reports_incompleteness(self, citation) -> None:
        from backend.contracts import EvidenceItem, EvidenceKind

        degraded = EvidenceSet(
            assembled_at=NOW,
            items=(
                EvidenceItem(kind=EvidenceKind.METRIC, citation=citation, excerpt="rate=0.1"),
            ),
            source_outcomes=(
                SourceOutcome(source_system="prometheus", status=SourceStatus.RETURNED_DATA),
                SourceOutcome(
                    source_system="loki", status=SourceStatus.UNAVAILABLE, detail="timeout"
                ),
            ),
        )
        assert degraded.is_complete is False
        assert [outcome.source_system for outcome in degraded.degraded_sources] == ["loki"]

    def test_cited_source_without_an_outcome_is_refused(self, citation) -> None:
        from backend.contracts import EvidenceItem, EvidenceKind

        with pytest.raises(ContractViolation, match="must have a recorded outcome"):
            EvidenceSet(
                assembled_at=NOW,
                items=(
                    EvidenceItem(kind=EvidenceKind.METRIC, citation=citation, excerpt="rate=0.1"),
                ),
                source_outcomes=(),
            )


class TestIsolationTierSufficiency:
    """Constitution S6: isolation is assigned by consequence, not convenience."""

    def test_destructive_tool_cannot_be_ambient(self) -> None:
        with pytest.raises(ContractViolation, match="insufficient for a destructive tool"):
            ToolDescriptor(
                connector=ConnectorRef(connector_id="c-1", system="aws"),
                tool_name="ec2.terminate",
                description="terminate an instance",
                side_effect_class=SideEffectClass.DESTRUCTIVE,
                isolation_tier=IsolationTier.AMBIENT,
            )

    def test_destructive_tool_may_be_sealed(self) -> None:
        tool = ToolDescriptor(
            connector=ConnectorRef(connector_id="c-1", system="aws"),
            tool_name="ec2.terminate",
            description="terminate an instance",
            side_effect_class=SideEffectClass.DESTRUCTIVE,
            isolation_tier=IsolationTier.SEALED,
        )
        assert tool.is_reversible is False

    def test_reversible_write_cannot_be_ambient(self) -> None:
        with pytest.raises(ContractViolation, match="insufficient"):
            ToolDescriptor(
                connector=ConnectorRef(connector_id="c-1", system="docker"),
                tool_name="docker.restart",
                description="restart a container",
                side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
                isolation_tier=IsolationTier.AMBIENT,
            )

    def test_unhealthy_connector_exposes_no_executable_tools(self) -> None:
        from backend.contracts import ConnectorCapabilities, ConnectorHealth

        connector = ConnectorRef(connector_id="c-1", system="docker")
        tool = ToolDescriptor(
            connector=connector,
            tool_name="docker.inspect",
            description="inspect",
            side_effect_class=SideEffectClass.READ,
            isolation_tier=IsolationTier.AMBIENT,
        )
        capabilities = ConnectorCapabilities(
            connector=connector, health=ConnectorHealth.UNAVAILABLE, tools=(tool,)
        )
        assert capabilities.executable_tools == ()
        assert capabilities.tool("docker.inspect") is tool


class TestTenantScopeConsistency:
    """Constitution I6: identity travels intact or not at all."""

    def test_organization_from_another_tenant_is_refused(self) -> None:
        from backend.contracts import OrganizationRef

        with pytest.raises(ContractViolation, match="different tenant"):
            TenantScope(
                tenant=TenantRef("tenant-a"),
                organization=OrganizationRef(tenant=TenantRef("tenant-b"), organization_id="o"),
            )

    def test_project_without_an_organization_is_refused(self, project) -> None:
        with pytest.raises(ContractViolation, match="requires an organization scope"):
            TenantScope(tenant=project.tenant, project=project)

    def test_blank_tenant_id_is_refused(self) -> None:
        with pytest.raises(ContractViolation, match="must not be blank"):
            TenantRef(tenant_id="   ")

    def test_there_is_no_default_tenant(self) -> None:
        with pytest.raises(TypeError):
            TenantRef()  # type: ignore[call-arg]


class TestExecutionResultAccountability:
    def test_failure_must_state_a_reason(self) -> None:
        with pytest.raises(ContractViolation, match="must state failure_reason"):
            ExecutionResult(
                execution_key="k",
                status=ExecutionStatus.FAILED,
                started_at=NOW,
                completed_at=LATER,
            )

    def test_refusal_must_state_a_reason(self) -> None:
        with pytest.raises(ContractViolation, match="must state failure_reason"):
            ExecutionResult(
                execution_key="k",
                status=ExecutionStatus.REFUSED,
                started_at=NOW,
                completed_at=LATER,
            )

    def test_terminal_status_requires_completion_time(self) -> None:
        with pytest.raises(ContractViolation, match="must record completed_at"):
            ExecutionResult(
                execution_key="k", status=ExecutionStatus.SUCCEEDED, started_at=NOW
            )

    def test_completion_cannot_precede_start(self) -> None:
        with pytest.raises(ContractViolation, match="must not precede started_at"):
            ExecutionResult(
                execution_key="k",
                status=ExecutionStatus.SUCCEEDED,
                started_at=LATER,
                completed_at=NOW,
            )

    def test_running_status_needs_no_completion_time(self) -> None:
        result = ExecutionResult(
            execution_key="k", status=ExecutionStatus.RUNNING, started_at=NOW
        )
        assert result.status.is_terminal is False
