"""Capability authorization and admission.

Two operations, and the gap between them is the point
-------------------------------------------------------
``authorize()`` answers *is this principal permitted?* — evaluated against the
registry as it stands, and producing a bound, expiring, digested decision.

``admit()`` answers *may this proceed right now?* — re-reading the authoritative
record at the moment the decision becomes actionable.

They are separate because time passes between them. A capability can be revoked,
quarantined, or republished in that gap, and a decision made thirty seconds ago
is evidence about thirty seconds ago. Admission re-reads rather than trusting the
decision's own account of the world, which is what closes the TOCTOU window:

    authorize  → ALLOW
    (capability revoked)
    admit      → DENY  ADMISSION_STATE_CHANGED

Order of checks
-----------------
Existence, tenancy, digest, lifecycle and trust are evaluated **before** policy.
Not for speed — because these are facts, and policy is judgement. A policy that
could allow a revoked capability would be a policy that could be written wrongly;
one that never sees revoked capabilities cannot be.

The tenant check is deliberately first among the visible ones, and it answers
``CAPABILITY_NOT_FOUND``. Telling a caller from another tenant that a capability
exists but is not theirs confirms it exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from backend.contracts.approval import ApprovalOutcome
from backend.contracts.audit import AuditEventKind
from backend.contracts.errors import ContractViolation
from backend.contracts.policy import PolicyEffect, RiskLevel
from backend.contexts.connectivity.application.commands import GetCapability
from backend.contexts.connectivity.application.policy import (
    CapabilityPolicy,
    GuardedPolicy,
    default_policy,
)
from backend.contexts.connectivity.domain.authorization import (
    AuthorizationDecision,
    AuthorizationRequest,
    AuthorizationSnapshot,
    CapabilityOperation,
    DenialReason,
)
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotFound,
    CapabilityVersionNotFound,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState

__all__ = [
    "ApprovalLookup",
    "NoApprovals",
    "CapabilityAuthorizationService",
    "PolicyBackedRegistrationGuard",
]

#: Lifecycle status required for ordinary execution use. There is deliberately
#: no ``allow_disabled`` anywhere: an administrative bypass on the ordinary
#: execution path is how the bypass becomes the path.
_EXECUTABLE_STATUSES = frozenset({CapabilityStatus.ENABLED, CapabilityStatus.DEPRECATED})

#: Lifecycle operations may act on capabilities that are not enabled — that is
#: what they are for. They still go through policy.
_LIFECYCLE_FORBIDDEN_STATUSES = frozenset({CapabilityStatus.REVOKED})


@runtime_checkable
class ApprovalLookup(Protocol):
    """Reads the existing approval system. Does not implement one.

    Returns the approval's outcome and the digest it was bound to, so
    authorization can check that the approval is *about this contract*. No new
    approval store, no new signing, no second integrity mechanism.
    """

    def find(
        self, context: Any, artifact_id: str
    ) -> Optional["ApprovalFacts"]: ...


@dataclass(frozen=True)
class ApprovalFacts:
    """What authorization needs to know about an approval."""

    artifact_id: str
    outcome: ApprovalOutcome
    bound_digest: Optional[str]
    """The CAPABILITY contract digest this approval was granted against. An
    approval for version 1 must not authorize version 2."""

    scope_tenant_id: Optional[str]
    bound_action_digest: Optional[str] = None
    """The ADR-038 ACTION digest this approval was granted for (ADR-090).

    Distinct from ``bound_digest`` and deliberately so. The capability digest
    says *which capability at which version*; the action digest additionally
    covers the validated input, the tenant, the principal and the environment --
    which is what stops an approval for restarting workload A being replayed to
    restart workload B.

    The gateway has always demanded this (``_check_approval`` refuses when it is
    ``None``: "an unbound approval would authorize anything this capability can
    do"). Until ADR-090 nothing could supply it, so that demand refused every
    approval-requiring dispatch. Optional here because an approval granted
    without one is simply not dispatchable -- which is the pre-existing
    behaviour, not a new refusal.
    """

    operation: Optional[str] = None
    expires_at: Optional[datetime] = None
    decided_by: Optional[str] = None
    """Who concluded the approval, as the namespaced reference the store holds.

    Phase 11.4 (ADR-124). A ``human:`` decider is a person holding scoped
    approver authority. Any other decider (``policy:autonomy/...``) is delegated
    authority recorded in the same approval authority, and authorization accepts
    it only for a capability whose contract declares a compensation -- L10's
    compensable class. ``None`` (an approval from a store that predates the
    field) is treated as a human decision, which is what every such approval was.
    """

    consumed_by_execution: Optional[str] = None
    """The execution that used this approval, once it has been used.

    Phase 11.4 run 10: the store recorded consumption (``mark_consumed``) but
    nothing enforced it, so a single-use approval stayed valid for every replay
    until it expired -- harmless only because layers above (the action-key
    claim) and below (the worker's re-read) happened to catch each replay seen.
    Both writers mark an approval consumed only AFTER its governed write
    returns, so every re-check of the execution it authorized precedes this.
    """

    @property
    def is_delegated(self) -> bool:
        return bool(self.decided_by) and not str(self.decided_by).startswith("human:")

    def is_valid_for(
        self,
        *,
        tenant_id: str,
        capability_digest: Optional[str],
        operation: str,
        moment: datetime,
    ) -> bool:
        """Whether this approval actually covers this request.

        Every clause matters. An approval for version 1 must not authorize
        version 2 (digest); an approval to READ must not authorize DELETE
        (operation); an approval for tenant A must not authorize tenant B
        (scope); an expired approval authorizes nothing; and an approval that
        has already been used authorizes nothing again (single use).
        """
        if self.outcome is not ApprovalOutcome.GRANTED:
            return False
        if self.consumed_by_execution:
            return False
        if self.expires_at is not None and moment >= self.expires_at:
            return False
        if self.scope_tenant_id and self.scope_tenant_id != tenant_id:
            return False
        if self.operation and self.operation != operation:
            return False
        if not self.bound_digest or self.bound_digest != capability_digest:
            return False
        return True


class NoApprovals:
    """No approval system wired in. Every approval lookup fails closed."""

    def find(self, context: Any, artifact_id: str) -> Optional[ApprovalFacts]:
        return None


class CapabilityAuthorizationService:
    """Decides whether a capability may be used, and re-checks at admission."""

    def __init__(
        self,
        *,
        registry: Any,
        policy: Optional[CapabilityPolicy] = None,
        approvals: Optional[ApprovalLookup] = None,
        audit: Optional[Any] = None,
    ) -> None:
        self._registry = registry
        # Wrapped unconditionally: an evaluator supplied by a caller is still
        # something that can raise, and the guard is not optional.
        self._policy = GuardedPolicy(policy) if policy is not None else default_policy()
        self._approvals = approvals or NoApprovals()
        self._audit = audit

    @property
    def has_approval_authority(self) -> bool:
        """Whether approvals presented to this service can ever be found.

        ``False`` means every approval lookup fails closed (``NoApprovals``):
        correct for a process that performs no approval-requiring work, and a
        composition error for one that does. Phase 11.4 (F-4) found the API
        process in the second state; the remediation runtime now refuses to
        start rather than plan actions this service could never authorize.
        """
        return not isinstance(self._approvals, NoApprovals)

    @property
    def policy_version(self) -> str:
        return self._policy.policy_version

    # ------------------------------------------------------------------
    # Authorization
    # ------------------------------------------------------------------

    def authorize(
        self, context: Any, request: AuthorizationRequest, *, now: Optional[datetime] = None
    ) -> AuthorizationDecision:
        """Decide. Every path that is not an explicit allow is a denial."""
        moment = now or datetime.now(timezone.utc)

        # Tenant of the request must be the tenant of the caller's context.
        # A caller cannot ask about a tenant it is not acting for.
        context_tenant = getattr(context, "tenant_id", None)
        is_platform = bool(getattr(context, "is_platform_internal", False))
        if not is_platform and context_tenant != request.tenant_id:
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.TENANT_MISMATCH, now=moment
                ),
            )

        # The principal named in the request must be the authenticated principal.
        #
        # Grants are read from the caller's ``IdentityContext``; the principal is
        # read from the request. If those may disagree, a caller can name one
        # principal and be evaluated with another's grants -- authorization about
        # somebody else, decided with the caller's privileges. The two must be
        # the same identity, or explicitly linked by ``on_behalf_of``.
        identity = getattr(context, "identity", None)
        authenticated = getattr(identity, "principal", None)
        if not is_platform:
            if authenticated is None:
                return self._recorded(
                    context,
                    AuthorizationDecision.deny(
                        request, DenialReason.PRINCIPAL_NOT_AUTHORIZED, now=moment
                    ),
                )
            delegate = getattr(identity, "on_behalf_of", None)
            claimed = request.principal.principal_id
            permitted_ids = {authenticated.principal_id}
            if delegate is not None:
                permitted_ids.add(delegate.principal_id)
            if claimed not in permitted_ids:
                return self._recorded(
                    context,
                    AuthorizationDecision.deny(
                        request, DenialReason.PRINCIPAL_NOT_AUTHORIZED, now=moment
                    ),
                )

        definition = self._load(context, request)
        if definition is None:
            # Absent and invisible are the same answer, on purpose.
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.CAPABILITY_NOT_FOUND, now=moment
                ),
            )

        # Visibility. Same reason code as absence.
        if not definition.visible_to(request.tenant_id):
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.CAPABILITY_NOT_FOUND, now=moment
                ),
            )

        facts = self._facts_check(request, definition, moment)
        if facts:
            return self._recorded(
                context, AuthorizationDecision.deny(request, *facts, now=moment)
            )

        snapshot = self._snapshot(context, request, definition, moment)
        verdict = self._policy.evaluate(snapshot)

        if verdict.effect is PolicyEffect.DENY:
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request,
                    *(verdict.reasons or (DenialReason.POLICY_DENIED,)),
                    policy_version=verdict.policy_version,
                    risk=verdict.risk or snapshot.implied_risk,
                    now=moment,
                ),
            )

        if verdict.effect is PolicyEffect.REQUIRE_APPROVAL:
            # An approval already supplied and valid satisfies the requirement;
            # otherwise the caller is told what to go and get.
            if snapshot.approval_valid:
                return self._recorded(
                    context,
                    AuthorizationDecision.allow(
                        request,
                        capability_digest=definition.digest,
                        policy_version=verdict.policy_version,
                        risk=verdict.risk or snapshot.implied_risk,
                        obligations=verdict.obligations,
                        approval_artifact_id=request.approval_artifact_id,
                        # Carried so the gateway can do the check this service
                        # cannot: whether the approval covers this ACTION, not
                        # merely this capability (ADR-090).
                        approval_bound_digest=snapshot.approval_bound_digest,
                        break_glass_used=self._break_glass_live(request, moment),
                        now=moment,
                    ),
                )
            return self._recorded(
                context,
                AuthorizationDecision.require_approval(
                    request,
                    *(verdict.reasons or (DenialReason.APPROVAL_REQUIRED,)),
                    policy_version=verdict.policy_version,
                    risk=verdict.risk or snapshot.implied_risk,
                    obligations=verdict.obligations,
                    now=moment,
                ),
            )

        return self._recorded(
            context,
            AuthorizationDecision.allow(
                request,
                capability_digest=definition.digest,
                policy_version=verdict.policy_version,
                risk=verdict.risk or snapshot.implied_risk,
                obligations=verdict.obligations,
                approval_artifact_id=request.approval_artifact_id,
                # Carried on every allow path, not only the one that started as
                # REQUIRE_APPROVAL: if an approval was presented at all, the
                # gateway must be able to check it covers THIS action (ADR-090).
                approval_bound_digest=snapshot.approval_bound_digest,
                break_glass_used=self._break_glass_live(request, moment),
                now=moment,
            ),
        )

    # ------------------------------------------------------------------
    # Admission
    # ------------------------------------------------------------------

    def admit(
        self,
        context: Any,
        decision: AuthorizationDecision,
        request: AuthorizationRequest,
        *,
        now: Optional[datetime] = None,
    ) -> AuthorizationDecision:
        """Re-check at the moment the decision becomes actionable.

        Re-reads the authoritative record rather than trusting the decision's
        account of it. Returns the original decision when everything still
        holds, and a fresh denial when it does not — never a mutated one, because
        a decision is a record of what was concluded and rewriting it would
        destroy the audit trail.
        """
        moment = now or datetime.now(timezone.utc)

        if not decision.allowed:
            return decision

        # Replay bound. A decision is usable only for the binding it was made
        # for; presenting it for a different execution is an attempted replay.
        if not decision.authorizes(request):
            self._audit_fact(
                context,
                AuditEventKind.REPLAY_ATTEMPT_DETECTED,
                decision,
                extra={"presented_binding": request.binding_key},
            )
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.BINDING_MISMATCH, now=moment
                ),
            )

        if not decision.is_live_at(moment):
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.ADMISSION_EXPIRED, now=moment
                ),
            )

        definition = self._load(context, request)
        if definition is None or not definition.visible_to(request.tenant_id):
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request, DenialReason.ADMISSION_STATE_CHANGED, now=moment
                ),
            )

        # The contract must still be the one that was authorized.
        if definition.digest != decision.capability_digest:
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request,
                    DenialReason.DIGEST_MISMATCH,
                    DenialReason.ADMISSION_STATE_CHANGED,
                    now=moment,
                ),
            )

        reasons = self._facts_check(request, definition, moment)
        if reasons:
            return self._recorded(
                context,
                AuthorizationDecision.deny(
                    request,
                    *reasons,
                    DenialReason.ADMISSION_STATE_CHANGED,
                    now=moment,
                ),
            )

        return decision

    # ------------------------------------------------------------------
    # Facts, checked before judgement
    # ------------------------------------------------------------------

    def _facts_check(
        self, request: AuthorizationRequest, definition: Any, moment: datetime
    ) -> tuple:
        """Non-negotiable state checks. Returns reasons, empty when clean."""
        reasons: list = []

        # Digest pinning. Execution must state the contract it believes it is
        # authorizing; a request without one is asking about whatever the
        # version currently happens to say.
        if request.operation.is_execution:
            if not request.expected_digest:
                reasons.append(DenialReason.DIGEST_MISSING)
            elif request.expected_digest != definition.digest:
                reasons.append(DenialReason.DIGEST_MISMATCH)

        if definition.status is CapabilityStatus.REVOKED:
            reasons.append(DenialReason.CAPABILITY_REVOKED)
        elif request.operation.is_execution:
            if definition.status not in _EXECUTABLE_STATUSES:
                reasons.append(DenialReason.CAPABILITY_NOT_ENABLED)
            if definition.trust is TrustState.QUARANTINED:
                # ENABLED + QUARANTINED is a legal state and must still refuse.
                reasons.append(DenialReason.CAPABILITY_QUARANTINED)
            elif not definition.trust.permits_execution:
                reasons.append(DenialReason.CAPABILITY_NOT_TRUSTED)

            if request.environment is not None and not definition.permits_environment(
                request.environment
            ):
                # A development authorization never authorizes production.
                reasons.append(DenialReason.ENVIRONMENT_NOT_PERMITTED)

        return tuple(reasons)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self, context: Any, request: AuthorizationRequest):
        try:
            return self._registry.get(
                context,
                GetCapability(
                    capability_id=request.capability_ref.capability_id.value,
                    version=request.capability_ref.version.number,
                ),
            )
        except (CapabilityNotFound, CapabilityVersionNotFound):
            return None
        except Exception:  # noqa: BLE001 - a registry that cannot answer denies
            return None

    def _snapshot(
        self,
        context: Any,
        request: AuthorizationRequest,
        definition: Any,
        moment: datetime,
    ) -> AuthorizationSnapshot:
        approval_facts = None
        if request.approval_artifact_id:
            try:
                approval_facts = self._approvals.find(
                    context, request.approval_artifact_id
                )
            except Exception:  # noqa: BLE001 - unavailable approval is no approval
                approval_facts = None

        approval_valid = bool(
            approval_facts
            and approval_facts.is_valid_for(
                tenant_id=request.tenant_id,
                capability_digest=definition.digest,
                operation=request.operation.value,
                moment=moment,
            )
        )

        # Phase 11.4 (ADR-124). A DELEGATED approval -- one concluded by a policy
        # decider rather than a human -- is recorded in the same approval
        # authority and bound by the same digest, and it is valid ONLY for a
        # capability whose contract declares a compensation (L10's compensable
        # class) and that is not DESTRUCTIVE. For every other capability,
        # including the rollout restart, an approval nobody human decided
        # authorizes nothing; L10's fresh-human rule for irreversible actions is
        # enforced here, below every caller, rather than trusted to them.
        if approval_valid and getattr(approval_facts, "is_delegated", False):
            contract = definition.contract
            compensable = bool(getattr(contract, "compensation_capability", None))
            destructive = getattr(getattr(contract, "side_effect_class", None), "value", None) == "destructive"
            if not compensable or destructive:
                import logging as _logging

                _logging.getLogger(__name__).warning(
                    "a delegated approval (%s) was presented for %s, which is not compensable; "
                    "it authorizes nothing", approval_facts.decided_by, definition.reference)
                approval_valid = False

        identity = getattr(context, "identity", None)
        grants = tuple(getattr(identity, "capabilities", ()) or ())

        return AuthorizationSnapshot(
            request=request,
            principal_grants=grants,
            capability_found=True,
            capability_status=definition.status,
            capability_trust=definition.trust,
            capability_digest=definition.digest,
            capability_owner=definition.owner.principal_id,
            capability_tenancy=definition.tenancy.value,
            capability_source=definition.source.value,
            capability_is_self_declared=definition.source.is_self_declared,
            side_effect_class=definition.contract.side_effect_class,
            effect_semantics=definition.contract.effect_semantics,
            supported_environments=definition.contract.supported_environments,
            required_permissions=definition.contract.required_permissions,
            approval_present=approval_facts is not None,
            approval_valid=approval_valid,
            approval_bound_digest=(
                # The ACTION digest (ADR-090), which is what the gateway
                # compares against. Reading ``bound_digest`` here would hand the
                # gateway a capability digest and fail every comparison.
                approval_facts.bound_action_digest if approval_facts else None
            ),
            evaluated_at=moment,
        )

    @staticmethod
    def _break_glass_live(request: AuthorizationRequest, moment: datetime) -> bool:
        return bool(request.break_glass and request.break_glass.is_live_at(moment))

    # ------------------------------------------------------------------
    # Audit — denials are first-class facts
    # ------------------------------------------------------------------

    def _recorded(
        self, context: Any, decision: AuthorizationDecision
    ) -> AuthorizationDecision:
        """Every decision is auditable, including — especially — the denials.

        A security system that records only successful actions cannot explain
        why an attack was stopped.
        """
        kind = AuditEventKind.POLICY_EVALUATED
        if decision.break_glass_used:
            kind = AuditEventKind.BREAK_GLASS_INVOKED
        elif decision.effect is PolicyEffect.REQUIRE_APPROVAL:
            kind = AuditEventKind.APPROVAL_REQUESTED
        elif not decision.allowed:
            kind = AuditEventKind.EXECUTION_REFUSED
        self._audit_fact(context, kind, decision)
        return decision

    def _audit_fact(
        self,
        context: Any,
        kind: Any,
        decision: AuthorizationDecision,
        *,
        extra: Optional[dict] = None,
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(
                tenant=TenantRef(tenant_id=decision.request.tenant_id)
            )
        detail = {
            # No secrets, no credentials, no justification free-text beyond what
            # the caller supplied deliberately.
            "effect": decision.effect.value,
            "capability_ref": decision.request.capability_ref.value,
            "capability_digest": decision.capability_digest,
            "operation": decision.request.operation.value,
            "reasons": list(decision.reason_codes),
            "policy_version": decision.policy_version,
            "risk": decision.risk.value,
            "approval_artifact_id": decision.approval_artifact_id,
            "break_glass": decision.break_glass_used,
            "binding_key": decision.binding_key,
            "expires_at": decision.expires_at.isoformat(),
            **(extra or {}),
        }
        try:
            self._audit.record(
                kind,
                scope,
                subject_reference=decision.request.capability_ref.value,
                detail=detail,
                actor=decision.request.principal,
                payload_digest=decision.payload_digest(),
            )
        except Exception:  # noqa: BLE001 - audit failure must not allow anything
            # Deliberately swallowed *after* the decision is already made. This
            # cannot turn a denial into an allow; the decision object is
            # returned unchanged either way.
            import logging

            logging.getLogger(__name__).warning(
                "capability authorization audit failed", exc_info=True
            )


class PolicyBackedRegistrationGuard:
    """Replaces ``OpenRegistration``. Registration is now a governed operation.

    Implements the ``RegistrationGuard`` Protocol from ADR-032, so nothing in
    the registry changes — the seam left in 3.2.1 is simply filled.

    Each lifecycle operation is authorized as itself. A principal permitted to
    register is not thereby permitted to enable or to trust, which is the
    separation of duties the operation vocabulary exists to express.
    """

    def __init__(self, authorization: CapabilityAuthorizationService) -> None:
        self._authorization = authorization

    def assert_may_register(self, context: Any, definition: Any) -> None:
        self._assert(context, definition, CapabilityOperation.REGISTER)

    def assert_may_change(self, context: Any, definition: Any, operation: str) -> None:
        mapping = {
            "validate": CapabilityOperation.VALIDATE,
            "enable": CapabilityOperation.ENABLE,
            "disable": CapabilityOperation.DISABLE,
            "deprecate": CapabilityOperation.DEPRECATE,
            "revoke": CapabilityOperation.REVOKE,
            "set_trust": CapabilityOperation.TRUST,
        }
        # An unmapped operation is refused rather than waved through: a new
        # lifecycle operation added later must be classified before it is
        # permitted, not permitted because nobody classified it.
        target = mapping.get(operation)
        if target is None:
            raise ContractViolation(
                f"lifecycle operation {operation!r} has no authorization mapping; "
                "refusing rather than defaulting to permitted"
            )
        self._assert(context, definition, target)

    def _assert(self, context: Any, definition: Any, operation: CapabilityOperation) -> None:
        identity = getattr(context, "identity", None)
        principal = getattr(identity, "principal", None)
        if principal is None:
            raise ContractViolation(
                f"{operation.value} requires an authenticated principal; an "
                "unauthenticated lifecycle change is an unattributable one"
            )

        request = AuthorizationRequest(
            tenant_id=getattr(context, "tenant_id", "") or "",
            principal=principal,
            capability_ref=definition.reference,
            operation=operation,
        )
        decision = self._authorization.authorize(context, request)
        if not decision.allowed:
            raise ContractViolation(
                f"{operation.value} of {definition.reference.value} was refused: "
                f"{', '.join(decision.reason_codes)}"
            )
