"""Direct, per-stage evidence for the SecureCapabilityInvocationGateway.

Phase 6.2, Part A. The gateway declares thirteen admission stages::

    identity -> tenancy -> binding -> authorization -> approval -> worker
    -> input -> digest -> obligations -> freshness -> lease -> rate -> credential

plus a fourteenth check, delegation, which runs immediately after authorization
and reports under stage "identity". This file gives every stage its own
dedicated refusal evidence, and proves the two properties the module docstring
calls "the security property":

* **The order is the boundary.** Every recording stub appends to one shared
  ``calls`` list, so each negative test can assert that the ports *behind* the
  failing stage were never consulted -- a tenancy failure never reaches the
  authorization authority, an authorization denial never reaches the lease
  authority, and nothing that refuses ever reaches the provider.

* **Credentials are last.** A request that was going to be refused must never
  cause a secret to be minted (ADR-038 s2). Every refusal test asserts
  ``credential acquisitions == 0`` and ``provider calls == 0``; the happy path
  asserts exactly one acquisition, after every other stage and before the one
  provider call.

Everything here is built from the real domain objects -- a real
``WorkerRuntime``, a real ``InMemoryWorkerDirectory`` walked up the full
commissioning ladder, the real ``TestProviderAdapter`` running the whole
adapter gate -- with recording stubs only at the gateway's declared ports,
which is where the composition root sits in production.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.contracts.connector import IsolationTier
from backend.contracts.credential import (
    CredentialRef,
    CredentialState,
    CredentialType,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.connector import CodeTrust
from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contracts.policy import PolicyEffect
from backend.contracts.provider import ProviderRef
from backend.contexts.execution.application.invocation_gateway import (
    AuthorityFacts,
    LeaseFacts,
    SecureCapabilityInvocationGateway,
)
from backend.contexts.execution.application.worker_runtime import (
    WorkerInvocationRefused,
    WorkerRuntime,
)
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.identifiers import AttemptId, ExecutionId
from backend.contexts.execution.domain.invocation import (
    FrozenClock,
    InvocationRefusal,
    InvocationRefused,
    InvocationRequest,
    canonical_action_digest,
)
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    ParameterKind,
    ParameterLocation,
    ParameterSpec,
    ProviderOperationSpec,
)
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import (
    WorkerExecutionResult,
    WorkerOutcome,
)
from backend.contexts.execution.domain.worker_directory import (
    WorkerAvailability,
    WorkerImplementation,
    WorkerInterface,
    WorkerScope,
    WorkerTrust,
)
from backend.contexts.execution.infrastructure.adapters.testing import (
    TestProviderAdapter,
)
from backend.contexts.execution.infrastructure.worker_directory import (
    InMemoryWorkerDirectory,
)
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext
from backend.platform.credentials import (
    CredentialGrant,
    CredentialMaterial,
    CredentialRefusal,
    CredentialRefused,
    IssuedCredential,
)


# ----------------------------------------------------------------------
# The one world every test lives in
# ----------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
LATER = NOW + timedelta(hours=2)
DEADLINE = NOW + timedelta(minutes=30)

TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"
ACTOR = PrincipalRef(principal_id="alice", kind=PrincipalKind.HUMAN)
DELEGATE = PrincipalRef(principal_id="bob", kind=PrincipalKind.HUMAN)

PROVIDER_ID = "testprov"
PROVIDER = ProviderRef(provider_id=PROVIDER_ID)
CAP_REF = "demo.testprov.thing@1.0.0"
CAP_DIGEST = "cap-digest-0001"
OP_READ = "thing.read"
OP_WRITE = "thing.write"
GOV_OP = "invoke"
BINDING_ID = "B-0001"
BINDING_DIGEST = "binding-digest-0001"
AUTH_DIGEST = "auth-digest-0001"
POLICY_VERSION = "policy-v1"
NODE = "node-1"
ENV = ExecutionEnvironment.DEVELOPMENT
LEASE_HOLDER = "dispatcher-1"
WORKER_ID = "test-worker"

_DEFAULT = object()


def _catalog() -> OperationCatalog:
    return OperationCatalog(
        PROVIDER_ID,
        [
            ProviderOperationSpec(
                operation=OP_READ,
                method="GET",
                path_template="/thing",
                side_effect_class=SideEffectClass.READ,
                effect_semantics=EffectSemantics.READ_ONLY,
                parameters=(
                    ParameterSpec(
                        name="name",
                        kind=ParameterKind.STRING,
                        location=ParameterLocation.QUERY,
                        required=False,
                    ),
                ),
            ),
            ProviderOperationSpec(
                operation=OP_WRITE,
                method="POST",
                path_template="/thing",
                side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
                effect_semantics=EffectSemantics.IDEMPOTENT_WRITE,
            ),
        ],
    )


def _implementation(isolation: IsolationTier) -> WorkerImplementation:
    return WorkerImplementation(
        worker_id=WORKER_ID,
        worker_kind=WorkerKind.CONNECTOR,
        interface=WorkerInterface.CONNECTOR,
        implementation="tests.invocation_gateway_matrix.scripted",
        implementation_version="0.0.0-test",
        isolation=isolation,
        scope=WorkerScope.TENANT,
        tenant_id=TENANT,
        supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
        supported_effects=frozenset(
            {EffectSemantics.READ_ONLY, EffectSemantics.IDEMPOTENT_WRITE}
        ),
        supported_providers=frozenset({PROVIDER_ID}),
        supported_operations=frozenset({OP_READ, OP_WRITE}),
    )


def _facts(operation: str = OP_READ, **overrides) -> AuthorityFacts:
    """A fully-green authorization position; override one clause to break it."""
    fields = dict(
        effect=PolicyEffect.ALLOW,
        policy_version=POLICY_VERSION,
        decision_digest="decision-digest-0001",
        capability_digest=CAP_DIGEST,
        tenant_id=TENANT,
        principal_id=ACTOR.principal_id,
        governance_operation=GOV_OP,
        provider_operation=operation,
        expires_at=LATER,
        binding_key="bk-0001",
        environment=ENV,
    )
    fields.update(overrides)
    return AuthorityFacts(**fields)


def _expected_digest(
    payload=None, *, operation: str = OP_READ, policy_version: str = POLICY_VERSION
) -> str:
    """The canonical action digest the gateway will compute for this action."""
    return canonical_action_digest(
        capability_ref=CAP_REF,
        capability_digest=CAP_DIGEST,
        operation=operation,
        tenant_id=TENANT,
        principal_id=ACTOR.principal_id,
        environment=ENV,
        binding_digest=BINDING_DIGEST,
        policy_version=policy_version,
        payload=payload or {},
    )


# ----------------------------------------------------------------------
# Recording stubs -- every one appends to the shared call-order log
# ----------------------------------------------------------------------


class RecordingAuthority:
    """The CapabilityAuthority port: answers with configured facts, records."""

    def __init__(self, calls, facts=None, error=None) -> None:
        self.calls = calls
        self.facts = facts
        self.error = error
        self.consultations = 0

    def facts_for(self, context, request, binding):
        self.consultations += 1
        self.calls.append("authority")
        if self.error is not None:
            raise self.error
        return self.facts


class RecordingLeases:
    """The LeaseAuthority port: answers with configured facts, records."""

    def __init__(self, calls, facts=None, error=None) -> None:
        self.calls = calls
        self.facts = facts
        self.error = error
        self.consultations = 0

    def lease_for(self, context, execution_id, node_id):
        self.consultations += 1
        self.calls.append("lease")
        if self.error is not None:
            raise self.error
        return self.facts


class RecordingCredentials:
    """The credential provider port, mirroring BrokerCredentialProvider's shape.

    Counts *attempts* (the port was consulted) separately from *acquisitions*
    (a secret was actually minted), because "no secret is minted for a refused
    request" is the property under test.
    """

    def __init__(self, calls, error=None, return_none=False) -> None:
        self.calls = calls
        self.error = error
        self.return_none = return_none
        self.attempts = 0
        self.acquisitions = 0

    def scoped_credential(self, context, request):
        self.attempts += 1
        self.calls.append("credential")
        if self.error is not None:
            raise self.error
        if self.return_none:
            return None
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=600)
        ref = CredentialRef(tenant_id=request.tenant_id, credential_id="test-cred-1")
        material = CredentialMaterial(
            secret="test-secret-value",
            ref=ref,
            credential_type=CredentialType.API_KEY,
            expires_at=expires_at,
        )
        grant = CredentialGrant(
            ref=ref,
            credential_type=CredentialType.API_KEY,
            scope=request.scope,
            state=CredentialState.ACTIVE,
            issued_at=issued_at,
            expires_at=expires_at,
            tenant_id=request.tenant_id,
            action_digest=request.action_digest,
            binding_digest=request.binding_digest,
            provider=request.provider,
            environment=request.environment,
            fingerprint=material.fingerprint(),
        )
        self.acquisitions += 1
        return IssuedCredential(grant, material)


class RecordingRateLimiter:
    """The RateLimiter port. Empty answer means within budget."""

    def __init__(self, calls, exceeded=(), error=None) -> None:
        self.calls = calls
        self.exceeded = tuple(exceeded)
        self.error = error

    def check(self, context, request):
        self.calls.append("rate")
        if self.error is not None:
            raise self.error
        return self.exceeded


class RecordingValidator:
    """An InputValidator that records under a given label."""

    def __init__(self, calls, label, problems=(), error=None) -> None:
        self.calls = calls
        self.label = label
        self.problems = tuple(problems)
        self.error = error

    def validate(self, binding, payload):
        self.calls.append(self.label)
        if self.error is not None:
            raise self.error
        return self.problems


class RecordingBindingValidator:
    """The worker runtime's BindingValidator port; always says the binding holds."""

    def __init__(self, calls) -> None:
        self.calls = calls

    def invalidations(self, context, binding):
        self.calls.append("binding_check")
        return ()


class ConnectorKindResolver:
    """The WorkerKindPort: every capability here resolves to the connector kind."""

    def kind_for(self, binding):
        return WorkerKind.CONNECTOR.value


class ForeignResultAdapter:
    """An adapter returning a result that describes some *other* invocation.

    Used only by the result-integrity test: the gateway must record such a
    result as UNKNOWN_OUTCOME, never as this invocation's success.
    """

    CONSUMES_PROVIDER_AUTHORITY = True

    def __init__(self, calls) -> None:
        self.calls = calls

    def run(self, context, request, *, authority=None):
        self.calls.append("provider")
        return WorkerExecutionResult.success(
            binding_id="B-9999-someone-elses",
            attempt_id=str(AttemptId.new()),
            started_at=datetime.now(timezone.utc),
            output={"ok": True},
        )


# ----------------------------------------------------------------------
# The fixture: one gateway, fully wired, every port recording
# ----------------------------------------------------------------------


class Fixture:
    """A complete, admissible invocation. Each test breaks exactly one thing."""

    def __init__(
        self,
        *,
        operation: str = OP_READ,
        isolation: IsolationTier = IsolationTier.SEALED,
        register_worker: bool = True,
        delegated: bool = False,
        payload=None,
        facts=_DEFAULT,
        authority_error=None,
        wire_authority: bool = True,
        lease_facts=_DEFAULT,
        lease_error=None,
        wire_leases: bool = True,
        credential_error=None,
        credential_none: bool = False,
        rate_exceeded=(),
        rate_error=None,
        gateway_validator_problems=(),
        gateway_validator_error=None,
        wire_gateway_validator: bool = True,
        adapter: str = "scripted",
    ) -> None:
        self.calls: list = []
        self.operation = operation
        self.payload = dict(payload or {})
        if operation == OP_WRITE:
            self.side_effect = SideEffectClass.IRREVERSIBLE_WRITE
            self.semantics = EffectSemantics.IDEMPOTENT_WRITE
        else:
            self.side_effect = SideEffectClass.READ
            self.semantics = EffectSemantics.READ_ONLY

        self.execution_id = ExecutionId.new()
        self.attempt_id = AttemptId.new()

        identity = IdentityContext(
            principal=ACTOR,
            capabilities=("capability:invoke",),
            on_behalf_of=DELEGATE if delegated else None,
        )
        self.delegated = delegated
        self.context = ExecutionContext.for_tenant(
            tenant_id=TENANT, identity=identity, source="pytest"
        )

        implementation = _implementation(isolation)
        self.worker_digest = implementation.digest
        if adapter == "foreign":
            self.adapter = ForeignResultAdapter(self.calls)
        else:
            self.adapter = TestProviderAdapter(
                implementation=implementation,
                provider=PROVIDER,
                catalog=_catalog(),
                allow_non_production=True,
                responder=self._respond,
            )

        directory = InMemoryWorkerDirectory()
        if register_worker:
            # The full commissioning ladder: registration is not enablement,
            # and the trust ladder refuses skipping.
            directory.register(self.context, implementation, self.adapter)
            directory.validate(self.context, worker_id=WORKER_ID, tenant_id=TENANT)
            directory.enable(self.context, worker_id=WORKER_ID, tenant_id=TENANT)
            directory.set_trust(
                self.context,
                worker_id=WORKER_ID,
                tenant_id=TENANT,
                trust=WorkerTrust.VERIFIED,
                reason="verified for the phase 6.2 gateway matrix",
            )
            directory.set_availability(
                self.context,
                worker_id=WORKER_ID,
                tenant_id=TENANT,
                availability=WorkerAvailability.AVAILABLE,
            )

        runtime = WorkerRuntime(
            binding_validator=RecordingBindingValidator(self.calls),
            worker_kinds=ConnectorKindResolver(),
            directory=directory,
            input_validator=RecordingValidator(self.calls, "runtime_input"),
        )

        if facts is _DEFAULT:
            facts = _facts(operation=operation)
        self.authority = (
            RecordingAuthority(self.calls, facts=facts, error=authority_error)
            if wire_authority
            else None
        )
        if lease_facts is _DEFAULT:
            lease_facts = LeaseFacts(
                held=True,
                node_id=NODE,
                worker_id=LEASE_HOLDER,
                attempt_id=str(self.attempt_id),
                expires_at=LATER,
            )
        self.leases = (
            RecordingLeases(self.calls, facts=lease_facts, error=lease_error)
            if wire_leases
            else None
        )
        self.credentials = RecordingCredentials(
            self.calls, error=credential_error, return_none=credential_none
        )
        self.rate_limiter = RecordingRateLimiter(
            self.calls, exceeded=rate_exceeded, error=rate_error
        )
        self.gateway_validator = (
            RecordingValidator(
                self.calls,
                "input",
                problems=gateway_validator_problems,
                error=gateway_validator_error,
            )
            if wire_gateway_validator
            else None
        )

        self.gateway = SecureCapabilityInvocationGateway(
            worker_runtime=runtime,
            authority=self.authority,
            leases=self.leases,
            input_validator=self.gateway_validator,
            credentials=self.credentials,
            rate_limiter=self.rate_limiter,
            clock=FrozenClock(NOW),
        )

        self.binding = self.binding_with()
        self.request = self.request_with()

    # -- builders ------------------------------------------------------

    def _respond(self, authority):
        self.calls.append("provider")
        return {"body": {"ok": True}}

    def binding_with(self, **overrides) -> BoundCapability:
        fields = dict(
            binding_id=BINDING_ID,
            binding_digest=BINDING_DIGEST,
            capability_ref=CAP_REF,
            capability_digest=CAP_DIGEST,
            provider=PROVIDER_ID,
            operation=self.operation,
            authorization_digest=AUTH_DIGEST,
            tenant_id=TENANT,
            principal_id=ACTOR.principal_id,
            expires_at=LATER,
            side_effect_class=self.side_effect,
            effect_semantics=self.semantics,
            # ADR-088: these fixtures drive typed connector operations, which is
            # exactly what FIXED means. A test that wants to exercise a
            # higher code-trust class overrides it.
            code_trust=CodeTrust.FIXED,
            environment=ENV,
            governance_operation=GOV_OP,
            execution_id=str(self.execution_id),
            node_id=NODE,
            authorization_policy_version=POLICY_VERSION,
        )
        fields.update(overrides)
        return BoundCapability(**fields)

    def request_with(self, **overrides) -> InvocationRequest:
        fields = dict(
            execution_id=self.execution_id,
            attempt_id=self.attempt_id,
            attempt_number=1,
            node_id=NODE,
            tenant_id=TENANT,
            principal=ACTOR,
            capability_ref=CAP_REF,
            capability_digest=CAP_DIGEST,
            operation=self.operation,
            governance_operation=GOV_OP,
            environment=ENV,
            binding_id=BINDING_ID,
            binding_digest=BINDING_DIGEST,
            worker_selection_id="sel-0001",
            worker_id=WORKER_ID,
            worker_digest=self.worker_digest,
            payload=dict(self.payload),
            lease_holder_id=LEASE_HOLDER,
            correlation_id="corr-0001",
            trace_id="trace-0001",
            deadline_at=DEADLINE,
            on_behalf_of=DELEGATE if self.delegated else None,
        )
        fields.update(overrides)
        return InvocationRequest(**fields)

    # -- observation ---------------------------------------------------

    @property
    def provider_calls(self) -> int:
        return self.calls.count("provider")


def _refused(
    fixture: Fixture,
    refusal: InvocationRefusal,
    stage: str,
    *,
    context=None,
    request=None,
    binding=None,
) -> InvocationRefused:
    """Admit, expect a refusal from exactly that stage, and prove the two
    invariants every refusal must satisfy: no provider call, no secret minted."""
    with pytest.raises(InvocationRefused) as caught:
        fixture.gateway.admit(
            context if context is not None else fixture.context,
            request if request is not None else fixture.request,
            binding if binding is not None else fixture.binding,
        )
    refused = caught.value
    assert refused.refusal is refusal, (
        f"expected {refusal.value}, got {refused.refusal.value}: {refused}"
    )
    assert refused.detail.get("stage") == stage, refused.detail
    assert fixture.provider_calls == 0, "a refused invocation reached the provider"
    assert fixture.credentials.acquisitions == 0, (
        "a refused invocation caused a secret to be minted"
    )
    return refused


# ----------------------------------------------------------------------
# 0. Construction
# ----------------------------------------------------------------------


class TestConstruction:
    def test_the_gateway_refuses_to_exist_without_the_worker_runtime(self) -> None:
        """"Without it ... the gate would be guarding nothing" -- a gateway
        cannot be assembled around something that is not the Phase 3.3.2
        runtime."""
        with pytest.raises(ContractViolation):
            SecureCapabilityInvocationGateway(worker_runtime=object())


# ----------------------------------------------------------------------
# 1. The fully-green path
# ----------------------------------------------------------------------


class TestHappyPath:
    def test_admission_runs_every_stage_in_the_declared_order(self) -> None:
        """One admission, all thirteen stages, and the recorded port order is
        exactly the order the module docstring declares -- credentials last."""
        fx = Fixture()
        expected_digest = _expected_digest()
        request = fx.request_with(declared_action_digest=expected_digest)

        admission = fx.gateway.admit(fx.context, request, fx.binding)

        assert admission.action_digest == expected_digest
        assert admission.credential is not None
        assert admission.deadline_seconds > 0
        assert admission.validated_payload == {}
        # The whole ordering proof for admission, in one line: authority, the
        # worker gate (binding re-check + the runtime's own input validation),
        # the gateway's input validation, lease, rate, and credentials LAST.
        assert fx.calls == [
            "authority",
            "binding_check",
            "runtime_input",
            "input",
            "lease",
            "rate",
            "credential",
        ]
        assert fx.credentials.acquisitions == 1
        assert fx.provider_calls == 0, "admit() alone must never invoke"

    def test_invoke_reaches_the_provider_exactly_once_after_the_credential(self) -> None:
        """invoke() = admit + one provider call. The credential is minted after
        every other stage and before the only provider call; nothing runs twice."""
        fx = Fixture(payload={"name": "widget"})

        outcome = fx.gateway.invoke(fx.context, fx.request, fx.binding)

        assert outcome.succeeded
        assert outcome.result.outcome is WorkerOutcome.SUCCESS
        assert fx.provider_calls == 1
        assert fx.credentials.acquisitions == 1
        assert fx.calls.count("credential") == 1
        credential_at = fx.calls.index("credential")
        for stage in ("authority", "binding_check", "runtime_input", "input", "lease", "rate"):
            assert fx.calls.index(stage) < credential_at, (
                f"{stage} was first consulted after the credential was minted"
            )
        assert fx.calls.index("provider") > credential_at
        assert [type(e).__name__ for e in outcome.events] == [
            "InvocationAdmitted",
            "InvocationStarted",
            "InvocationCompleted",
        ]
        # The adapter's own record agrees: exactly one governed call.
        assert len(fx.adapter.calls) == 1
        assert fx.adapter.calls[0]["action_digest"] == outcome.admission.action_digest

    def test_a_valid_approval_bound_to_this_exact_action_admits(self) -> None:
        """An approval is sufficient only when its bound digest IS this action's
        digest -- the positive half of the approval stage."""
        fx = Fixture(
            facts=_facts(
                effect=PolicyEffect.REQUIRE_APPROVAL,
                approval_required=True,
                approval_present=True,
                approval_valid=True,
                approval_artifact_id="APPROVAL-1",
                approval_bound_digest=_expected_digest(),
                approval_expires_at=LATER,
            )
        )
        admission = fx.gateway.admit(fx.context, fx.request, fx.binding)
        assert admission.authority.approval_artifact_id == "APPROVAL-1"
        assert fx.credentials.acquisitions == 1


# ----------------------------------------------------------------------
# 2. identity (including the delegation check that reports under it)
# ----------------------------------------------------------------------


class TestIdentityStage:
    def test_a_context_with_no_authenticated_principal_is_refused(self) -> None:
        """"The context carries no authenticated principal" -- identity is the
        first stage, so nothing else is ever consulted."""
        fx = Fixture()
        refused = _refused(
            fx,
            InvocationRefusal.IDENTITY_MISSING,
            "identity",
            context=SimpleNamespace(identity=None),
        )
        assert fx.authority.consultations == 0
        assert refused.refusal.is_retryable is False

    def test_a_request_naming_a_principal_the_context_did_not_authenticate(self) -> None:
        """Never trust a principal supplied alongside the request; the
        authenticated one is the only one that was proved."""
        fx = Fixture()
        mallory = PrincipalRef(principal_id="mallory", kind=PrincipalKind.HUMAN)
        _refused(
            fx,
            InvocationRefusal.PRINCIPAL_MISMATCH,
            "identity",
            request=fx.request_with(principal=mallory),
        )
        assert fx.authority.consultations == 0

    def test_a_delegation_chain_the_context_did_not_authenticate(self) -> None:
        """The request delegates and the authenticated context does not: actor
        and delegated principal stay distinct, and a mismatch refuses."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.PRINCIPAL_MISMATCH,
            "identity",
            request=fx.request_with(on_behalf_of=DELEGATE),
        )
        assert fx.authority.consultations == 0

    def test_delegation_the_decision_never_sanctioned_is_refused(self) -> None:
        """The Phase 4.4 gap closed: 'absence is not permission'. The chain is
        authentic, but the decision said nothing about delegation -- and the
        refusal lands before a worker is ever selected."""
        fx = Fixture(delegated=True)  # default facts: delegation_permitted=False
        _refused(fx, InvocationRefusal.DELEGATION_NOT_AUTHORIZED, "identity")
        assert fx.authority.consultations == 1
        assert "binding_check" not in fx.calls, (
            "a worker was selected for an invocation nobody may make"
        )

    def test_delegation_sanctioned_for_a_different_principal_is_refused(self) -> None:
        """A decision about carol's authority never authorizes acting for bob.
        A different principal is a refusal, never a substitution."""
        fx = Fixture(
            delegated=True,
            facts=_facts(delegation_permitted=True, delegated_principal_id="carol"),
        )
        _refused(fx, InvocationRefusal.DELEGATION_NOT_AUTHORIZED, "identity")

    def test_delegation_permitted_but_unbound_is_refused(self) -> None:
        """"An unbound delegation would authorize acting for anybody"."""
        fx = Fixture(
            delegated=True,
            facts=_facts(delegation_permitted=True, delegated_principal_id=None),
        )
        _refused(fx, InvocationRefusal.DELEGATION_NOT_AUTHORIZED, "identity")

    def test_a_delegated_decision_used_for_a_non_delegated_request_is_refused(self) -> None:
        """The decision names a delegated principal and the request delegates to
        nobody: somebody else's authority must not run as one's own."""
        fx = Fixture(
            facts=_facts(delegation_permitted=True, delegated_principal_id="bob"),
        )
        _refused(fx, InvocationRefusal.DELEGATION_NOT_AUTHORIZED, "identity")


# ----------------------------------------------------------------------
# 3. tenancy
# ----------------------------------------------------------------------


class TestTenancyStage:
    def test_a_platform_internal_context_cannot_reach_a_tenant_capability(self) -> None:
        """"A platform-internal context has no tenant of its own to match
        against, so it must never be usable to reach tenant capabilities"."""
        fx = Fixture()
        platform = ExecutionContext.platform_internal(
            reason="gateway matrix test", component="tests", source="pytest"
        )
        # The request principal matches the platform context so the refusal
        # provably comes from the tenancy stage, not identity.
        request = fx.request_with(
            principal=PrincipalRef(principal_id="tests", kind=PrincipalKind.PLATFORM)
        )
        _refused(
            fx,
            InvocationRefusal.TENANT_UNKNOWN,
            "tenancy",
            context=platform,
            request=request,
        )
        assert fx.authority.consultations == 0

    def test_a_cross_tenant_request_is_refused_without_disclosure(self) -> None:
        """Tenant B's request under tenant A's context refuses at tenancy --
        before the authorization authority could confirm or deny that the
        capability even exists -- and the refusal leaks no capability detail."""
        fx = Fixture()
        refused = _refused(
            fx,
            InvocationRefusal.TENANT_MISMATCH,
            "tenancy",
            request=fx.request_with(tenant_id=OTHER_TENANT),
        )
        assert fx.authority.consultations == 0, (
            "the authority was consulted for another tenant's request"
        )
        disclosed = str(refused) + str(refused.to_dict())
        assert CAP_REF not in disclosed
        assert CAP_DIGEST not in disclosed
        assert refused.refusal.is_security_relevant


# ----------------------------------------------------------------------
# 4. binding
# ----------------------------------------------------------------------


class TestBindingStage:
    def test_a_request_naming_a_different_binding_is_refused(self) -> None:
        """"Mismatches are never repaired" -- the request must name the binding
        it was actually handed."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.BINDING_MISMATCH,
            "binding",
            request=fx.request_with(binding_id="B-somebody-else"),
        )
        assert fx.authority.consultations == 0

    def test_a_binding_digest_disagreement_is_refused(self) -> None:
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.BINDING_MISMATCH,
            "binding",
            request=fx.request_with(binding_digest="tampered-digest"),
        )
        assert fx.authority.consultations == 0

    def test_a_binding_made_for_a_different_node_is_refused(self) -> None:
        """A binding is scoped to one execution node; presenting it for another
        node is somebody else's authority."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.EXECUTION_MISMATCH,
            "binding",
            binding=fx.binding_with(node_id="node-other"),
        )
        assert fx.authority.consultations == 0

    def test_an_expired_binding_is_refused_never_extended(self) -> None:
        """"Expiry is never extended at the point of use"."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.BINDING_EXPIRED,
            "binding",
            binding=fx.binding_with(expires_at=NOW - timedelta(seconds=1)),
        )
        assert fx.authority.consultations == 0

    def test_a_binding_with_no_environment_is_refused(self) -> None:
        """"Unstated is not a wildcard, and a development binding must not
        reach production"."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.ENVIRONMENT_UNKNOWN,
            "binding",
            binding=fx.binding_with(environment=None),
        )

    def test_an_undeclared_effect_is_refused(self) -> None:
        """"An undeclared repeat is what turns one production change into two"
        -- UNKNOWN effect semantics stay fail-closed."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.EFFECT_UNDECLARED,
            "binding",
            binding=fx.binding_with(effect_semantics=EffectSemantics.UNKNOWN),
        )
        assert fx.authority.consultations == 0


# ----------------------------------------------------------------------
# 5. authorization
# ----------------------------------------------------------------------


class TestAuthorizationStage:
    def test_an_absent_authorization_authority_is_a_refusal_not_a_bypass(self) -> None:
        """"Absence of a port is a refusal in every case, never a bypass"."""
        fx = Fixture(wire_authority=False)
        _refused(fx, InvocationRefusal.AUTHORIZATION_UNAVAILABLE, "authorization")

    def test_an_authority_that_raises_refuses_without_leaking_the_error(self) -> None:
        """Unverifiable is unusable -- and only the exception *type* travels."""
        fx = Fixture(authority_error=RuntimeError("pg://secret-host is down"))
        refused = _refused(
            fx, InvocationRefusal.AUTHORIZATION_UNAVAILABLE, "authorization"
        )
        assert "RuntimeError" in refused.safe_message
        assert "secret-host" not in refused.safe_message

    def test_no_decision_is_never_allow(self) -> None:
        """"Missing is never allow"."""
        fx = Fixture(facts=None)
        _refused(fx, InvocationRefusal.AUTHORIZATION_MISSING, "authorization")

    def test_a_policy_denial_refuses_and_no_worker_is_ever_selected(self) -> None:
        """Denial carries the policy's own reasons, and selecting a worker for
        an invocation nobody may make is work done on behalf of a refusal."""
        fx = Fixture(
            facts=_facts(effect=PolicyEffect.DENY, reasons=("policy_denied_by_rule",))
        )
        refused = _refused(fx, InvocationRefusal.AUTHORIZATION_DENIED, "authorization")
        assert refused.reasons == ("policy_denied_by_rule",)
        assert "binding_check" not in fx.calls
        assert "lease" not in fx.calls

    def test_an_expired_decision_is_refused(self) -> None:
        """Authorization freshness: the decision itself has lapsed."""
        fx = Fixture(facts=_facts(expires_at=NOW - timedelta(seconds=1)))
        _refused(fx, InvocationRefusal.AUTHORIZATION_EXPIRED, "authorization")

    def test_a_request_that_cannot_name_its_governance_operation_is_refused(self) -> None:
        """"Absent is refused, not tolerated" -- a request that cannot say
        which governed action it is cannot be matched against a decision."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.OPERATION_MISMATCH,
            "authorization",
            request=fx.request_with(governance_operation=None),
        )

    def test_a_decision_about_a_different_governance_operation_is_refused(self) -> None:
        """First of the two independent operation comparisons:
        decision-vs-request on the governance verb."""
        fx = Fixture(facts=_facts(governance_operation="administer"))
        _refused(fx, InvocationRefusal.OPERATION_MISMATCH, "authorization")

    def test_a_decision_covering_a_different_provider_operation_is_refused(self) -> None:
        """Second comparison: decision-vs-request on the concrete provider
        action -- two vocabularies, two comparisons, neither standing in for
        the other."""
        fx = Fixture(facts=_facts(provider_operation=OP_WRITE))
        _refused(fx, InvocationRefusal.OPERATION_MISMATCH, "authorization")

    def test_a_decision_for_a_different_capability_digest_is_refused(self) -> None:
        """The tampered-decision case: authority facts presented for another
        capability contract must not authorize this one."""
        fx = Fixture(facts=_facts(capability_digest="some-other-contract-digest"))
        _refused(fx, InvocationRefusal.CAPABILITY_MISMATCH, "authorization")

    def test_a_policy_change_under_a_live_binding_is_refused(self) -> None:
        """"The rules changed under a live binding ... not something to
        proceed through silently"."""
        fx = Fixture(facts=_facts(policy_version="policy-v2"))
        _refused(fx, InvocationRefusal.POLICY_VERSION_CHANGED, "authorization")


# ----------------------------------------------------------------------
# 6. approval
# ----------------------------------------------------------------------


class TestApprovalStage:
    def test_require_approval_with_no_valid_approval_is_refused(self) -> None:
        """A REQUIRE_APPROVAL effect without a valid approval refuses before a
        worker is selected."""
        fx = Fixture(facts=_facts(effect=PolicyEffect.REQUIRE_APPROVAL))
        _refused(fx, InvocationRefusal.APPROVAL_REQUIRED, "approval")
        assert "binding_check" not in fx.calls

    def test_approval_required_and_none_recorded_is_refused(self) -> None:
        fx = Fixture(facts=_facts(approval_required=True))
        _refused(fx, InvocationRefusal.APPROVAL_MISSING, "approval")

    def test_an_invalid_approval_is_refused(self) -> None:
        fx = Fixture(
            facts=_facts(
                approval_required=True, approval_present=True, approval_valid=False
            )
        )
        _refused(fx, InvocationRefusal.APPROVAL_MISSING, "approval")

    def test_an_expired_approval_is_none_at_all(self) -> None:
        """"An expired approval is not a weaker approval, it is none"."""
        fx = Fixture(
            facts=_facts(
                approval_required=True,
                approval_present=True,
                approval_valid=True,
                approval_bound_digest=_expected_digest(),
                approval_expires_at=NOW - timedelta(seconds=1),
            )
        )
        _refused(fx, InvocationRefusal.APPROVAL_EXPIRED, "approval")

    def test_an_unbound_approval_is_refused(self) -> None:
        """"An unbound approval would authorize anything this capability can
        do"."""
        fx = Fixture(
            facts=_facts(
                approval_required=True,
                approval_present=True,
                approval_valid=True,
                approval_bound_digest=None,
                approval_expires_at=LATER,
            )
        )
        _refused(fx, InvocationRefusal.APPROVAL_MISMATCH, "approval")

    def test_an_approval_for_a_different_action_is_refused(self) -> None:
        """An approval for delete_repository must not authorize
        create_repository: the bound digest must equal this action's digest."""
        fx = Fixture(
            facts=_facts(
                approval_required=True,
                approval_present=True,
                approval_valid=True,
                approval_bound_digest="digest-of-some-other-action",
                approval_expires_at=LATER,
            )
        )
        _refused(fx, InvocationRefusal.APPROVAL_MISMATCH, "approval")


# ----------------------------------------------------------------------
# 7. worker
# ----------------------------------------------------------------------


class TestWorkerStage:
    def test_no_registered_worker_means_refusal_not_a_default(self) -> None:
        """An empty directory refuses; there is no default worker."""
        fx = Fixture(register_worker=False)
        _refused(fx, InvocationRefusal.WORKER_UNAVAILABLE, "worker")
        assert "lease" not in fx.calls

    def test_a_selection_naming_a_different_worker_is_refused(self) -> None:
        """"The worker selected now is not the one the request names"."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.WORKER_SELECTION_MISMATCH,
            "worker",
            request=fx.request_with(worker_id="other-worker"),
        )
        assert "lease" not in fx.calls

    def test_a_worker_rebuilt_since_the_request_is_refused(self) -> None:
        """Same id, different build: the audit trail would name the worker that
        was chosen while different code performed the work."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.WORKER_DIGEST_MISMATCH,
            "worker",
            request=fx.request_with(worker_digest="digest-of-a-different-build"),
        )

    def test_insufficient_isolation_refuses_a_write(self) -> None:
        """An AMBIENT worker is sufficient only for reads; a write-classified
        operation must refuse with isolation_insufficient rather than run in a
        weaker sandbox than the effect demands."""
        fx = Fixture(operation=OP_WRITE, isolation=IsolationTier.AMBIENT)
        with pytest.raises(InvocationRefused) as caught:
            fx.gateway.admit(fx.context, fx.request, fx.binding)
        refused = caught.value
        assert refused.refusal is InvocationRefusal.WORKER_UNAVAILABLE
        assert refused.detail.get("stage") == "worker"
        cause = refused.__cause__
        assert isinstance(cause, WorkerInvocationRefused)
        assert "isolation_insufficient" in str(cause)
        assert fx.provider_calls == 0
        assert fx.credentials.acquisitions == 0
        assert "lease" not in fx.calls

    def test_a_write_runs_when_the_isolation_is_sufficient(self) -> None:
        """The control for the isolation refusal: the same write under a SEALED
        worker admits, proving the refusal above was the isolation clause."""
        fx = Fixture(operation=OP_WRITE, isolation=IsolationTier.SEALED)
        admission = fx.gateway.admit(fx.context, fx.request, fx.binding)
        assert admission.binding.side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE
        assert fx.credentials.acquisitions == 1


# ----------------------------------------------------------------------
# 8. input
# ----------------------------------------------------------------------


class TestInputStage:
    def test_a_payload_with_no_validator_is_refused_not_forwarded(self) -> None:
        """"Best effort validate" means unvalidated input reaching a real
        system; absence of the validator fails closed for any payload."""
        fx = Fixture(wire_gateway_validator=False, payload={"name": "widget"})
        _refused(fx, InvocationRefusal.INPUT_VALIDATION_UNAVAILABLE, "input")
        assert "lease" not in fx.calls
        assert fx.credentials.attempts == 0, "a credential was minted for unvalidated input"

    def test_a_rejected_payload_is_refused_before_it_is_digested(self) -> None:
        """Input validation precedes the action digest, because digesting first
        would bind whatever arrived. Nothing downstream of input ran."""
        fx = Fixture(
            payload={"name": "x"},
            gateway_validator_problems=("name: not permitted here",),
        )
        refused = _refused(fx, InvocationRefusal.INPUT_INVALID, "input")
        assert "name: not permitted here" in refused.safe_message
        assert "lease" not in fx.calls
        assert "rate" not in fx.calls
        assert fx.credentials.attempts == 0

    def test_a_validator_that_raises_is_a_refusal(self) -> None:
        """Unvalidatable is unusable; only the exception type is disclosed."""
        fx = Fixture(
            payload={"name": "x"},
            gateway_validator_error=RuntimeError("schema store exploded"),
        )
        refused = _refused(fx, InvocationRefusal.INPUT_VALIDATION_UNAVAILABLE, "input")
        assert "RuntimeError" in refused.safe_message
        assert "schema store" not in refused.safe_message


# ----------------------------------------------------------------------
# 9. digest
# ----------------------------------------------------------------------


class TestDigestStage:
    def test_a_declared_digest_that_does_not_match_is_refused(self) -> None:
        """"The payload changed between authorization and invocation" -- the
        caller's declared digest must equal the canonical one."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.PAYLOAD_DIGEST_MISMATCH,
            "digest",
            request=fx.request_with(declared_action_digest="not-what-it-digests-to"),
        )
        assert "lease" not in fx.calls
        assert fx.credentials.attempts == 0

    def test_a_payload_tampered_after_digest_declaration_is_caught(self) -> None:
        """The tampering case in full: the digest was declared over the
        original payload, the request carries a different one, and the gateway
        catches the swap -- no lease read, no credential minted."""
        fx = Fixture(payload={"name": "tampered"})
        declared_for_original = _expected_digest(payload={"name": "original"})
        _refused(
            fx,
            InvocationRefusal.PAYLOAD_DIGEST_MISMATCH,
            "digest",
            request=fx.request_with(declared_action_digest=declared_for_original),
        )
        assert fx.credentials.attempts == 0


# ----------------------------------------------------------------------
# 10. obligations
# ----------------------------------------------------------------------


class TestObligationsStage:
    def test_an_outstanding_obligation_refuses_and_is_not_advisory(self) -> None:
        """"A policy that said 'allow, provided X' and then ran without X did
        not produce the decision anybody made"."""
        fx = Fixture(facts=_facts(obligations=("retain_logs_for_audit",)))
        refused = _refused(fx, InvocationRefusal.OBLIGATION_UNSATISFIED, "obligations")
        assert "retain_logs_for_audit" in refused.safe_message
        assert "lease" not in fx.calls
        assert fx.credentials.attempts == 0


# ----------------------------------------------------------------------
# 11. freshness
# ----------------------------------------------------------------------


class TestFreshnessStage:
    def test_no_remaining_authority_window_refuses_before_any_work(self) -> None:
        """"Starting work that cannot complete within it would leave it running
        past the thing that permitted it" -- an already-passed deadline closes
        the window, and neither the lease nor the rate limiter nor the
        credential provider is ever consulted."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.DEADLINE_EXPIRED,
            "freshness",
            request=fx.request_with(deadline_at=NOW - timedelta(seconds=5)),
        )
        assert "lease" not in fx.calls
        assert "rate" not in fx.calls
        assert fx.credentials.attempts == 0


# ----------------------------------------------------------------------
# 12. lease
# ----------------------------------------------------------------------


class TestLeaseStage:
    def test_an_absent_lease_authority_is_a_refusal(self) -> None:
        """"Without one two workers could run the same node and the record
        would show one"."""
        fx = Fixture(wire_leases=False)
        _refused(fx, InvocationRefusal.LEASE_UNVERIFIABLE, "lease")
        assert "rate" not in fx.calls
        assert fx.credentials.attempts == 0

    def test_a_lease_authority_that_raises_is_a_refusal(self) -> None:
        fx = Fixture(lease_error=RuntimeError("lease store down"))
        refused = _refused(fx, InvocationRefusal.LEASE_UNVERIFIABLE, "lease")
        assert "RuntimeError" in refused.safe_message

    def test_an_unknown_lease_is_refused(self) -> None:
        fx = Fixture(lease_facts=None)
        _refused(fx, InvocationRefusal.LEASE_INVALID, "lease")

    def test_a_lease_not_held_is_refused(self) -> None:
        fx = Fixture(lease_facts=LeaseFacts(held=False, node_id=NODE))
        _refused(fx, InvocationRefusal.LEASE_INVALID, "lease")
        assert "rate" not in fx.calls

    def test_an_expired_lease_is_refused_never_reclaimed(self) -> None:
        """"Reclaiming it is recovery's decision, not this gate's"."""
        fx = Fixture(
            lease_facts=LeaseFacts(
                held=True,
                node_id=NODE,
                worker_id=LEASE_HOLDER,
                expires_at=NOW - timedelta(seconds=1),
            )
        )
        _refused(fx, InvocationRefusal.LEASE_INVALID, "lease")

    def test_a_request_that_cannot_name_its_lease_holder_is_refused(self) -> None:
        """"A request that cannot say who holds the lease cannot be shown to
        hold it" -- absence of lease_holder_id is not a bypass."""
        fx = Fixture()
        _refused(
            fx,
            InvocationRefusal.LEASE_INVALID,
            "lease",
            request=fx.request_with(lease_holder_id=None),
        )

    def test_a_node_leased_to_a_different_participant_is_refused(self) -> None:
        fx = Fixture(
            lease_facts=LeaseFacts(
                held=True,
                node_id=NODE,
                worker_id="some-other-dispatcher",
                expires_at=LATER,
            )
        )
        _refused(fx, InvocationRefusal.LEASE_INVALID, "lease")

    def test_a_live_attempt_other_than_this_one_is_refused(self) -> None:
        """"The live attempt is not the one this request names"."""
        fx = Fixture(
            lease_facts=LeaseFacts(
                held=True,
                node_id=NODE,
                worker_id=LEASE_HOLDER,
                attempt_id=str(AttemptId.new()),
                expires_at=LATER,
            )
        )
        _refused(fx, InvocationRefusal.ATTEMPT_MISMATCH, "lease")
        assert fx.credentials.attempts == 0


# ----------------------------------------------------------------------
# 13. rate
# ----------------------------------------------------------------------


class TestRateStage:
    def test_an_exceeded_budget_refuses_before_a_credential_exists(self) -> None:
        fx = Fixture(rate_exceeded=("tenant_budget_exhausted",))
        refused = _refused(fx, InvocationRefusal.RATE_LIMITED, "rate")
        assert "tenant_budget_exhausted" in refused.safe_message
        assert refused.retryable, "a rate limit is a resource refusal, retryable"
        assert fx.credentials.attempts == 0

    def test_a_limiter_that_cannot_answer_is_a_spent_budget(self) -> None:
        """"A limiter that raises is treated as refusing, because a limiter
        that cannot answer is one whose budget is unknown"."""
        fx = Fixture(rate_error=RuntimeError("limiter backend gone"))
        refused = _refused(fx, InvocationRefusal.RATE_LIMITED, "rate")
        assert "RuntimeError" in refused.safe_message
        assert fx.credentials.attempts == 0


# ----------------------------------------------------------------------
# 14. credential
# ----------------------------------------------------------------------


class TestCredentialStage:
    def test_a_fabric_refusal_travels_with_its_own_reason_code(self) -> None:
        """The fabric's reason code reaches the operator, no secret is minted,
        and the provider is never contacted."""
        fx = Fixture(
            credential_error=CredentialRefused(
                CredentialRefusal.INSUFFICIENT_SCOPE,
                "the provider grants less than the action needs",
            )
        )
        refused = _refused(fx, InvocationRefusal.CREDENTIAL_UNAVAILABLE, "credential")
        assert refused.reasons == ("credential_insufficient_scope",)
        assert fx.credentials.attempts == 1
        assert fx.credentials.acquisitions == 0

    def test_a_provider_exception_is_never_stringified_into_the_refusal(self) -> None:
        """"A provider client's exception routinely carries the request it was
        making, headers included" -- only the type name travels."""
        fx = Fixture(
            credential_error=RuntimeError("Authorization: Bearer hunter2 leaked")
        )
        refused = _refused(fx, InvocationRefusal.CREDENTIAL_UNAVAILABLE, "credential")
        assert "RuntimeError" in refused.safe_message
        assert "hunter2" not in refused.safe_message
        assert fx.credentials.acquisitions == 0

    def test_a_none_answer_is_a_refusal_not_an_anonymous_call(self) -> None:
        fx = Fixture(credential_none=True)
        _refused(fx, InvocationRefusal.CREDENTIAL_UNAVAILABLE, "credential")
        assert fx.credentials.attempts == 1
        assert fx.credentials.acquisitions == 0


# ----------------------------------------------------------------------
# 15. Result integrity
# ----------------------------------------------------------------------


class TestResultIntegrity:
    def test_a_result_describing_another_invocation_becomes_unknown_outcome(self) -> None:
        """"A result naming another binding or attempt belongs to another run
        -- possibly another tenant's. It is never recorded as this one's." The
        foreign success is downgraded to UNKNOWN_OUTCOME, never to success and
        never to a definite failure."""
        fx = Fixture(adapter="foreign")

        outcome = fx.gateway.invoke(fx.context, fx.request, fx.binding)

        assert not outcome.succeeded
        assert outcome.result.outcome is WorkerOutcome.UNKNOWN_OUTCOME
        assert outcome.result.binding_id == BINDING_ID, (
            "the recorded result must be re-keyed to THIS invocation"
        )
        assert outcome.result.detail.get("result_integrity") == "failed"
        assert "does not describe this invocation" in outcome.result.failure.reason
        assert fx.provider_calls == 1
        # The invocation was admitted, so one credential legitimately exists --
        # integrity failure is about the record, not about admission.
        assert fx.credentials.acquisitions == 1
        assert [type(e).__name__ for e in outcome.events] == [
            "InvocationAdmitted",
            "InvocationStarted",
            "InvocationAmbiguous",
        ]
