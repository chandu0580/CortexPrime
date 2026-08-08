"""Capability authorization: the question, the evidence, and the answer.

Three types, and the distinction between them is the design
-------------------------------------------------------------
``AuthorizationRequest``  — what is being asked. Supplied by a caller.
``AuthorizationSnapshot`` — the evidence, assembled by the service from
                            authoritative reads. **This is what policy sees.**
``AuthorizationDecision`` — the answer, immutable and bound.

Policy is handed a snapshot rather than a repository. An evaluator that could
look things up would have authorization inputs nobody can enumerate: the same
request could decide differently depending on what the evaluator chose to fetch,
and a review could not reconstruct why. Everything a decision rests on is in the
snapshot, which is why the snapshot is what gets digested.

Authorization is not ownership
--------------------------------
Owning a capability and being permitted to use it are different facts. There is
no rule here of the form ``owner == principal → allow``, and there is deliberately
no field that would make one easy to write. Ownership travels in the snapshot as
one input among several; policy may weigh it and may not substitute for it.

The same applies to provenance. ``source == INTERNAL`` is a claim about where a
definition came from, not a grant.

Default deny is structural
----------------------------
``AuthorizationDecision`` has no default effect. Every construction states one,
and every path that fails to reach a policy evaluation constructs a denial with
a reason. There is no code path that returns "allowed" by omission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.approval import PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.identity import PrincipalRef
from backend.contracts.policy import Obligation, PolicyEffect, RiskLevel
from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
from backend.contexts.connectivity.domain.identifiers import CapabilityRef
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState
from backend.platform.hashing import compute_digest

__all__ = [
    "CapabilityOperation",
    "DenialReason",
    "AuthorizationRequest",
    "AuthorizationSnapshot",
    "AuthorizationDecision",
    "BreakGlass",
    "DEFAULT_DECISION_TTL_SECONDS",
]

#: How long a decision stays actionable. Short on purpose: a decision is a
#: statement about security state at one instant, and that state changes.
#: Renewal is a new evaluation, never an extension of an old one.
DEFAULT_DECISION_TTL_SECONDS = 300


class CapabilityOperation(str, Enum):
    """What is being asked for. The operation is part of the decision.

    Authorizing a capability rather than an operation is how permission to read
    becomes permission to delete. Lifecycle operations are listed individually
    for the same reason: they are separate privileges, and a principal allowed
    to register something must not thereby be allowed to trust it.
    """

    # -- use --------------------------------------------------------
    INVOKE = "invoke"
    """Ordinary execution use. The common case, and the strictest."""

    INSPECT = "inspect"
    """Read the capability's definition. Still authorized -- being able to
    enumerate what a tenant can do is itself information."""

    # -- lifecycle (separation of duties) ---------------------------
    REGISTER = "register"
    VALIDATE = "validate"
    ENABLE = "enable"
    DISABLE = "disable"
    DEPRECATE = "deprecate"
    REVOKE = "revoke"
    TRUST = "trust"
    QUARANTINE = "quarantine"

    @property
    def is_lifecycle(self) -> bool:
        return self not in {CapabilityOperation.INVOKE, CapabilityOperation.INSPECT}

    @property
    def is_execution(self) -> bool:
        return self is CapabilityOperation.INVOKE

    @property
    def grants_availability(self) -> bool:
        """Whether performing this makes a capability usable by others.

        These are the operations that turn a record into an ability. They are
        the ones separation of duties exists for: whoever proposes a capability
        must not be the one who makes it live.
        """
        return self in {CapabilityOperation.ENABLE, CapabilityOperation.TRUST}

    @property
    def reduces_exposure(self) -> bool:
        """Whether performing this makes the platform *safer*.

        These must never be gated behind an approval that risk escalation would
        otherwise demand. A destructive capability is exactly the one somebody
        needs to revoke at three in the morning, and a policy that made shutting
        it down harder than using it would have the escalation backwards.
        """
        return self in {
            CapabilityOperation.DISABLE,
            CapabilityOperation.REVOKE,
            CapabilityOperation.QUARANTINE,
            CapabilityOperation.DEPRECATE,
        }

    @property
    def required_grant(self) -> str:
        """The coarse grant name policy looks for on the principal."""
        return f"capability:{self.value}"


class DenialReason(str, Enum):
    """Machine-readable reasons. Every non-allow decision carries at least one.

    Deliberately coarse at the tenant boundary: a caller from another tenant is
    told ``CAPABILITY_NOT_FOUND`` rather than ``TENANT_MISMATCH``, because the
    second confirms the capability exists.
    """

    CAPABILITY_NOT_FOUND = "capability_not_found"
    CAPABILITY_NOT_ENABLED = "capability_not_enabled"
    CAPABILITY_NOT_TRUSTED = "capability_not_trusted"
    CAPABILITY_QUARANTINED = "capability_quarantined"
    CAPABILITY_REVOKED = "capability_revoked"
    DIGEST_MISMATCH = "digest_mismatch"
    DIGEST_MISSING = "digest_missing"
    VERSION_NOT_PINNED = "version_not_pinned"
    TENANT_MISMATCH = "tenant_mismatch"
    PRINCIPAL_NOT_AUTHORIZED = "principal_not_authorized"
    OPERATION_NOT_ALLOWED = "operation_not_allowed"
    ENVIRONMENT_NOT_PERMITTED = "environment_not_permitted"
    EFFECT_UNDECLARED = "effect_undeclared"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_INVALID = "approval_invalid"
    APPROVAL_EXPIRED = "approval_expired"
    POLICY_DENIED = "policy_denied"
    POLICY_UNAVAILABLE = "policy_unavailable"
    ADMISSION_EXPIRED = "admission_expired"
    ADMISSION_STATE_CHANGED = "admission_state_changed"
    BINDING_MISMATCH = "binding_mismatch"
    SEPARATION_OF_DUTIES = "separation_of_duties"

    @property
    def is_disclosure_safe(self) -> bool:
        """Whether this reason may be returned across a tenant boundary.

        Most are not. Telling an unauthorized caller that a capability is
        quarantined tells them it exists, who runs it, and that something is
        wrong with it.
        """
        return self in {
            DenialReason.CAPABILITY_NOT_FOUND,
            DenialReason.PRINCIPAL_NOT_AUTHORIZED,
            DenialReason.POLICY_DENIED,
        }


@dataclass(frozen=True)
class BreakGlass:
    """An explicitly governed exceptional authorization.

    Never a bypass. It does not skip evaluation, it does not skip audit, and it
    does not skip binding -- it is an input that policy may weigh, and it is
    bounded in time and required to say who and why. A break-glass with no
    reason, no principal, or no expiry is refused at construction, because an
    emergency lever nobody has to sign for is just a back door.
    """

    invoked_by: PrincipalRef
    reason: str
    expires_at: datetime
    ticket_reference: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.invoked_by, PrincipalRef):
            raise ContractViolation("break-glass must name who invoked it")
        if not self.reason.strip():
            raise ContractViolation(
                "break-glass must say why; an unexplained emergency override is "
                "indistinguishable from an attack that succeeded"
            )
        if self.expires_at.tzinfo is None:
            raise ContractViolation("expires_at must be timezone-aware")

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def to_dict(self) -> dict:
        return {
            "invoked_by": self.invoked_by.principal_id,
            "reason": self.reason,
            "expires_at": self.expires_at.isoformat(),
            "ticket_reference": self.ticket_reference,
        }


@dataclass(frozen=True)
class AuthorizationRequest:
    """What a caller is asking for.

    ``expected_digest`` is mandatory for execution. A request that names only a
    capability and a version is asking about whatever that version currently
    says, and the whole point of the digest is that a caller states which
    contract it believes it is authorizing.
    """

    tenant_id: str
    principal: PrincipalRef
    capability_ref: CapabilityRef
    operation: CapabilityOperation
    expected_digest: Optional[str] = None
    environment: Optional[CapabilityEnvironment] = None

    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: Optional[str] = None

    approval_artifact_id: Optional[str] = None
    approval_digest: Optional[str] = None
    justification: Optional[str] = None
    break_glass: Optional[BreakGlass] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ContractViolation(
                "tenant_id is required; an authorization request that cannot say "
                "which tenant it is for cannot be isolated"
            )
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if not isinstance(self.capability_ref, CapabilityRef):
            raise ContractViolation(
                "capability_ref must be a pinned CapabilityRef; 'latest' is not an "
                "authorization target, because a decision about a moving version "
                "is a decision about whatever it becomes"
            )
        if not isinstance(self.operation, CapabilityOperation):
            raise ContractViolation("operation must be a CapabilityOperation")

    @property
    def binding_key(self) -> str:
        """What a decision is replayable against, and nothing more."""
        parts = [
            self.tenant_id,
            self.principal.principal_id,
            self.capability_ref.value,
            self.operation.value,
            self.execution_id or "-",
            self.node_id or "-",
            self.workflow_id or "-",
            self.mission_id or "-",
        ]
        return "|".join(parts)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "principal": self.principal.principal_id,
            "principal_kind": self.principal.kind.value,
            "capability_ref": self.capability_ref.value,
            "operation": self.operation.value,
            "expected_digest": self.expected_digest,
            "environment": self.environment.value if self.environment else None,
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "approval_artifact_id": self.approval_artifact_id,
            "break_glass": self.break_glass.to_dict() if self.break_glass else None,
            "requested_at": self.requested_at.isoformat(),
        }


@dataclass(frozen=True)
class AuthorizationSnapshot:
    """Everything a decision rests on, frozen at one instant.

    Assembled by the service from authoritative reads and handed to policy.
    Policy gets this and nothing else -- no repository, no service, no way to
    fetch. That is what makes a decision reproducible: given the same snapshot,
    any evaluator reaches the same answer, and a review can reconstruct exactly
    what was known.
    """

    request: AuthorizationRequest
    principal_grants: tuple = ()
    """Coarse grants resolved at authentication (``IdentityContext.capabilities``).
    An *input* to policy, never a substitute for it -- Constitution I1 requires a
    recorded decision regardless of what a principal holds."""

    capability_found: bool = False
    capability_status: Optional[CapabilityStatus] = None
    capability_trust: Optional[TrustState] = None
    capability_digest: Optional[str] = None
    capability_owner: Optional[str] = None
    capability_tenancy: Optional[str] = None
    capability_source: Optional[str] = None
    capability_is_self_declared: bool = False
    side_effect_class: Optional[SideEffectClass] = None
    effect_semantics: Optional[EffectSemantics] = None
    supported_environments: tuple = ()
    required_permissions: tuple = ()

    approval_present: bool = False
    approval_valid: bool = False
    approval_bound_digest: Optional[str] = None

    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def principal_is_owner(self) -> bool:
        """Available to policy as an input. Never an authorization on its own."""
        return bool(
            self.capability_owner
            and self.capability_owner == self.request.principal.principal_id
        )

    @property
    def implied_risk(self) -> RiskLevel:
        """Risk implied by the declared effect, never lowered by omission.

        An undeclared effect is CRITICAL, not LOW. The reason is the same one
        that runs through the whole capability model: the field most often
        missing is the one that says how much damage the thing can do.
        """
        if self.effect_semantics is None or self.side_effect_class is None:
            return RiskLevel.CRITICAL
        if self.effect_semantics is EffectSemantics.UNKNOWN:
            return RiskLevel.CRITICAL
        if self.side_effect_class is SideEffectClass.DESTRUCTIVE:
            return RiskLevel.CRITICAL
        if self.side_effect_class is SideEffectClass.IRREVERSIBLE_WRITE:
            return RiskLevel.HIGH
        if self.side_effect_class is SideEffectClass.REVERSIBLE_WRITE:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def to_dict(self) -> dict:
        return {
            "request": self.request.to_dict(),
            "principal_grants": sorted(self.principal_grants),
            "capability_found": self.capability_found,
            "capability_status": (
                self.capability_status.value if self.capability_status else None
            ),
            "capability_trust": (
                self.capability_trust.value if self.capability_trust else None
            ),
            "capability_digest": self.capability_digest,
            "capability_owner": self.capability_owner,
            "capability_tenancy": self.capability_tenancy,
            "capability_source": self.capability_source,
            "capability_is_self_declared": self.capability_is_self_declared,
            "side_effect_class": (
                self.side_effect_class.value if self.side_effect_class else None
            ),
            "effect_semantics": (
                self.effect_semantics.value if self.effect_semantics else None
            ),
            "supported_environments": sorted(
                e.value for e in self.supported_environments
            ),
            "required_permissions": sorted(self.required_permissions),
            "approval_present": self.approval_present,
            "approval_valid": self.approval_valid,
            "implied_risk": self.implied_risk.value,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True)
class AuthorizationDecision:
    """The answer. Immutable, bound, digested, and time-limited."""

    effect: PolicyEffect
    request: AuthorizationRequest
    policy_version: str
    decided_at: datetime
    expires_at: datetime
    binding_key: str
    capability_digest: Optional[str] = None
    reasons: tuple = ()
    obligations: tuple = ()
    risk: RiskLevel = RiskLevel.CRITICAL
    approval_artifact_id: Optional[str] = None
    break_glass_used: bool = False
    digest: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.effect, PolicyEffect):
            raise ContractViolation("effect must be a PolicyEffect")
        if not self.policy_version.strip():
            raise ContractViolation(
                "a decision must record which policy version produced it; without "
                "it nobody can answer 'what authorized this' after policy changes"
            )
        if self.expires_at <= self.decided_at:
            raise ContractViolation(
                "a decision must expire after it is made; one that never expires "
                "is a standing grant, and execution grants do not stand"
            )
        if self.effect is not PolicyEffect.ALLOW and not self.reasons:
            raise ContractViolation(
                "every non-allow decision must carry a machine-readable reason; a "
                "denial nobody can explain cannot be appealed or audited"
            )
        if self.effect is PolicyEffect.ALLOW and not self.capability_digest:
            raise ContractViolation(
                "an allow decision must name the exact contract it authorized; "
                "without the digest it authorizes whatever the capability later "
                "becomes"
            )

    # -- queries -------------------------------------------------------

    @property
    def allowed(self) -> bool:
        return self.effect is PolicyEffect.ALLOW

    @property
    def requires_approval(self) -> bool:
        return self.effect is PolicyEffect.REQUIRE_APPROVAL

    @property
    def reason_codes(self) -> tuple:
        return tuple(r.value for r in self.reasons)

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def authorizes(self, request: AuthorizationRequest) -> bool:
        """Whether this decision covers that request.

        The replay bound. A decision is usable only for the exact binding it was
        made for -- same tenant, principal, capability version, operation, and
        the same execution/workflow/mission it named. A decision for workflow A
        is not a token for workflow B.
        """
        return self.binding_key == request.binding_key

    def digest_payload(self) -> dict:
        """The security-relevant decision. No rendering, no volatile fields."""
        return {
            "effect": self.effect.value,
            "tenant_id": self.request.tenant_id,
            "principal_id": self.request.principal.principal_id,
            "capability_ref": self.request.capability_ref.value,
            "capability_digest": self.capability_digest,
            "operation": self.request.operation.value,
            "binding_key": self.binding_key,
            "policy_version": self.policy_version,
            "reasons": sorted(r.value for r in self.reasons),
            "risk": self.risk.value,
            "approval_artifact_id": self.approval_artifact_id,
            "break_glass_used": self.break_glass_used,
            "decided_at": self.decided_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def sealed(self) -> "AuthorizationDecision":
        from dataclasses import replace

        return replace(self, digest=compute_digest(self.digest_payload()).value)

    def payload_digest(self) -> PayloadDigest:
        """Reuses the published approval/hash vocabulary. No new algorithm."""
        return compute_digest(self.digest_payload())

    def to_dict(self) -> dict:
        return {
            **self.digest_payload(),
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "obligations": [
                {"kind": o.kind.value, "detail": o.detail} for o in self.obligations
            ],
            "digest": self.digest,
        }

    # -- construction --------------------------------------------------

    @classmethod
    def deny(
        cls,
        request: AuthorizationRequest,
        *reasons: DenialReason,
        policy_version: str = "builtin/0",
        risk: RiskLevel = RiskLevel.CRITICAL,
        now: Optional[datetime] = None,
    ) -> "AuthorizationDecision":
        """The default answer. Constructed on every path that is not an allow."""
        moment = now or datetime.now(timezone.utc)
        return cls(
            effect=PolicyEffect.DENY,
            request=request,
            policy_version=policy_version,
            decided_at=moment,
            expires_at=moment + timedelta(seconds=DEFAULT_DECISION_TTL_SECONDS),
            binding_key=request.binding_key,
            reasons=tuple(reasons) or (DenialReason.POLICY_DENIED,),
            risk=risk,
        ).sealed()

    @classmethod
    def allow(
        cls,
        request: AuthorizationRequest,
        *,
        capability_digest: str,
        policy_version: str,
        risk: RiskLevel,
        obligations: tuple = (),
        approval_artifact_id: Optional[str] = None,
        break_glass_used: bool = False,
        ttl_seconds: int = DEFAULT_DECISION_TTL_SECONDS,
        now: Optional[datetime] = None,
    ) -> "AuthorizationDecision":
        moment = now or datetime.now(timezone.utc)
        return cls(
            effect=PolicyEffect.ALLOW,
            request=request,
            policy_version=policy_version,
            decided_at=moment,
            expires_at=moment + timedelta(seconds=ttl_seconds),
            binding_key=request.binding_key,
            capability_digest=capability_digest,
            obligations=tuple(obligations),
            risk=risk,
            approval_artifact_id=approval_artifact_id,
            break_glass_used=break_glass_used,
        ).sealed()

    @classmethod
    def require_approval(
        cls,
        request: AuthorizationRequest,
        *reasons: DenialReason,
        policy_version: str,
        risk: RiskLevel,
        obligations: tuple = (),
        now: Optional[datetime] = None,
    ) -> "AuthorizationDecision":
        moment = now or datetime.now(timezone.utc)
        return cls(
            effect=PolicyEffect.REQUIRE_APPROVAL,
            request=request,
            policy_version=policy_version,
            decided_at=moment,
            expires_at=moment + timedelta(seconds=DEFAULT_DECISION_TTL_SECONDS),
            binding_key=request.binding_key,
            reasons=tuple(reasons) or (DenialReason.APPROVAL_REQUIRED,),
            obligations=tuple(obligations),
            risk=risk,
        ).sealed()
