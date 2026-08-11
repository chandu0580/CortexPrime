"""The credential request, the grant it produces, and why issuance can refuse.

Nothing is inferred
---------------------
Every fact the fabric needs is a required field. There is no ambient tenant, no
current principal, no default environment, and no way to build a request from
less than the whole authority chain. A subsystem that could fill in a blank would
eventually fill in the wrong one, and the blank most likely to be filled wrongly
is the tenant.

The request is bound to an action, not to a capability
--------------------------------------------------------
``action_digest`` is the one computed by ``SecureCapabilityInvocationGateway``
(ADR-038) — capability, operation, validated input, tenant, principal,
environment, binding, policy version, all under one hash. **No second action hash
is computed here.**

That is what makes the confused deputy structural: a credential issued for the
action "create an issue in repository A" carries the digest of *that* action. It
cannot be presented for "delete repository B", because the digest of that action
is a different number and the grant says which one it was for.

Issuance narrows; it never broadens
-------------------------------------
Everything about the grant is bounded by the request, and everything about the
request is bounded by the authority that produced it. Scope may be equal or
narrower — and a narrower one is *refused* rather than silently accepted, because
half a credential fails in the middle of an operation somebody approved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.credential import (
    CredentialRef,
    CredentialScope,
    CredentialState,
    CredentialType,
)
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.identity import PrincipalRef

__all__ = [
    "CredentialRefusal",
    "CredentialRefused",
    "CredentialRequest",
    "CredentialGrant",
    "MAX_CREDENTIAL_LIFETIME_SECONDS",
]

MAX_CREDENTIAL_LIFETIME_SECONDS = 900
"""Fifteen minutes, as a ceiling nobody can raise from a call site. A request may
ask for less and the authority window routinely allows less; nothing allows more.
A credential outliving the invocation it was minted for is a credential available
for the next thing somebody thinks of."""


class CredentialRefusal(str, Enum):
    """Why a credential was not issued. Every value is safe to show a caller.

    None of them names a provider host, a vault path, a secret, or an exception
    trace: a refusal that leaks infrastructure detail turns the credential
    boundary into a reconnaissance surface for exactly the attacker who is
    probing it.
    """

    # -- the request itself ---------------------------------------------
    REQUEST_INCOMPLETE = "credential_request_incomplete"
    TENANT_MISMATCH = "credential_tenant_mismatch"
    PRINCIPAL_MISMATCH = "credential_principal_mismatch"
    DELEGATION_NOT_AUTHORIZED = "credential_delegation_not_authorized"
    ENVIRONMENT_MISMATCH = "credential_environment_mismatch"
    ACTION_MISMATCH = "credential_action_mismatch"
    BINDING_MISMATCH = "credential_binding_mismatch"

    # -- authority ---------------------------------------------------------
    AUTHORIZATION_EXPIRED = "credential_authorization_expired"
    APPROVAL_REQUIRED = "credential_approval_required"
    APPROVAL_EXPIRED = "credential_approval_expired"
    AUTHORITY_WINDOW_CLOSED = "credential_authority_window_closed"
    """No time remains once every expiry is taken into account. Issuing here
    would mint something already dead, or worse, something that outlives the
    permission for it."""

    # -- scope ---------------------------------------------------------------
    SCOPE_NOT_REQUESTED = "credential_scope_not_requested"
    INSUFFICIENT_SCOPE = "credential_insufficient_scope"
    SCOPE_BROADENED = "credential_scope_broadened"
    """The provider returned more than was asked for. Refused: a credential
    stronger than the authority that requested it is a privilege escalation
    delivered by the thing that was supposed to prevent one."""

    RESOURCE_MISMATCH = "credential_resource_mismatch"

    # -- credential state -------------------------------------------------------
    EXPIRED = "credential_expired"
    REVOKED = "credential_revoked"
    STATE_UNKNOWN = "credential_state_unknown"
    """Cannot establish whether it is valid. Fails closed -- "not known to be
    invalid" is not "known valid"."""

    # -- provider -----------------------------------------------------------------
    PROVIDER_UNAVAILABLE = "credential_provider_unavailable"
    PROVIDER_REFUSED = "credential_provider_refused"
    PROVIDER_MALFORMED = "credential_provider_malformed"
    NO_PROVIDER = "credential_no_provider"
    """Nothing is registered for this provider and environment. There is no
    fallback, no default, and no system credential."""

    # -- lifecycle -------------------------------------------------------------------
    LIFETIME_UNSUPPORTED = "credential_lifetime_unsupported"
    """The provider cannot issue something short-lived enough. Stated rather than
    accepted: a long-lived secret is not a just-in-time credential, and calling
    it one is the lie that makes the whole model decorative."""

    @property
    def is_retryable(self) -> bool:
        """Whether asking again could plausibly succeed without a decision.

        Deliberately narrow. An authority mismatch will not resolve by being
        asked again, and marking one retryable turns a security refusal into a
        retry loop against the boundary that keeps saying no.
        """
        return self in {
            CredentialRefusal.PROVIDER_UNAVAILABLE,
            CredentialRefusal.STATE_UNKNOWN,
        }

    @property
    def is_security_relevant(self) -> bool:
        return self in {
            CredentialRefusal.TENANT_MISMATCH,
            CredentialRefusal.PRINCIPAL_MISMATCH,
            CredentialRefusal.DELEGATION_NOT_AUTHORIZED,
            CredentialRefusal.ACTION_MISMATCH,
            CredentialRefusal.BINDING_MISMATCH,
            CredentialRefusal.SCOPE_BROADENED,
            CredentialRefusal.RESOURCE_MISMATCH,
            CredentialRefusal.ENVIRONMENT_MISMATCH,
            CredentialRefusal.REVOKED,
        }


class CredentialRefused(ContractViolation):
    """No credential was issued. Carries nothing that could leak."""

    def __init__(
        self,
        refusal: CredentialRefusal,
        message: str,
        *,
        correlation_id: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(f"{refusal.value}: {message}")
        self.refusal = refusal
        self.reason_code = refusal.value
        self.safe_message = message
        self.correlation_id = correlation_id
        self.detail = dict(detail or {})

    @property
    def retryable(self) -> bool:
        return self.refusal.is_retryable

    def to_dict(self) -> dict:
        return {
            "refusal": self.refusal.value,
            "reason": self.safe_message,
            "retryable": self.retryable,
            "security_relevant": self.refusal.is_security_relevant,
            "correlation_id": self.correlation_id,
            **self.detail,
        }


@dataclass(frozen=True)
class CredentialRequest:
    """Everything the fabric needs, stated explicitly. Nothing inferred."""

    tenant_id: str
    principal: PrincipalRef
    provider: str
    environment: ExecutionEnvironment
    scope: CredentialScope

    capability_ref: str
    capability_digest: str
    operation: str

    binding_id: str
    binding_digest: str
    action_digest: str
    """The ADR-038 digest. Not recomputed here -- one action hash exists in this
    platform and this is a reference to it."""

    execution_id: str
    node_id: str
    attempt_id: str

    authorization_digest: str
    authorization_expires_at: datetime
    policy_version: str

    approval_required: bool = False
    approval_artifact_id: Optional[str] = None
    approval_expires_at: Optional[datetime] = None

    on_behalf_of: Optional[PrincipalRef] = None
    """Kept distinct from ``principal``. A worker acting for a human and a human
    acting for themselves are different authorities, and a credential minted for
    the wrong one is the confused deputy in its original form."""

    delegation_authorized: bool = False
    """Whether the authorization decision sanctioned acting for ``on_behalf_of``.

    **Added in Phase 4.4** to close the gap ADR-040 opened and never shut:
    ``DELEGATION_NOT_AUTHORIZED`` was declared as a refusal reason and nothing
    could raise it, because nothing carried an authoritative answer.

    Fail-closed by default, so a caller that forgets it gets a refusal rather
    than a credential. Populated only by the invocation gateway, from the
    authorization decision — never from the request, the tenant, the role or the
    provider account.

    The broker checks it as **defence in depth**, not as the authority: the
    gateway already refused this invocation before a credential request existed.
    Two independent refusals for one mistake is the correct number here, because
    the consequence of missing it is a live provider credential minted under
    somebody else's identity."""

    requested_lifetime_seconds: int = MAX_CREDENTIAL_LIFETIME_SECONDS
    deadline_at: Optional[datetime] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    break_glass_reason: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        for label in (
            "tenant_id",
            "provider",
            "capability_ref",
            "capability_digest",
            "operation",
            "binding_id",
            "binding_digest",
            "action_digest",
            "execution_id",
            "node_id",
            "attempt_id",
            "authorization_digest",
            "policy_version",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a credential request "
                    "missing it cannot be bound to an action, and an unbound "
                    "credential request is a request for any credential"
                )
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if self.on_behalf_of is not None and not isinstance(
            self.on_behalf_of, PrincipalRef
        ):
            raise ContractViolation("on_behalf_of must be a PrincipalRef when present")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation(
                "environment must be an ExecutionEnvironment; a credential for an "
                "unstated environment is a production credential waiting to be "
                "used in development, or the reverse"
            )
        if not isinstance(self.scope, CredentialScope):
            raise ContractViolation(
                "a credential request must state the scope it needs; a request "
                "with no scope is a request for whatever the provider will give"
            )
        if self.authorization_expires_at.tzinfo is None:
            raise ContractViolation("authorization_expires_at must be timezone-aware")
        if self.approval_expires_at is not None and (
            self.approval_expires_at.tzinfo is None
        ):
            raise ContractViolation("approval_expires_at must be timezone-aware")
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            raise ContractViolation("deadline_at must be timezone-aware")
        if not isinstance(self.requested_lifetime_seconds, int) or (
            self.requested_lifetime_seconds < 1
        ):
            raise ContractViolation("requested_lifetime_seconds must be at least 1")
        if self.requested_lifetime_seconds > MAX_CREDENTIAL_LIFETIME_SECONDS:
            raise ContractViolation(
                f"a credential may not be requested for longer than "
                f"{MAX_CREDENTIAL_LIFETIME_SECONDS}s; the ceiling is not "
                "raisable from a call site because the call site is exactly "
                "where it would be raised for convenience"
            )
        if self.approval_required and not self.approval_artifact_id:
            raise ContractViolation(
                "an action requiring approval must name the approval; 'approval "
                "is required and here is none' is not a request that can be "
                "granted"
            )
        if not isinstance(self.delegation_authorized, bool):
            raise ContractViolation("delegation_authorized must be a bool")
        if self.delegation_authorized and self.on_behalf_of is None:
            raise ContractViolation(
                "delegation is marked authorized but no delegated principal is "
                "named; an authorized delegation to nobody is a flag that would "
                "later be read as permission for whoever turns up"
            )
        if self.break_glass_reason is not None and not self.break_glass_reason.strip():
            raise ContractViolation(
                "break-glass requires a stated reason; an emergency lever nobody "
                "has to sign for is a back door"
            )

    # -- queries ---------------------------------------------------------

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    @property
    def effective_principal_id(self) -> str:
        """Whose authority the credential represents.

        The delegated principal when one exists, otherwise the actor. This is the
        identity the provider should see, and keeping it a derived property means
        no call site has to remember which of the two it was.
        """
        return (
            self.on_behalf_of.principal_id
            if self.on_behalf_of is not None
            else self.principal.principal_id
        )

    def effective_expiry(self, now: datetime) -> datetime:
        """The earliest moment any authority behind this credential lapses.

        Four independent clocks bound one credential: the authorization, the
        approval, the execution deadline, and the requested lifetime under the
        hard ceiling. The minimum is the only combination that cannot be widened
        by adding another authority to the list.
        """
        candidates = [
            now + timedelta(
                seconds=min(
                    self.requested_lifetime_seconds, MAX_CREDENTIAL_LIFETIME_SECONDS
                )
            ),
            self.authorization_expires_at,
        ]
        if self.approval_expires_at is not None:
            candidates.append(self.approval_expires_at)
        if self.deadline_at is not None:
            candidates.append(self.deadline_at)
        return min(candidates)

    def remaining_seconds(self, now: datetime) -> int:
        """Whole seconds of authority left, floored. Never rounded up."""
        return int((self.effective_expiry(now) - now).total_seconds())

    def audit_detail(self) -> dict:
        """Attribution for the credential lifecycle. No secret can reach this.

        Built from identifiers and digests only. There is no field here that
        could hold secret material, which is why this is safe to call from an
        audit path without a redaction pass.
        """
        return {
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "effective_principal_id": self.effective_principal_id,
            "on_behalf_of": (
                self.on_behalf_of.principal_id if self.on_behalf_of else None
            ),
            "delegation_authorized": self.delegation_authorized,
            "provider": self.provider,
            "environment": self.environment.value,
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
            "operation": self.operation,
            "binding_id": self.binding_id,
            "binding_digest": self.binding_digest,
            "action_digest": self.action_digest,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "attempt_id": self.attempt_id,
            "authorization_digest": self.authorization_digest,
            "policy_version": self.policy_version,
            "approval_artifact_id": self.approval_artifact_id,
            "requested_scope": self.scope.to_dict(),
            "requested_lifetime_seconds": self.requested_lifetime_seconds,
            "break_glass": self.break_glass_reason is not None,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
        }


@dataclass(frozen=True)
class CredentialGrant:
    """The metadata of an issued credential. **Safe to persist and audit.**

    Deliberately separate from ``CredentialMaterial``: this describes the
    credential, that one *is* it. The split is what lets an execution record say
    which credential was used without the record containing one.
    """

    ref: CredentialRef
    credential_type: CredentialType
    scope: CredentialScope
    state: CredentialState
    issued_at: datetime
    expires_at: datetime

    tenant_id: str
    action_digest: str
    binding_digest: str
    provider: str
    environment: ExecutionEnvironment
    fingerprint: str
    """A non-reversible identifier for the secret value. Lets an audit answer
    "was it the same credential" across two invocations without either record
    containing one."""

    provider_reference: Optional[str] = None
    """The provider's own handle, when it has one and it is not itself secret --
    a Vault path, an OAuth token id. Never the token."""

    def __post_init__(self) -> None:
        if not isinstance(self.ref, CredentialRef):
            raise ContractViolation("ref must be a CredentialRef")
        if not isinstance(self.state, CredentialState):
            raise ContractViolation("state must be a CredentialState")
        if not isinstance(self.scope, CredentialScope):
            raise ContractViolation("scope must be a CredentialScope")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation("environment must be an ExecutionEnvironment")
        for label in ("action_digest", "binding_digest", "fingerprint", "tenant_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if self.expires_at <= self.issued_at:
            raise ContractViolation(
                "a grant must expire after it is issued; one that never expires "
                "is a standing credential wearing a shorter word"
            )
        if self.ref.tenant_id != self.tenant_id:
            raise ContractViolation(
                "the grant's tenant and its reference's tenant disagree; one of "
                "them is somebody else's"
            )

    def is_live_at(self, moment: datetime) -> bool:
        return self.state.permits_use and moment < self.expires_at

    def authorizes(self, request: CredentialRequest) -> bool:
        """Whether this grant is the one for that request.

        Every clause matters. Same tenant, same binding, same action, same
        provider, same environment — and a scope that *covers* what was asked
        rather than merely overlapping it.
        """
        return (
            self.tenant_id == request.tenant_id
            and self.binding_digest == request.binding_digest
            and self.action_digest == request.action_digest
            and self.provider == request.provider
            and self.environment is request.environment
            and self.scope.covers(request.scope)
        )

    def to_dict(self) -> dict:
        return {
            "ref": self.ref.value,
            "credential_type": self.credential_type.value,
            "scope": self.scope.to_dict(),
            "state": self.state.value,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "tenant_id": self.tenant_id,
            "action_digest": self.action_digest,
            "binding_digest": self.binding_digest,
            "provider": self.provider,
            "environment": self.environment.value,
            "fingerprint": self.fingerprint,
            "provider_reference": self.provider_reference,
        }
