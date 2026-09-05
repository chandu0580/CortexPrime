"""The final deterministic gate between approved authority and real work.

What this is
--------------
Four components each recorded a fact at a different moment: the capability was
registered and trusted, the principal was authorized, a binding was made, a
worker was selected. Nothing yet checked that they still agree *with each other*
at the instant something is about to happen to a production system.

This does. It is not a new authorization system, not a new registry, not a new
resolver, not a second policy engine. It asks the existing authorities whether
what they said is still true, together, now — and refuses if any one of them
disagrees.

The order is the security property
------------------------------------
    identity → tenancy → binding → authorization → approval → worker
    → input → digest → obligations → freshness → lease → credentials → invoke

Identity first because everything downstream is scoped by it. Input validation
before the action digest, because digesting first would bind whatever arrived.
Credentials **last**, after every authorization check has passed, so a request
that was going to be refused never causes a secret to be minted.

What it never does
--------------------
No retry — Execution owns that (ADR-031). No fallback worker, no re-resolution,
no rebinding, no expiry extension. A mismatch between two authority artifacts is
returned as a refusal naming which one; it is never repaired. Repairing it would
mean executing something other than what was approved, with the approved
artifact's id in the audit trail.

No LLM participates in any decision here, and there is no transport: this governs
invocation, it does not perform it.

Ports, not imports
--------------------
Every collaborator is a Protocol. This module never imports Connectivity — the
composition root implements these over the real services. Absence of a port is a
refusal in every case, never a bypass.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contracts.policy import PolicyEffect, RiskLevel
from backend.contexts.execution.application.instrumentation import (
    NullObserver,
    SafeObserver,
)
from backend.contexts.execution.application.worker_runtime import (
    WorkerAdmission,
    WorkerInvocationRefused,
    WorkerRuntime,
)
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.failure import FailureClass
from backend.contexts.execution.domain.invocation import (
    AuthorityWindow,
    Clock,
    InvocationRefusal,
    InvocationRefused,
    InvocationRequest,
    SystemClock,
)
from backend.contexts.execution.domain.provider_invocation import (
    CancellationToken,
    ProviderAuthority,
)
from backend.contexts.execution.domain.invocation_events import (
    INVOCATION_AGGREGATE_TYPE,
    InvocationAdmitted,
    InvocationAmbiguous,
    InvocationCompleted,
    InvocationRefusedEvent,
    InvocationStarted,
)
from backend.contexts.execution.domain.worker_contract import (
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerOutcome,
)
from backend.contexts.execution.domain.worker_selection import WorkerSelection
from backend.platform.events import EventMetadata

__all__ = [
    "AuthorityFacts",
    "LeaseFacts",
    "CapabilityAuthority",
    "LeaseAuthority",
    "RateLimiter",
    "InvocationAdmission",
    "InvocationOutcome",
    "SecureCapabilityInvocationGateway",
]

log = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# What the authorities answer with
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorityFacts:
    """The authorization position, re-read at invocation time.

    A projection into primitives, exactly as ``BoundCapability`` is. Execution may
    not import ``AuthorizationDecision`` (S2) and should not want to: the
    composition root asks Connectivity and hands back what was answered.

    ``effect`` is the authoritative verdict. There is no field meaning "probably
    fine" and no way to express one — a missing decision arrives as ``DENY``
    because the alternative is a default, and the default would be allow.
    """

    effect: PolicyEffect
    policy_version: str
    decision_digest: str
    capability_digest: str
    tenant_id: str
    principal_id: str

    governance_operation: str
    """What the authorization decided about: the governance verb, from the
    decision itself. Compared against the request's governance verb."""

    provider_operation: str
    """The concrete provider action the binding names. Compared against the
    request's provider operation.

    Carried on the facts rather than read straight off the binding so the
    gateway performs **two independent comparisons** -- decision-vs-request and
    binding-vs-request -- instead of one comparison and one assumption."""
    expires_at: datetime
    binding_key: str

    risk: RiskLevel = RiskLevel.CRITICAL
    """Critical when nobody said. Reuses the platform's single risk model; this
    phase adds no second one."""

    side_effect_class: Optional[SideEffectClass] = None
    effect_semantics: Optional[EffectSemantics] = None
    environment: Optional[ExecutionEnvironment] = None

    delegation_permitted: bool = False
    """Whether the authorization decision sanctions on-behalf-of execution.

    **Fail-closed default, and this is the whole of the Phase 4.1 delegation
    gap.** ``DELEGATION_NOT_AUTHORIZED`` was declared in ADR-040 and never
    raised, because nothing carried an authoritative answer to "may this actor
    act for that principal". The authenticated context was compared against the
    request — which proves the actor is who they say and proves nothing about
    whose authority they are borrowing.

    ``False`` means the decision said nothing, which is not permission.
    """

    delegated_principal_id: Optional[str] = None
    """Whom the decision sanctions acting for. Compared by equality against the
    request's ``on_behalf_of``; a different principal is a refusal, never a
    substitution.

    Populated by the composition root **from the authorization decision**. It is
    never inferred from an owner, a role, a capability, a tenant or a request
    body — every one of those is something the caller can influence."""

    approval_required: bool = False
    approval_present: bool = False
    approval_valid: bool = False
    approval_artifact_id: Optional[str] = None
    approval_bound_digest: Optional[str] = None
    """The action digest the approval was granted against. An approval for
    ``delete_repository`` must not authorize ``create_repository``, and an
    approval for repository A must not authorize repository B — comparing this
    against the computed action digest is what makes that structural rather
    than aspirational."""

    approval_expires_at: Optional[datetime] = None
    obligations: tuple = ()
    reasons: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.effect, PolicyEffect):
            raise ContractViolation("effect must be a PolicyEffect")
        if self.expires_at.tzinfo is None:
            raise ContractViolation("expires_at must be timezone-aware")

    @property
    def allowed(self) -> bool:
        return self.effect is PolicyEffect.ALLOW

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def to_dict(self) -> dict:
        return {
            "effect": self.effect.value,
            "policy_version": self.policy_version,
            "decision_digest": self.decision_digest,
            "capability_digest": self.capability_digest,
            "governance_operation": self.governance_operation,
            "provider_operation": self.provider_operation,
            "risk": self.risk.value,
            "expires_at": self.expires_at.isoformat(),
            "delegation_permitted": self.delegation_permitted,
            "delegated_principal_id": self.delegated_principal_id,
            "approval_required": self.approval_required,
            "approval_valid": self.approval_valid,
            "approval_artifact_id": self.approval_artifact_id,
            "obligations": list(self.obligations),
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class LeaseFacts:
    """Whether the caller actually holds this node, right now.

    Execution owns leases (ADR-031). The gateway reads; it never grants, renews
    or reclaims. Reclaim is recovery's, and a gate that could reclaim could take
    a node away from a worker still writing to production.
    """

    held: bool
    node_id: str
    worker_id: Optional[str] = None
    attempt_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    node_state: Optional[str] = None

    def is_live_at(self, moment: datetime) -> bool:
        return self.held and self.expires_at is not None and moment < self.expires_at


# ----------------------------------------------------------------------
# Ports
# ----------------------------------------------------------------------


@runtime_checkable
class CapabilityAuthority(Protocol):
    """Re-asks Connectivity whether this action is authorized, now.

    Not a cache read. A binding being valid says the *target* is still the one
    chosen; it does not say the principal may still invoke it. Policy changes,
    grants are withdrawn, approvals expire — and every one of those must be able
    to stop work already in flight through the gate.

    Implemented at the composition root over ``CapabilityAuthorizationService``.
    Raising, returning ``None``, or being absent are all refusals.
    """

    def facts_for(
        self, context: Any, request: InvocationRequest, binding: BoundCapability
    ) -> Optional[AuthorityFacts]: ...


@runtime_checkable
class LeaseAuthority(Protocol):
    """Reads the authoritative lease state for one node."""

    def lease_for(
        self, context: Any, execution_id: str, node_id: str
    ) -> Optional[LeaseFacts]: ...


@runtime_checkable
class RateLimiter(Protocol):
    """A seam for future per-tenant/principal/capability/worker limits.

    **Nothing implements this and no limiter is built in this phase.** Its
    absence is treated as "no limit configured" rather than as a refusal, and
    that is a deliberate, stated difference from every other port here: a rate
    limit is a resource control, not an authority control. An unavailable
    *authority* must fail closed; an unconfigured *quota* is simply not a rule
    anybody wrote.

    A limiter that raises is treated as refusing, because a limiter that cannot
    answer is one whose budget is unknown.
    """

    def check(self, context: Any, request: InvocationRequest) -> tuple: ...


@runtime_checkable
class InvocationRecorder(Protocol):
    """Records the outcome on the Execution aggregate.

    A port so the gateway holds no repository and writes no aggregate itself.
    The composition root implements it over ``ExecutionService``.
    """

    def record(
        self,
        context: Any,
        request: InvocationRequest,
        result: WorkerExecutionResult,
    ) -> Any: ...


# ----------------------------------------------------------------------
# Admission and outcome
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class InvocationAdmission:
    """Everything that agreed, and the action they agreed on. Nothing has run."""

    request: InvocationRequest
    binding: BoundCapability
    authority: AuthorityFacts
    worker: WorkerAdmission
    window: AuthorityWindow
    action_digest: str
    validated_payload: Mapping[str, Any]
    deadline_seconds: int
    admitted_at: datetime

    credential: Optional[Any] = field(default=None, repr=False, compare=False)
    """The ``IssuedCredential``, held from admission to invocation and no longer.

    ``repr=False`` and ``compare=False`` so it cannot print or be compared into
    a log. It is **never** included in ``audit_detail`` — only the grant's
    metadata is, and that carries a reference and a fingerprint rather than a
    secret.

    A second, harder guard comes free: ``IssuedCredential.__getstate__`` raises,
    so ``dataclasses.asdict`` and every serialiser built on ``deepcopy`` fail
    loudly on an admission rather than quietly emitting the secret. That is the
    behaviour to want — a noisy failure at the moment somebody tries to write an
    admission down.
    """

    cancellation: Optional[CancellationToken] = field(
        default=None, repr=False, compare=False
    )
    """The token an adapter observes and propagates into transport.

    Created per admission rather than shared, so cancelling one invocation
    cannot stop another. Requesting a stop through it is honest about what it
    achieves: an adapter checks it before sending and the transport honours it
    while connecting, but once an operation may have been transmitted the
    outcome stays ambiguous rather than becoming a cancellation (ADR-042 §22).
    """

    @property
    def selection(self) -> WorkerSelection:
        return self.worker.selection

    def provider_authority(self) -> ProviderAuthority:
        """Project this admission into what an adapter consumes.

        The only place a ``ProviderAuthority`` is built. Everything on it was
        decided by a check above: the binding by resolution, the digest by
        ``_check_action_digest`` over the *validated* payload, the credential by
        the fabric against that digest, the worker by selection. Nothing is
        computed here and nothing is defaulted — this is a projection, and a
        projection that invented a field would be inventing authority.
        """
        from backend.contracts.provider import ProviderRef

        request = self.request
        return ProviderAuthority(
            tenant_id=request.tenant_id,
            principal=request.principal,
            on_behalf_of=request.on_behalf_of,
            environment=request.environment,
            provider=ProviderRef(provider_id=self.binding.provider),
            binding=self.binding,
            action_digest=self.action_digest,
            authorization_digest=self.authority.decision_digest,
            policy_version=self.authority.policy_version,
            approval_ref=self.authority.approval_artifact_id,
            execution_id=str(request.execution_id),
            node_id=request.node_id,
            attempt_id=str(request.attempt_id),
            attempt_number=request.attempt_number,
            worker_id=self.selection.worker_id,
            worker_digest=self.selection.worker_digest,
            selection_id=self.selection.selection_id,
            # The validated payload, not the request's. The adapter receives
            # exactly the bytes the action digest covers.
            payload=self.validated_payload,
            authority_expires_at=self.window.effective_expiry,
            deadline_seconds=self.deadline_seconds,
            idempotency_key=request.idempotency_key,
            execution_key=request.execution_key,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            credential=self.credential,
            cancellation=self.cancellation,
            admitted_at=self.admitted_at,
        )

    @property
    def credential_grant(self) -> Optional[Any]:
        """The safe half of the credential: reference, scope, expiry, fingerprint."""
        return getattr(self.credential, "grant", None)

    def audit_detail(self) -> dict:
        """Full attribution for one invocation. No secret can reach this.

        Built from digests and ids only — there is no branch here that can emit a
        credential, a token or a payload, because none of them is in scope.
        """
        return {
            **self.worker.audit_detail(),
            "attempt_id": str(self.request.attempt_id),
            "attempt_number": self.request.attempt_number,
            "node_id": self.request.node_id,
            "action_digest": self.action_digest,
            "policy_version": self.authority.policy_version,
            "authorization_effect": self.authority.effect.value,
            "authorization_digest": self.authority.decision_digest,
            "approval_artifact_id": self.authority.approval_artifact_id,
            "risk": self.authority.risk.value,
            "effect_semantics": self.binding.effect_semantics.value,
            "side_effect_class": self.binding.side_effect_class.value,
            "effective_expiry": self.window.effective_expiry.isoformat(),
            "expiry_limited_by": self.window.binding_expiry_source,
            "deadline_seconds": self.deadline_seconds,
            "correlation_id": self.request.correlation_id,
            "trace_id": self.request.trace_id,
            "on_behalf_of": (
                self.request.on_behalf_of.principal_id
                if self.request.on_behalf_of
                else None
            ),
            # The credential's *metadata* only. A reference, a scope, an expiry
            # and a non-reversible fingerprint — every one safe to write down,
            # and the material deliberately unreachable from here.
            **(
                {
                    "credential_ref": grant.ref.value,
                    "credential_type": grant.credential_type.value,
                    "credential_scope": grant.scope.to_dict(),
                    "credential_expires_at": grant.expires_at.isoformat(),
                    "credential_fingerprint": grant.fingerprint,
                }
                if (grant := self.credential_grant) is not None
                else {"credential_ref": None}
            ),
        }


@dataclass(frozen=True)
class InvocationOutcome:
    """What happened, and the events that say so."""

    result: WorkerExecutionResult
    admission: InvocationAdmission
    events: tuple = ()
    recorded: bool = False

    @property
    def succeeded(self) -> bool:
        return self.result.succeeded

    @property
    def outcome_is_known(self) -> bool:
        return self.result.outcome_is_known

    def to_dict(self) -> dict:
        return {
            "outcome": self.result.outcome.value,
            "outcome_known": self.result.outcome_is_known,
            "result_digest": self.result.result_digest,
            "recorded": self.recorded,
            "events": [type(e).EVENT_TYPE for e in self.events],
            **self.admission.audit_detail(),
        }


# ----------------------------------------------------------------------
# The gateway
# ----------------------------------------------------------------------


class SecureCapabilityInvocationGateway:
    """The one authoritative path from an approved action to a running one.

    Holds no repository, no registry and no aggregate. It reads authorities,
    decides admission, invokes once through the Phase 3.3.2 runtime, checks what
    came back, and hands the result to Execution to record.
    """

    #: The order refusals are reported in. Fixed so that a request wrong in three
    #: ways always names the same one first -- a refusal reason that varied by
    #: evaluation order would make two identical requests look like two problems.
    STAGES = (
        "identity",
        "tenancy",
        "binding",
        "authorization",
        "approval",
        "worker",
        "input",
        "digest",
        "obligations",
        "freshness",
        "lease",
        "rate",
        "credential",
    )

    def __init__(
        self,
        *,
        worker_runtime: WorkerRuntime,
        authority: Optional[CapabilityAuthority] = None,
        leases: Optional[LeaseAuthority] = None,
        recorder: Optional[InvocationRecorder] = None,
        input_validator: Optional[Any] = None,
        credentials: Optional[Any] = None,
        rate_limiter: Optional[RateLimiter] = None,
        outbox: Optional[Any] = None,
        audit: Optional[Any] = None,
        observer: Optional[Any] = None,
        clock: Optional[Clock] = None,
    ) -> None:
        if not isinstance(worker_runtime, WorkerRuntime):
            raise ContractViolation(
                "the gateway invokes through the Phase 3.3.2 worker runtime; without "
                "it there is no worker selection, no TOCTOU re-check and no adapter "
                "boundary, and the gate would be guarding nothing"
            )
        self._workers = worker_runtime
        self._authority = authority
        self._leases = leases
        self._recorder = recorder
        self._input_validator = input_validator
        """The gateway's own validator, not the runtime's. Both fail closed and
        both run: this one is the authority boundary, the runtime's is defence in
        depth. Sharing one instance would mean a single wiring mistake removes
        both, which is precisely what defence in depth is supposed to survive."""

        self._credentials = credentials
        self._rate_limiter = rate_limiter
        self._outbox = outbox
        self._audit = audit
        self._observer = SafeObserver(observer or NullObserver())
        self._clock = clock or SystemClock()

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------

    def admit(
        self,
        context: Any,
        request: InvocationRequest,
        binding: BoundCapability,
    ) -> InvocationAdmission:
        """Run the whole chain. Returns only when every link held."""
        now = self._clock.now()

        self._check_identity(context, request)
        self._check_tenancy(context, request, binding)
        self._check_binding_agreement(request, binding, now)

        authority = self._check_authorization(context, request, binding, now)
        # Delegation immediately after authorization, because the authorization
        # decision is the only thing that can answer it. Before worker selection,
        # because selecting a worker for an invocation nobody may make is work
        # done on behalf of a refusal.
        self._check_delegation(request, authority)
        worker = self._check_worker(context, request, binding, now)

        validated = self._validate_input(context, request, binding)
        action_digest = self._check_action_digest(request, authority, validated)
        self._check_approval(request, authority, action_digest, now)
        self._check_obligations(request, authority)

        window = self._window(binding, authority, request)
        deadline_seconds = self._check_freshness(request, window, now)

        self._check_lease(context, request, worker, now)
        self._check_rate(context, request)
        # Credentials last: a request that was going to be refused must never
        # cause a secret to be minted.
        credential = self._acquire_credential(
            context,
            request,
            binding,
            authority=authority,
            action_digest=action_digest,
            window=window,
            now=now,
        )

        return InvocationAdmission(
            request=request,
            binding=binding,
            authority=authority,
            worker=worker,
            window=window,
            action_digest=action_digest,
            validated_payload=dict(validated),
            deadline_seconds=deadline_seconds,
            admitted_at=now,
            credential=credential,
            cancellation=CancellationToken(),
        )

    # -- 1. identity -----------------------------------------------------

    def _check_identity(self, context: Any, request: InvocationRequest) -> None:
        identity = getattr(context, "identity", None)
        principal = getattr(identity, "principal", None)
        if principal is None:
            raise self._refuse(
                request,
                InvocationRefusal.IDENTITY_MISSING,
                "the context carries no authenticated principal",
                stage="identity",
            )
        if principal.principal_id != request.principal_id:
            # Never trust a principal supplied alongside the request. The
            # authenticated one is the only one that was proved.
            raise self._refuse(
                request,
                InvocationRefusal.PRINCIPAL_MISMATCH,
                "the request names a principal the context did not authenticate",
                stage="identity",
            )
        on_behalf = getattr(identity, "on_behalf_of", None)
        declared = request.on_behalf_of
        if (on_behalf is None) != (declared is None) or (
            on_behalf is not None
            and declared is not None
            and on_behalf.principal_id != declared.principal_id
        ):
            # Actor and delegated principal stay distinct. Flattening them loses
            # which of the two a decision was made about.
            raise self._refuse(
                request,
                InvocationRefusal.PRINCIPAL_MISMATCH,
                "the delegation chain in the request differs from the authenticated one",
                stage="identity",
            )

    # -- 2. tenancy ------------------------------------------------------

    def _check_tenancy(
        self, context: Any, request: InvocationRequest, binding: BoundCapability
    ) -> None:
        tenant = getattr(context, "tenant_id", None)
        if not tenant:
            raise self._refuse(
                request,
                InvocationRefusal.TENANT_UNKNOWN,
                "the context carries no tenant; there is no ambient tenant, no "
                "default, and no system tenant",
                stage="tenancy",
            )
        if getattr(context, "is_platform_internal", False):
            # A platform-internal context has no tenant of its own to match
            # against, so it must never be usable to reach tenant capabilities.
            raise self._refuse(
                request,
                InvocationRefusal.TENANT_UNKNOWN,
                "a platform-internal context cannot invoke a tenant capability",
                stage="tenancy",
            )
        if tenant != request.tenant_id or binding.tenant_id != request.tenant_id:
            raise self._refuse(
                request,
                InvocationRefusal.TENANT_MISMATCH,
                "the context, the request and the binding do not name one tenant",
                stage="tenancy",
            )

    # -- 3. the binding agrees with the request ---------------------------

    def _check_binding_agreement(
        self, request: InvocationRequest, binding: BoundCapability, now: datetime
    ) -> None:
        """Every identifying field must match. Mismatches are never repaired."""
        if not isinstance(binding, BoundCapability):
            raise self._refuse(
                request,
                InvocationRefusal.GATEWAY_MISCONFIGURED,
                "no capability binding was supplied",
                stage="binding",
            )
        if binding.binding_id != request.binding_id:
            raise self._refuse(
                request,
                InvocationRefusal.BINDING_MISMATCH,
                "the request names a different binding than the one supplied",
                stage="binding",
            )
        if binding.binding_digest != request.binding_digest:
            raise self._refuse(
                request,
                InvocationRefusal.BINDING_MISMATCH,
                "the binding digest in the request does not match the binding",
                stage="binding",
            )
        if binding.capability_ref != request.capability_ref:
            raise self._refuse(
                request,
                InvocationRefusal.CAPABILITY_MISMATCH,
                "the request and the binding name different capabilities",
                stage="binding",
            )
        if binding.capability_digest != request.capability_digest:
            raise self._refuse(
                request,
                InvocationRefusal.CAPABILITY_MISMATCH,
                "the capability contract digest changed since the request was built",
                stage="binding",
            )
        # The concrete action. ``BoundCapability.operation`` is the provider
        # operation, so this is binding-vs-request on the thing that will
        # actually execute -- a provider operation swapped after the binding was
        # sealed cannot survive here.
        if binding.operation != request.operation:
            raise self._refuse(
                request,
                InvocationRefusal.OPERATION_MISMATCH,
                "the request and the binding name different provider operations",
                stage="binding",
            )
        if (
            binding.governance_operation is not None
            and request.governance_operation is not None
            and binding.governance_operation != request.governance_operation
        ):
            raise self._refuse(
                request,
                InvocationRefusal.OPERATION_MISMATCH,
                "the request and the binding name different governance operations",
                stage="binding",
            )
        if binding.principal_id != request.principal_id:
            raise self._refuse(
                request,
                InvocationRefusal.PRINCIPAL_MISMATCH,
                "the binding was made for a different principal",
                stage="binding",
            )
        if (binding.execution_id or None) != str(request.execution_id):
            raise self._refuse(
                request,
                InvocationRefusal.EXECUTION_MISMATCH,
                "the binding was made for a different execution",
                stage="binding",
            )
        if (binding.node_id or None) != request.node_id:
            raise self._refuse(
                request,
                InvocationRefusal.EXECUTION_MISMATCH,
                "the binding was made for a different node",
                stage="binding",
            )
        if binding.environment is None:
            raise self._refuse(
                request,
                InvocationRefusal.ENVIRONMENT_UNKNOWN,
                "the binding does not state an environment; unstated is not a "
                "wildcard, and a development binding must not reach production",
                stage="binding",
            )
        if binding.environment is not request.environment:
            raise self._refuse(
                request,
                InvocationRefusal.ENVIRONMENT_MISMATCH,
                "the request and the binding name different environments",
                stage="binding",
            )
        if binding.effect_semantics is EffectSemantics.UNKNOWN:
            # UNKNOWN stays fail-closed. No worker's opinion upgrades it.
            raise self._refuse(
                request,
                InvocationRefusal.EFFECT_UNDECLARED,
                "the capability does not declare whether repeating it is safe; an "
                "undeclared repeat is what turns one production change into two",
                stage="binding",
            )
        if not binding.is_live_at(now):
            raise self._refuse(
                request,
                InvocationRefusal.BINDING_EXPIRED,
                "the binding has expired; expiry is never extended at the point of use",
                stage="binding",
            )

    # -- 4. authorization -------------------------------------------------

    def _check_authorization(
        self,
        context: Any,
        request: InvocationRequest,
        binding: BoundCapability,
        now: datetime,
    ) -> AuthorityFacts:
        if self._authority is None:
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_UNAVAILABLE,
                "no authorization authority is wired; the gateway will not act on "
                "an authorization it cannot have confirmed",
                stage="authorization",
            )
        try:
            facts = self._authority.facts_for(context, request, binding)
        except Exception as exc:  # noqa: BLE001 - unverifiable is unusable
            log.warning("authorization re-check failed", exc_info=True)
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_UNAVAILABLE,
                f"authorization could not be established ({type(exc).__name__})",
                stage="authorization",
            ) from exc

        if facts is None:
            # Missing is never allow.
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_MISSING,
                "no authorization decision covers this action",
                stage="authorization",
            )
        if not isinstance(facts, AuthorityFacts):
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_UNAVAILABLE,
                "the authorization authority answered with something uninterpretable",
                stage="authorization",
            )
        if facts.effect is PolicyEffect.DENY:
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_DENIED,
                "policy denies this action",
                stage="authorization",
                reasons=facts.reasons,
            )
        if facts.effect is PolicyEffect.REQUIRE_APPROVAL and not facts.approval_valid:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_REQUIRED,
                "this action requires an approval that is not present or not valid",
                stage="approval",
                reasons=facts.reasons,
            )
        if facts.effect not in (PolicyEffect.ALLOW, PolicyEffect.REQUIRE_APPROVAL):
            # Anything else -- including a value added later -- is not an allow.
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_DENIED,
                f"policy returned {facts.effect.value}, which is not permission to act",
                stage="authorization",
                reasons=facts.reasons,
            )
        if not facts.is_live_at(now):
            raise self._refuse(
                request,
                InvocationRefusal.AUTHORIZATION_EXPIRED,
                "the authorization decision has expired",
                stage="authorization",
            )
        if facts.tenant_id != request.tenant_id:
            raise self._refuse(
                request,
                InvocationRefusal.TENANT_MISMATCH,
                "the authorization was made for a different tenant",
                stage="authorization",
            )
        if facts.principal_id != request.principal_id:
            raise self._refuse(
                request,
                InvocationRefusal.PRINCIPAL_MISMATCH,
                "the authorization was made for a different principal",
                stage="authorization",
            )
        # Two vocabularies, two comparisons, neither standing in for the
        # other. This is the check that blocked Phase 5.5: it compared the
        # decision's governance verb against the request's provider operation
        # and refused every invocation, because "invoke" is never equal to
        # "repository.get_repository".
        if request.governance_operation is None:
            # Absent is refused, not tolerated. A request that cannot say which
            # governed action it is cannot be matched against a decision.
            raise self._refuse(
                request,
                InvocationRefusal.OPERATION_MISMATCH,
                "the request does not state which governance operation it is",
                stage="authorization",
            )
        if facts.governance_operation != request.governance_operation:
            raise self._refuse(
                request,
                InvocationRefusal.OPERATION_MISMATCH,
                "the authorization was made for a different governance operation",
                stage="authorization",
            )
        if facts.provider_operation != request.operation:
            raise self._refuse(
                request,
                InvocationRefusal.OPERATION_MISMATCH,
                "the authorization covers a different provider operation",
                stage="authorization",
            )
        if facts.capability_digest != request.capability_digest:
            raise self._refuse(
                request,
                InvocationRefusal.CAPABILITY_MISMATCH,
                "the authorization named a different capability contract",
                stage="authorization",
            )
        if (
            facts.environment is not None
            and facts.environment is not request.environment
        ):
            raise self._refuse(
                request,
                InvocationRefusal.ENVIRONMENT_MISMATCH,
                "the authorization was made for a different environment",
                stage="authorization",
            )
        if (
            binding.authorization_policy_version
            and facts.policy_version != binding.authorization_policy_version
        ):
            # The rules changed under a live binding. Not necessarily a denial --
            # but not something to proceed through silently either.
            raise self._refuse(
                request,
                InvocationRefusal.POLICY_VERSION_CHANGED,
                "policy has changed since this binding was authorized; the action "
                "must be re-authorized under the current policy",
                stage="authorization",
            )
        return facts

    # -- 4b. delegation -----------------------------------------------------

    def _check_delegation(
        self, request: InvocationRequest, facts: AuthorityFacts
    ) -> None:
        """Whether this actor may act for the principal it names. **Phase 4.4.**

        The gap ADR-040 left open. ``_check_identity`` proves the delegation
        chain in the request matches the one the *context* authenticated — which
        establishes that the caller is not lying about the request, and
        establishes nothing about whether the delegation was ever permitted.
        Both are needed and they are different questions:

            identity     "is this actor who they say, acting for whom they say?"
            delegation   "was this actor ever allowed to act for that principal?"

        Three refusals, and the first is the one that was missing entirely:

        * the request delegates and the decision does not sanction delegation;
        * the decision sanctions delegation for a *different* principal;
        * the decision names a delegated principal and the request delegates to
          nobody — a decision made about somebody else's authority being used to
          perform an action as oneself.

        There is deliberately no fourth branch that repairs a mismatch. A
        delegated principal is not something to be corrected at the point of
        use; it is the identity the whole action was authorized under.
        """
        declared = request.on_behalf_of
        sanctioned = facts.delegated_principal_id

        if declared is None:
            if sanctioned is not None:
                raise self._refuse(
                    request,
                    InvocationRefusal.DELEGATION_NOT_AUTHORIZED,
                    "the authorization was made for delegated execution and this "
                    "request delegates to nobody; the action would run under the "
                    "actor's own authority against a decision about somebody "
                    "else's",
                    stage="identity",
                )
            return

        if not facts.delegation_permitted:
            # The default, and the point of the default: a decision that said
            # nothing about delegation has not permitted it.
            raise self._refuse(
                request,
                InvocationRefusal.DELEGATION_NOT_AUTHORIZED,
                "this request acts on behalf of another principal and the "
                "authorization decision does not sanction delegation; absence "
                "is not permission",
                stage="identity",
            )
        if sanctioned is None:
            raise self._refuse(
                request,
                InvocationRefusal.DELEGATION_NOT_AUTHORIZED,
                "delegation is permitted in principle but the decision names no "
                "delegated principal; an unbound delegation would authorize "
                "acting for anybody",
                stage="identity",
            )
        if sanctioned != declared.principal_id:
            raise self._refuse(
                request,
                InvocationRefusal.DELEGATION_NOT_AUTHORIZED,
                "the request acts for a different principal than the "
                "authorization sanctioned",
                stage="identity",
            )

    # -- 5. approval binding ----------------------------------------------

    def _check_approval(
        self,
        request: InvocationRequest,
        facts: AuthorityFacts,
        action_digest: str,
        now: datetime,
    ) -> None:
        """An approval must be *for this action*, not merely present.

        "There is some approval" is not sufficient and never has been. An
        approval for ``github.delete_repository`` must not authorize
        ``github.create_repository``; an approval for repository A must not
        authorize repository B. Both are the same check: the approval was granted
        against an action digest, and that digest covers the capability, the
        operation, the validated input, the tenant, the principal and the
        environment.
        """
        if not facts.approval_required and facts.effect is not PolicyEffect.REQUIRE_APPROVAL:
            return
        if not facts.approval_present:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_MISSING,
                "this action requires approval and none is recorded",
                stage="approval",
            )
        if not facts.approval_valid:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_MISSING,
                "the recorded approval is not valid for this action",
                stage="approval",
            )
        if facts.approval_expires_at is not None and now >= facts.approval_expires_at:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_EXPIRED,
                "the approval has expired; an expired approval is not a weaker "
                "approval, it is none",
                stage="approval",
            )
        if facts.approval_bound_digest is None:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_MISMATCH,
                "the approval is not bound to a specific action; an unbound "
                "approval would authorize anything this capability can do",
                stage="approval",
            )
        if facts.approval_bound_digest != action_digest:
            raise self._refuse(
                request,
                InvocationRefusal.APPROVAL_MISMATCH,
                "the approval was granted for a different action than the one "
                "about to run",
                stage="approval",
            )

    # -- 6. worker --------------------------------------------------------

    def _check_worker(
        self,
        context: Any,
        request: InvocationRequest,
        binding: BoundCapability,
        now: datetime,
    ) -> WorkerAdmission:
        """Delegates to Phase 3.3.2. This phase adds no second worker system.

        ``now`` is threaded through rather than letting the runtime read its own
        clock. Two readings would let a binding pass the gateway's expiry check
        at one instant and fail the runtime's at another — and the gap between
        them is a gap where the same request is simultaneously live and expired.
        """
        try:
            worker_request = self._worker_request(
                request, binding, payload=request.payload, deadline=None
            )
            admission = self._workers.assert_invocable(context, worker_request, now=now)
        except WorkerInvocationRefused as exc:
            raise self._refuse(
                request,
                _WORKER_REFUSALS.get(exc.reason_code, InvocationRefusal.WORKER_UNAVAILABLE),
                exc.reason_code,
                stage="worker",
            ) from exc

        if admission.selection.worker_id != request.worker_id:
            raise self._refuse(
                request,
                InvocationRefusal.WORKER_SELECTION_MISMATCH,
                "the worker selected now is not the one the request names",
                stage="worker",
            )
        if admission.selection.worker_digest != request.worker_digest:
            # Same id, different build. The audit trail would name the worker
            # that was chosen while different code performed the work.
            raise self._refuse(
                request,
                InvocationRefusal.WORKER_DIGEST_MISMATCH,
                "the worker implementation changed since the request was built",
                stage="worker",
            )
        return admission

    # -- 7. input ----------------------------------------------------------

    def _validate_input(
        self, context: Any, request: InvocationRequest, binding: BoundCapability
    ) -> Mapping[str, Any]:
        """The authoritative pre-execution validation boundary.

        A worker may validate too — that is defence in depth, not authority. If
        validation cannot be performed, the answer is refusal: "best effort
        validate" means unvalidated input reaching a real system whenever the
        validator happens to be unavailable.
        """
        validator = self._input_validator
        if validator is None:
            if request.payload:
                raise self._refuse(
                    request,
                    InvocationRefusal.INPUT_VALIDATION_UNAVAILABLE,
                    "no input validator is wired and this action carries input",
                    stage="input",
                )
            return {}
        try:
            problems = validator.validate(binding, request.payload)
        except Exception as exc:  # noqa: BLE001 - unvalidatable is unusable
            raise self._refuse(
                request,
                InvocationRefusal.INPUT_VALIDATION_UNAVAILABLE,
                f"input could not be validated ({type(exc).__name__})",
                stage="input",
            ) from exc
        if problems:
            raise self._refuse(
                request,
                InvocationRefusal.INPUT_INVALID,
                "; ".join(str(p) for p in problems)[:400],
                stage="input",
            )
        return dict(request.payload)

    # -- 8. the action digest ----------------------------------------------

    def _check_action_digest(
        self,
        request: InvocationRequest,
        facts: AuthorityFacts,
        validated: Mapping[str, Any],
    ) -> str:
        """Compute the canonical digest, and refuse if the caller disagrees.

        Computed over the *validated* payload, after validation, and frozen from
        here. Nothing downstream may rewrite the payload: the adapter receives
        exactly what was digested, so what was authorized and what executes are
        the same bytes.
        """
        digest = request.action_digest(
            policy_version=facts.policy_version, payload=validated
        )
        if (
            request.declared_action_digest is not None
            and request.declared_action_digest != digest
        ):
            raise self._refuse(
                request,
                InvocationRefusal.PAYLOAD_DIGEST_MISMATCH,
                "the action does not digest to what the request declared; the "
                "payload changed between authorization and invocation",
                stage="digest",
            )
        return digest

    # -- 9. obligations -----------------------------------------------------

    def _check_obligations(
        self, request: InvocationRequest, facts: AuthorityFacts
    ) -> None:
        """Unsatisfied obligations refuse. Reuses the platform's obligation model.

        An obligation the gateway cannot discharge is not an advisory note. A
        policy that said "allow, provided X" and then ran without X did not
        produce the decision anybody made.
        """
        outstanding = tuple(o for o in facts.obligations if o)
        if outstanding:
            raise self._refuse(
                request,
                InvocationRefusal.OBLIGATION_UNSATISFIED,
                "the authorization carries obligations this gateway cannot "
                f"discharge: {', '.join(str(o) for o in outstanding)[:200]}",
                stage="obligations",
            )

    # -- 10. freshness -------------------------------------------------------

    @staticmethod
    def _window(
        binding: BoundCapability,
        facts: AuthorityFacts,
        request: InvocationRequest,
    ) -> AuthorityWindow:
        return AuthorityWindow(
            binding_expires_at=binding.expires_at,
            authorization_expires_at=facts.expires_at,
            approval_expires_at=facts.approval_expires_at,
            deadline_at=request.deadline_at,
        )

    def _check_freshness(
        self, request: InvocationRequest, window: AuthorityWindow, now: datetime
    ) -> int:
        """Refuse before invoking work that cannot finish inside its authority."""
        remaining = window.remaining_seconds(now)
        if remaining <= 0:
            raise self._refuse(
                request,
                InvocationRefusal.DEADLINE_EXPIRED,
                f"no authority window remains (limited by {window.binding_expiry_source}); "
                "starting work that cannot complete within it would leave it running "
                "past the thing that permitted it",
                stage="freshness",
            )
        return remaining

    # -- 11. lease ------------------------------------------------------------

    def _check_lease(
        self,
        context: Any,
        request: InvocationRequest,
        worker: WorkerAdmission,
        now: datetime,
    ) -> None:
        """A valid lease is required. The gateway never grants or reclaims one."""
        if self._leases is None:
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_UNVERIFIABLE,
                "no lease authority is wired; without one two workers could run "
                "the same node and the record would show one",
                stage="lease",
            )
        try:
            facts = self._leases.lease_for(
                context, str(request.execution_id), request.node_id
            )
        except Exception as exc:  # noqa: BLE001
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_UNVERIFIABLE,
                f"the lease could not be read ({type(exc).__name__})",
                stage="lease",
            ) from exc

        if facts is None or not facts.held:
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_INVALID,
                "no live lease is held for this node",
                stage="lease",
            )
        if not facts.is_live_at(now):
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_INVALID,
                "the lease for this node has expired; reclaiming it is recovery's "
                "decision, not this gate's",
                stage="lease",
            )
        # The lease holder, compared against the lease holder.
        #
        # ADR-036 §9: Execution owns the lease and a worker never holds one of
        # its own. So ``facts.worker_id`` is the *execution participant* the
        # aggregate leased the node to -- the dispatcher -- while
        # ``worker.worker_id`` is the provider implementation that was selected.
        # Comparing those two refused every invocation, because they are answers
        # to different questions and are never equal by construction.
        #
        # Nothing here is relaxed: a request that does not name its lease holder
        # is refused, and a request naming the wrong one is refused. What changed
        # is only *which* identity the stored holder is compared against.
        if request.lease_holder_id is None:
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_INVALID,
                "the request does not name the lease holder it runs under; a "
                "request that cannot say who holds the lease cannot be shown to "
                "hold it",
                stage="lease",
            )
        if facts.worker_id is not None and facts.worker_id != request.lease_holder_id:
            raise self._refuse(
                request,
                InvocationRefusal.LEASE_INVALID,
                "the node is leased to a different execution participant",
                stage="lease",
            )
        if facts.attempt_id is not None and facts.attempt_id != str(request.attempt_id):
            raise self._refuse(
                request,
                InvocationRefusal.ATTEMPT_MISMATCH,
                "the live attempt is not the one this request names",
                stage="lease",
            )

    # -- 12. rate --------------------------------------------------------------

    def _check_rate(self, context: Any, request: InvocationRequest) -> None:
        if self._rate_limiter is None:
            return  # No limiter configured. A quota nobody wrote is not a rule.
        try:
            exceeded = self._rate_limiter.check(context, request)
        except Exception as exc:  # noqa: BLE001 - an unanswerable budget is spent
            raise self._refuse(
                request,
                InvocationRefusal.RATE_LIMITED,
                f"the rate limiter could not answer ({type(exc).__name__})",
                stage="rate",
            ) from exc
        if exceeded:
            raise self._refuse(
                request,
                InvocationRefusal.RATE_LIMITED,
                "; ".join(str(e) for e in exceeded)[:200],
                stage="rate",
            )

    # -- 13. credentials --------------------------------------------------------

    def _acquire_credential(
        self,
        context: Any,
        request: InvocationRequest,
        binding: BoundCapability,
        *,
        authority: "AuthorityFacts",
        action_digest: str,
        window: AuthorityWindow,
        now: datetime,
    ) -> Optional[Any]:
        """Last, and only if everything else passed.

        Placed at the end of the chain deliberately (ADR-038 §2): a request that
        was going to be refused must never cause a secret to be minted. Moving
        this earlier for convenience would mean every refused invocation left a
        live credential behind at some provider.

        The request carries the **action digest**, not just the binding. A
        provider given only the binding could return a credential for a different
        resource within the same capability, which is the confused deputy in its
        original form.

        Returns the issued credential so ``invoke`` can hand the material
        straight to the transport and drop it. It is **not** stored on the
        admission: an admission is audited, and a credential on an audited object
        is a credential in the audit log one refactor from now.
        """
        if self._credentials is None:
            # No adapter in this deployment requires one. Stated rather than
            # assumed: this is not "credentials were checked and none needed".
            return None

        from backend.contracts.credential import CredentialScope
        from backend.platform.credentials import CredentialRefused, CredentialRequest

        # Lifetime is bounded by the *already computed* authority window, so a
        # credential can never outlive the permission that asked for it.
        lifetime = max(1, min(window.remaining_seconds(now), 900))
        try:
            credential_request = CredentialRequest(
                tenant_id=request.tenant_id,
                principal=request.principal,
                on_behalf_of=request.on_behalf_of,
                # From the authorization decision, checked by ``_check_delegation``
                # above. Never from the request: the request is the thing being
                # authorized, and it cannot vouch for itself.
                delegation_authorized=(
                    request.on_behalf_of is not None and authority.delegation_permitted
                ),
                provider=binding.provider,
                environment=request.environment,
                scope=CredentialScope.of(
                    f"{binding.operation}", resource=binding.capability_ref
                ),
                capability_ref=binding.capability_ref,
                capability_digest=binding.capability_digest,
                operation=binding.operation,
                binding_id=binding.binding_id,
                binding_digest=binding.binding_digest,
                action_digest=action_digest,
                execution_id=str(request.execution_id),
                node_id=request.node_id,
                attempt_id=str(request.attempt_id),
                authorization_digest=authority.decision_digest,
                authorization_expires_at=authority.expires_at,
                policy_version=authority.policy_version,
                approval_required=authority.approval_required,
                approval_artifact_id=authority.approval_artifact_id,
                approval_expires_at=authority.approval_expires_at,
                requested_lifetime_seconds=lifetime,
                deadline_at=window.effective_expiry,
                correlation_id=request.correlation_id,
                causation_id=request.causation_id,
            )
        except Exception as exc:  # noqa: BLE001 - an unbuildable request refuses
            raise self._refuse(
                request,
                InvocationRefusal.CREDENTIAL_UNAVAILABLE,
                f"a credential request could not be formed ({type(exc).__name__})",
                stage="credential",
            ) from None

        try:
            issued = self._credentials.scoped_credential(context, credential_request)
        except CredentialRefused as refused:
            # The fabric's own reason code travels, so an operator sees
            # 'credential_insufficient_scope' rather than a generic failure.
            raise self._refuse(
                request,
                InvocationRefusal.CREDENTIAL_UNAVAILABLE,
                refused.safe_message,
                stage="credential",
                reasons=(refused.reason_code,),
            ) from None
        except Exception as exc:  # noqa: BLE001
            # Never str(exc) here: a provider client's exception routinely
            # carries the request it was making, headers included.
            raise self._refuse(
                request,
                InvocationRefusal.CREDENTIAL_UNAVAILABLE,
                f"a scoped credential could not be obtained ({type(exc).__name__})",
                stage="credential",
            ) from None
        if issued is None:
            raise self._refuse(
                request,
                InvocationRefusal.CREDENTIAL_UNAVAILABLE,
                "no scoped credential is available for this action",
                stage="credential",
            )
        return issued

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(
        self,
        context: Any,
        request: InvocationRequest,
        binding: BoundCapability,
    ) -> InvocationOutcome:
        """Admit, invoke exactly once, check the result, record it.

        No loop, no retry, no fallback. When this returns, either one invocation
        happened or none did, and the events say which.
        """
        try:
            admission = self.admit(context, request, binding)
        except InvocationRefused as refused:
            self._emit_refusal(context, request, refused)
            raise

        events = [self._admitted_event(context, admission)]
        self._publish(context, request, events)

        started = self._started_event(context, admission)
        self._publish(context, request, [started])
        events.append(started)

        worker_request = self._worker_request(
            request,
            binding,
            payload=admission.validated_payload,
            deadline=admission.deadline_seconds,
        )
        try:
            result = self._workers.invoke(
                context,
                worker_request,
                selection=admission.selection,
                now=admission.admitted_at,
                # Phase 4.3. The credential material travels here and nowhere
                # else: an adapter receives it for the moment of use and hands
                # it to transport, and nothing in between writes it down.
                authority=admission.provider_authority(),
            )
        except WorkerInvocationRefused as exc:
            # The runtime's final pre-action check refused. Nothing ran.
            refused = self._refuse(
                request,
                _WORKER_REFUSALS.get(
                    exc.reason_code, InvocationRefusal.WORKER_UNAVAILABLE
                ),
                exc.reason_code,
                stage="worker",
            )
            self._emit_refusal(context, request, refused)
            raise refused from exc

        result = self._check_result(admission, result)
        outcome_events = self._outcome_events(context, admission, result)
        self._publish(context, request, outcome_events)
        events.extend(outcome_events)

        recorded = self._record(context, request, result)
        self._audit_invocation(context, admission, result)
        return InvocationOutcome(
            result=result,
            admission=admission,
            events=tuple(events),
            recorded=recorded,
        )

    # -- result integrity ------------------------------------------------

    def _check_result(
        self, admission: InvocationAdmission, result: WorkerExecutionResult
    ) -> WorkerExecutionResult:
        """A result must be about the thing that ran. Otherwise it is not a result.

        A malformed or foreign result becomes ``UNKNOWN_OUTCOME``, never a
        failure and never a success. The work may well have happened; what is
        missing is a trustworthy account of it, and recording an untrustworthy
        account as success is how a half-applied change is marked done.
        """
        request = admission.request
        if not isinstance(result, WorkerExecutionResult):
            return WorkerExecutionResult.unknown(
                binding_id=request.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=admission.admitted_at,
                reason=(
                    f"the runtime returned {type(result).__name__}, not a "
                    "WorkerExecutionResult; what happened is unknown"
                ),
            )
        problems = []
        if result.binding_id != request.binding_id:
            problems.append("binding")
        if result.attempt_id != str(request.attempt_id):
            problems.append("attempt")
        if result.outcome is not WorkerOutcome.SUCCESS and result.failure is None:
            problems.append("unclassified failure")
        if problems:
            # A result naming another binding or attempt belongs to another run --
            # possibly another tenant's. It is never recorded as this one's.
            return WorkerExecutionResult.unknown(
                binding_id=request.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=admission.admitted_at,
                reason=(
                    "the result does not describe this invocation ("
                    + ", ".join(problems)
                    + "); it cannot be recorded as its outcome"
                ),
                detail={"result_integrity": "failed"},
            )
        return result

    # -- recording ---------------------------------------------------------

    def _record(
        self,
        context: Any,
        request: InvocationRequest,
        result: WorkerExecutionResult,
    ) -> bool:
        if self._recorder is None:
            return False
        try:
            self._recorder.record(context, request, result)
            return True
        except Exception:  # noqa: BLE001
            # Recording is Execution's; a failure here must not be reported as a
            # successful invocation, but it also cannot un-happen the work.
            log.error("recording an invocation result failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Events, outbox, audit
    # ------------------------------------------------------------------

    def _base_fields(self, admission: InvocationAdmission) -> dict:
        request = admission.request
        return {
            "execution_id": str(request.execution_id),
            "attempt_id": str(request.attempt_id),
            "node_id": request.node_id,
            "tenant_id": request.tenant_id,
            "principal_id": request.principal_id,
            "capability_ref": request.capability_ref,
            "capability_digest": request.capability_digest,
            "binding_id": request.binding_id,
            "binding_digest": request.binding_digest,
            "operation": request.operation,
            "environment": request.environment.value,
            "correlation_id_ref": request.correlation_id or "",
        }

    @staticmethod
    def _metadata(context: Any, request: InvocationRequest) -> EventMetadata:
        return EventMetadata.create(
            aggregate_id=str(request.execution_id),
            aggregate_type=INVOCATION_AGGREGATE_TYPE,
            scope=context.scope,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
            actor=getattr(getattr(context, "identity", None), "principal", None),
        )

    def _admitted_event(
        self, context: Any, admission: InvocationAdmission
    ) -> InvocationAdmitted:
        selection = admission.selection
        authority = admission.authority
        return InvocationAdmitted(
            metadata=self._metadata(context, admission.request),
            **self._base_fields(admission),
            worker_id=selection.worker_id,
            worker_digest=selection.worker_digest,
            worker_selection_id=selection.selection_id,
            action_digest=admission.action_digest,
            policy_version=authority.policy_version,
            authorization_digest=authority.decision_digest,
            approval_artifact_id=authority.approval_artifact_id or "",
            risk=authority.risk.value,
            effect_semantics=admission.binding.effect_semantics.value,
            side_effect_class=admission.binding.side_effect_class.value,
            effective_expiry=admission.window.effective_expiry.isoformat(),
            expiry_limited_by=admission.window.binding_expiry_source,
            deadline_seconds=admission.deadline_seconds,
        )

    def _started_event(
        self, context: Any, admission: InvocationAdmission
    ) -> InvocationStarted:
        return InvocationStarted(
            metadata=self._metadata(context, admission.request),
            **self._base_fields(admission),
            worker_id=admission.selection.worker_id,
            worker_digest=admission.selection.worker_digest,
            action_digest=admission.action_digest,
            deadline_seconds=admission.deadline_seconds,
            credential_required=self._credentials is not None,
        )

    def _outcome_events(
        self,
        context: Any,
        admission: InvocationAdmission,
        result: WorkerExecutionResult,
    ) -> tuple:
        base = {
            **self._base_fields(admission),
            "worker_id": admission.selection.worker_id,
            "worker_digest": admission.selection.worker_digest,
            "action_digest": admission.action_digest,
        }
        if result.outcome_is_known:
            return (
                InvocationCompleted(
                    metadata=self._metadata(context, admission.request),
                    **base,
                    outcome=result.outcome.value,
                    result_digest=result.result_digest or "",
                    observed_effect=(
                        result.observed_effect.value if result.observed_effect else ""
                    ),
                    duration_seconds=result.duration_seconds,
                    failure_class=(
                        result.failure_class.value if result.failure_class else ""
                    ),
                ),
            )
        return (
            InvocationAmbiguous(
                metadata=self._metadata(context, admission.request),
                **base,
                outcome=result.outcome.value,
                failure_class=(
                    result.failure_class.value
                    if result.failure_class
                    else FailureClass.UNKNOWN_OUTCOME.value
                ),
                reason=(result.failure.reason if result.failure else "")[:500],
                mutating=admission.binding.mutates,
                idempotent=admission.binding.is_repeatable,
                duration_seconds=result.duration_seconds,
            ),
        )

    def _emit_refusal(
        self, context: Any, request: InvocationRequest, refused: InvocationRefused
    ) -> None:
        """A denial is a fact. Recorded with the same attribution as a success."""
        event = InvocationRefusedEvent(
            metadata=self._metadata(context, request),
            execution_id=str(request.execution_id),
            attempt_id=str(request.attempt_id),
            node_id=request.node_id,
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            capability_ref=request.capability_ref,
            capability_digest=request.capability_digest,
            binding_id=request.binding_id,
            binding_digest=request.binding_digest,
            operation=request.operation,
            environment=request.environment.value,
            correlation_id_ref=request.correlation_id or "",
            refusal=refused.refusal.value,
            reason=refused.safe_message,
            retryable=refused.retryable,
            security_relevant=refused.refusal.is_security_relevant,
            worker_id=request.worker_id,
            worker_digest=request.worker_digest,
            stage=str(refused.detail.get("stage", "")),
        )
        self._publish(context, request, [event])
        self._audit_refusal(context, request, refused)

    def _publish(
        self, context: Any, request: InvocationRequest, events: list
    ) -> None:
        """Through the existing Execution outbox. No second outbox is created.

        Ordering is preserved by recording each stage as it happens rather than
        batching at the end -- a batch written after the fact would show a
        completion whose admission had not yet been durable.

        The in-memory outbox provides no cross-process durability and none is
        claimed here; what it provides is ordering and a single publication path.
        """
        if self._outbox is None or not events:
            return
        try:
            self._outbox.record(context, str(request.execution_id), events)
        except Exception:  # noqa: BLE001
            # Publication is not authorization. A failure to record an event must
            # never turn a refusal into an allow, so this is logged and the
            # decision stands.
            log.error("recording invocation events failed", exc_info=True)

    def _audit_invocation(
        self,
        context: Any,
        admission: InvocationAdmission,
        result: WorkerExecutionResult,
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        kind = (
            AuditEventKind.EXECUTION_SUCCEEDED
            if result.succeeded
            else AuditEventKind.EXECUTION_FAILED
        )
        self._safe_audit(
            kind,
            context,
            subject_reference=admission.request.capability_ref,
            detail={
                **admission.audit_detail(),
                "invocation_outcome": result.outcome.value,
                "outcome_known": result.outcome_is_known,
                "failure_class": (
                    result.failure_class.value if result.failure_class else None
                ),
                "result_digest": result.result_digest,
            },
        )

    def _audit_refusal(
        self, context: Any, request: InvocationRequest, refused: InvocationRefused
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        self._safe_audit(
            AuditEventKind.EXECUTION_REFUSED,
            context,
            subject_reference=request.capability_ref,
            detail={**request.to_dict(), **refused.to_dict()},
        )

    def _safe_audit(self, kind: Any, context: Any, **fields: Any) -> None:
        """Audit failure can never turn a denial into an allow.

        The decision has already been made by the time anything is written here.
        A raise would propagate out of a refusal path and could be caught as
        something other than a refusal, so it is contained.
        """
        try:
            self._audit.record_in_context(kind, context, **fields)
        except Exception:  # noqa: BLE001
            log.error("recording an invocation audit fact failed", exc_info=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _worker_request(
        self,
        request: InvocationRequest,
        binding: BoundCapability,
        *,
        payload: Mapping[str, Any],
        deadline: Optional[int],
    ) -> WorkerExecutionRequest:
        """Build the Phase 3.3.1 request. The kind is resolved, never guessed."""
        return WorkerExecutionRequest(
            execution_id=request.execution_id,
            attempt_id=request.attempt_id,
            attempt_number=request.attempt_number,
            node_id=request.node_id,
            worker_kind=self._workers.kind_for(binding),
            tenant_id=request.tenant_id,
            principal=request.principal,
            binding=binding,
            payload=payload,
            deadline_seconds=deadline,
            # Execution's key, passed through. Minting a second one here would
            # give the provider two identities for one logical operation.
            idempotency_key=request.idempotency_key,
            execution_key=request.execution_key,
            correlation_id=request.correlation_id,
            causation_id=request.causation_id,
        )

    def _refuse(
        self,
        request: InvocationRequest,
        refusal: InvocationRefusal,
        message: str,
        *,
        stage: str,
        reasons: tuple = (),
    ) -> InvocationRefused:
        """Build the refusal. Constructing one never invokes or mutates anything."""
        return InvocationRefused(
            refusal,
            message,
            correlation_id=request.correlation_id,
            detail={"stage": stage},
            reasons=tuple(str(r) for r in reasons),
        )


#: Phase 3.3.2 refusal codes projected onto this phase's vocabulary. Unmapped
#: codes become WORKER_UNAVAILABLE -- never an allow, and never a code invented
#: to look more specific than what was actually known.
_WORKER_REFUSALS = {
    "binding_refused": InvocationRefusal.BINDING_INVALID,
    "binding_unverifiable": InvocationRefusal.BINDING_UNVERIFIABLE,
    "binding_invalid": InvocationRefusal.BINDING_INVALID,
    "worker_kind_unresolved": InvocationRefusal.WORKER_UNAVAILABLE,
    "worker_kind_mismatch": InvocationRefusal.WORKER_SELECTION_MISMATCH,
    "worker_unavailable": InvocationRefusal.WORKER_UNAVAILABLE,
    "worker_ambiguous": InvocationRefusal.WORKER_AMBIGUOUS,
    "worker_selection_mismatch": InvocationRefusal.WORKER_SELECTION_MISMATCH,
    "worker_selection_invalid": InvocationRefusal.WORKER_DIGEST_MISMATCH,
    "worker_adapter_unavailable": InvocationRefusal.WORKER_UNAVAILABLE,
    "input_unvalidatable": InvocationRefusal.INPUT_VALIDATION_UNAVAILABLE,
    "input_invalid": InvocationRefusal.INPUT_INVALID,
}
