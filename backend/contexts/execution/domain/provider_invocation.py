"""The authority an adapter consumes. It cannot be manufactured, only carried.

What this object is
---------------------
Everything the gateway established, frozen into one value and handed down. By
the time one exists, seven things have already happened: the capability was
registered and trusted, the principal was authorized, a binding was made, a
worker was selected, the input was validated, the action was digested, and a
credential was minted for *that digest*. This carries the result of all of it to
the one component that talks to the outside world.

Why it exists at all
----------------------
Because ``WorkerExecutionRequest`` deliberately cannot carry it. That object is
logged, digested and passed between processes, and putting credential material
on it would put a secret in every one of those places. So the authority travels
beside the request, on a type that refuses to be written down.

The rule this object exists to make unbreakable
-------------------------------------------------
**An adapter cannot invent authority.** Every field is required; the digests are
opaque strings Execution cannot compute; the binding is a projection with no
constructor path from nothing (``BoundCapability``); and the credential is
material the credential fabric issued against ``action_digest``. An adapter, a
route or a service that built one of these would still hold nothing that any
downstream check accepts — the provider would reject the credential it could not
produce, and the broker would reject the request it could not sign.

That is why adapters refuse when this is absent rather than proceeding with
defaults. There is no default tenant, no default principal, no default provider
and no default credential anywhere below this line.

Cancellation is carried, not caught
-------------------------------------
``cancellation`` is observed by the adapter and propagated into transport. It is
never used to *report* a cancelled operation as finished: a stop requested after
transmission stops nothing anybody can vouch for, and the outcome stays
ambiguous. See ``CancellationToken.requested``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts._contract import freeze_mapping
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contracts.identity import PrincipalRef
from backend.contracts.provider import ProviderRef
from backend.contexts.execution.domain.bound_capability import BoundCapability

__all__ = [
    "CancellationToken",
    "ProviderAuthority",
    "AuthorityMissing",
]


class AuthorityMissing(ContractViolation):
    """An adapter was asked to act without gateway authority.

    Raised nowhere in the run path — adapters *return* a refusal rather than
    raising, so that a missing authority is recorded as a refused invocation
    rather than as an exception somebody catches. It exists for the construction
    paths, where being handed the wrong thing is a wiring bug and should be loud.
    """


class CancellationToken:
    """A one-way flag, safe to read from a transport thread.

    One direction only: it can be requested and never withdrawn. A token that
    could be un-cancelled would let a race decide whether a stop happened, and
    "was it cancelled" is a question that must have one answer.

    Deliberately not an ``asyncio.Event`` and not a ``threading.Event``: this is
    read by synchronous adapter code and by whatever transport is attached, and
    binding it to one concurrency model would make the other one wrap it.
    """

    __slots__ = ("_lock", "_requested", "_reason", "_requested_at")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requested = False
        self._reason: Optional[str] = None
        self._requested_at: Optional[datetime] = None

    def request(self, reason: str, *, now: Optional[datetime] = None) -> None:
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation(
                "cancelling requires a stated reason; a stop nobody had to "
                "explain is one nobody can account for afterwards"
            )
        with self._lock:
            if self._requested:
                return  # First reason wins. A second is a later fact, not this one.
            self._requested = True
            self._reason = reason
            self._requested_at = now or datetime.now(timezone.utc)

    @property
    def requested(self) -> bool:
        with self._lock:
            return self._requested

    @property
    def reason(self) -> Optional[str]:
        with self._lock:
            return self._reason

    @property
    def requested_at(self) -> Optional[datetime]:
        with self._lock:
            return self._requested_at

    def __repr__(self) -> str:
        return f"<CancellationToken requested={self.requested}>"


@dataclass(frozen=True)
class ProviderAuthority:
    """One authorized provider operation, complete and immutable.

    Frozen, and frozen *for the invocation*: an authority that could change
    while an adapter held it would mean the permission a request was built under
    is not the permission it went out under.
    """

    # -- who and where ---------------------------------------------------
    tenant_id: str
    principal: PrincipalRef
    environment: ExecutionEnvironment
    provider: ProviderRef

    # -- what was authorized ---------------------------------------------
    binding: BoundCapability
    """Mandatory. There is no path to an adapter that does not carry one, and
    it is the authoritative statement of what may be done — not the payload,
    not the operation string, and certainly not the provider's own opinion."""

    action_digest: str
    """The ADR-038 digest, computed once at the gateway over the *validated*
    payload. **Never recomputed here.** One action hash exists in this platform;
    this is a reference to it, and the credential was minted against it."""

    authorization_digest: str
    policy_version: str

    # -- which run ---------------------------------------------------------
    execution_id: str
    node_id: str
    attempt_id: str
    attempt_number: int

    # -- which implementation -----------------------------------------------
    worker_id: str
    worker_digest: str
    selection_id: str

    # -- the operation itself -------------------------------------------------
    payload: Mapping[str, Any] = field(default_factory=dict)
    """Validated input, frozen. The adapter receives exactly the bytes that were
    digested and authorized; nothing below this line may rewrite it, because a
    rewritten payload is an action nobody approved wearing an approved digest."""

    # -- time ---------------------------------------------------------------------
    authority_expires_at: Optional[datetime] = None
    deadline_seconds: Optional[int] = None

    # -- correlation -----------------------------------------------------------------
    idempotency_key: Optional[str] = None
    """Execution's key, passed through untouched. An adapter that minted one
    would give the provider two identities for one logical operation, which is
    the precise opposite of what an idempotency key is for."""

    execution_key: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    on_behalf_of: Optional[PrincipalRef] = None

    # -- runtime-only -------------------------------------------------------------------
    credential: Optional[Any] = field(default=None, repr=False, compare=False)
    """The Phase 4.1 ``IssuedCredential``, present only for the moment of use.

    ``repr=False`` and ``compare=False``, absent from ``to_dict`` and from
    ``audit_detail``. A second guard comes free: ``IssuedCredential.__getstate__``
    raises, so ``dataclasses.asdict`` and every serialiser built on ``deepcopy``
    fail loudly on an authority rather than quietly emitting the secret.
    """

    cancellation: Optional[CancellationToken] = field(
        default=None, repr=False, compare=False
    )

    admitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.binding, BoundCapability):
            raise ContractViolation(
                "a provider authority must carry the capability binding it is "
                "performing; without one an adapter cannot be told what it was "
                "authorized to do, and nothing downstream can check it"
            )
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if self.on_behalf_of is not None and not isinstance(
            self.on_behalf_of, PrincipalRef
        ):
            raise ContractViolation("on_behalf_of must be a PrincipalRef when present")
        if not isinstance(self.provider, ProviderRef):
            raise ContractViolation("provider must be a ProviderRef")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation(
                "an authority must state its environment; a development "
                "authority reaching a production provider is the mistake this "
                "field exists to make impossible"
            )
        for label in (
            "tenant_id",
            "action_digest",
            "authorization_digest",
            "policy_version",
            "execution_id",
            "node_id",
            "attempt_id",
            "worker_id",
            "worker_digest",
            "selection_id",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; an authority missing it "
                    "cannot be bound to an action, and an unbound authority is "
                    "authority for anything"
                )
        if self.attempt_number < 1:
            raise ContractViolation("attempt numbers start at 1")

        # The three places tenancy could disagree, checked against each other.
        # Guessing which one is right would be the whole breach.
        if self.binding.tenant_id != self.tenant_id:
            raise ContractViolation(
                "the authority tenant and the binding tenant disagree; one of "
                "them is somebody else's"
            )
        if self.binding.principal_id != self.principal.principal_id:
            raise ContractViolation(
                "the authority principal and the binding principal disagree; an "
                "adapter does not act as somebody the binding did not name"
            )
        if not self.provider.matches(self.binding.provider):
            raise ContractViolation(
                f"the authority names provider {self.provider.provider_id!r} but "
                f"the binding names {self.binding.provider!r}; a provider "
                "substituted between binding and invocation is a different "
                "external system entirely"
            )
        if (
            self.binding.environment is not None
            and self.binding.environment is not self.environment
        ):
            raise ContractViolation(
                "the authority and the binding name different environments"
            )
        if self.authority_expires_at is not None and (
            self.authority_expires_at.tzinfo is None
        ):
            raise ContractViolation("authority_expires_at must be timezone-aware")
        if self.deadline_seconds is not None and self.deadline_seconds < 1:
            raise ContractViolation("deadline_seconds must be at least 1")

        object.__setattr__(self, "payload", freeze_mapping(self.payload))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def operation(self) -> str:
        """The operation, from the binding. **Never from the payload.**"""
        return self.binding.operation

    @property
    def capability_ref(self) -> str:
        return self.binding.capability_ref

    @property
    def capability_digest(self) -> str:
        return self.binding.capability_digest

    @property
    def binding_digest(self) -> str:
        return self.binding.binding_digest

    @property
    def side_effect_class(self) -> SideEffectClass:
        return self.binding.side_effect_class

    @property
    def effect_semantics(self) -> EffectSemantics:
        return self.binding.effect_semantics

    @property
    def mutates(self) -> bool:
        return self.binding.mutates

    @property
    def is_retry(self) -> bool:
        return self.attempt_number > 1

    @property
    def effective_principal_id(self) -> str:
        """Whose authority this represents: the delegated principal, or the actor."""
        return (
            self.on_behalf_of.principal_id
            if self.on_behalf_of is not None
            else self.principal.principal_id
        )

    @property
    def cancelled(self) -> bool:
        return self.cancellation is not None and self.cancellation.requested

    def remaining_seconds(self, now: datetime) -> float:
        """Whole seconds of authority left. Never negative, never rounded up.

        The minimum of the deadline this invocation was given and the moment its
        authority lapses. Taking the minimum rather than either alone is what
        stops work outliving the permission for it when the two disagree.
        """
        candidates = []
        if self.deadline_seconds is not None:
            candidates.append(float(self.deadline_seconds))
        if self.authority_expires_at is not None:
            candidates.append((self.authority_expires_at - now).total_seconds())
        if not candidates:
            return 0.0
        return max(0.0, min(candidates))

    def timeout_seconds(self, *provider_limits: Optional[float], now: datetime) -> float:
        """The bound for one provider exchange: the smallest limit that applies.

        ``min(provider limit, transport limit, remaining authority)`` — ADR-042
        §23. A ``None`` limit is one nobody stated and is skipped rather than
        read as unbounded, because the authority window is always present and is
        the ceiling that matters.
        """
        limits = [value for value in provider_limits if value is not None and value > 0]
        window = self.remaining_seconds(now)
        limits.append(window)
        return max(0.0, min(limits))

    def is_live_at(self, moment: datetime) -> bool:
        """Whether every clock behind this invocation still permits it."""
        if not self.binding.is_live_at(moment):
            return False
        if self.authority_expires_at is not None and moment >= self.authority_expires_at:
            return False
        credential = getattr(self.credential, "grant", None)
        if credential is not None and not credential.is_live_at(moment):
            return False
        return True

    def has_credential(self) -> bool:
        return self.credential is not None

    @property
    def credential_grant(self) -> Optional[Any]:
        """The safe half of the credential: reference, scope, expiry, fingerprint."""
        return getattr(self.credential, "grant", None)

    @property
    def credential_material(self) -> Optional[Any]:
        """The Phase 4.1 ``CredentialMaterial``, for handing to transport only.

        Reached through a property rather than stored twice so there is exactly
        one place the material lives on this object. Every caller of this is a
        transport hand-off, and there are deliberately few of them.
        """
        return getattr(self.credential, "material", None)

    # ------------------------------------------------------------------
    # Records
    # ------------------------------------------------------------------

    def audit_detail(self) -> dict:
        """Full attribution for one provider operation. No secret can reach this.

        Built from identifiers and digests only. There is no branch here that
        can emit a credential, a token or a payload, because none of them is in
        scope — the credential contributes a reference and a fingerprint, both
        of which are safe to write down and neither of which is reversible.
        """
        grant = self.credential_grant
        return {
            "tenant_id": self.tenant_id,
            "principal_id": self.principal.principal_id,
            "effective_principal_id": self.effective_principal_id,
            "on_behalf_of": (
                self.on_behalf_of.principal_id if self.on_behalf_of else None
            ),
            "provider": self.provider.provider_id,
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
            "operation": self.operation,
            "binding_id": self.binding.binding_id,
            "binding_digest": self.binding_digest,
            "action_digest": self.action_digest,
            "authorization_digest": self.authorization_digest,
            "policy_version": self.policy_version,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "attempt_id": self.attempt_id,
            "attempt_number": self.attempt_number,
            "worker_id": self.worker_id,
            "worker_digest": self.worker_digest,
            "selection_id": self.selection_id,
            "environment": self.environment.value,
            "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "idempotency_key_present": self.idempotency_key is not None,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "credential_ref": grant.ref.value if grant is not None else None,
            "credential_fingerprint": grant.fingerprint if grant is not None else None,
        }

    def to_dict(self) -> dict:
        """Safe for logs and events. **No payload and no credential material.**"""
        return self.audit_detail()

    def __repr__(self) -> str:
        return (
            f"<ProviderAuthority {self.provider.provider_id}/{self.operation} "
            f"tenant={self.tenant_id} action={self.action_digest[:12]}…>"
        )
