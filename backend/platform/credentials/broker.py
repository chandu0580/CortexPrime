"""The credential broker: the one place a credential is issued, and every refusal.

What it is
------------
A fail-closed orchestrator between a request and a provider adapter. It checks
what it can check, asks the adapter, then checks what came back — and refuses at
any point rather than proceeding with something it cannot vouch for.

It is **not** an authorization system. Every authority input arrives already
decided: the authorization digest and expiry come from ADR-034's decision, the
approval from the existing approval machinery, the binding from ADR-035, the
action digest from ADR-038. The broker verifies they still agree and that the
credential it hands back is bounded by them. It never *makes* one of those
decisions, and it can never turn a refusal upstream into an allow here.

Possession is not authority
-----------------------------
Issuing a credential says the caller may authenticate to a provider. It does not
say CortexPrime authorized the action — the invocation gateway already said that,
and a credential obtained here does not revisit it. That separation is why a
leaked credential still fails at the gate.

The check that runs after the provider answers
------------------------------------------------
The most important code in this module is the *post*-issuance verification.
A provider adapter is infrastructure somebody else may have written, and it can
return a credential that is broader than requested, for the wrong tenant, for the
wrong resource, or already expired. Each of those is refused, and the broadened
one is refused loudest: a credential stronger than the authority that asked for
it is a privilege escalation delivered by the component meant to prevent one.

No fallback, anywhere
-----------------------
No default provider. No system credential. No other tenant's credential. No
cached unrelated token. No environment variable. If the requested credential
cannot be obtained, the answer is a refusal, and what happens next is the
caller's decision with the facts in front of it.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.credential import CredentialRef, CredentialState
from backend.contracts.errors import ContractViolation
from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.redaction import safe_exception_text
from backend.platform.credentials.request import (
    CredentialGrant,
    CredentialRefusal,
    CredentialRefused,
    CredentialRequest,
)

__all__ = [
    "IssuedCredential",
    "CredentialAdapter",
    "AuthorityRevalidator",
    "CredentialBroker",
    "CREDENTIAL_METRICS",
]

log = logging.getLogger(__name__)

CREDENTIAL_METRICS = (
    "credential.acquisition.success",
    "credential.acquisition.failure",
    "credential.expired",
    "credential.revoked",
    "credential.scope_denied",
    "credential.provider_unavailable",
    "credential.state_unknown",
    "credential.break_glass",
)


class IssuedCredential:
    """What an adapter returns: the grant and the material, together and briefly.

    Not a dataclass and not serialisable, for the same reason
    ``CredentialMaterial`` is not: an object holding both the description and the
    secret is exactly the object somebody would log to see "what credential did
    we get". Its ``__repr__`` shows the grant and never the material.
    """

    __slots__ = ("grant", "material")

    def __init__(self, grant: CredentialGrant, material: CredentialMaterial) -> None:
        if not isinstance(grant, CredentialGrant):
            raise ContractViolation("grant must be a CredentialGrant")
        if not isinstance(material, CredentialMaterial):
            raise ContractViolation("material must be CredentialMaterial")
        if material.ref != grant.ref:
            raise ContractViolation(
                "the material and the grant name different credentials; one of "
                "them describes something that is not what was handed over"
            )
        self.grant = grant
        self.material = material

    def __repr__(self) -> str:
        return f"<IssuedCredential {self.grant.ref.value} state={self.grant.state.value}>"

    __str__ = __repr__

    def __getstate__(self) -> Any:
        raise ContractViolation(
            "an issued credential cannot be serialised; it holds material. "
            "Persist the grant"
        )


@runtime_checkable
class CredentialAdapter(Protocol):
    """A provider-neutral adapter. Vendor code lives behind this, never in front.

    Three verbs, and only where the underlying mechanism supports them. A static
    API key has no meaningful ``revoke``; an OAuth broker does. An adapter says
    which it supports rather than pretending uniformly.

    **No vendor appears in the domain.** Vault, AWS Secrets Manager, Azure Key
    Vault and an OAuth broker are all implementations of this, wired at the
    composition root. A fabric that named one would need changing for the second.
    """

    @property
    def provider_id(self) -> str:
        """Which provider this adapter serves. Matched against the request."""
        ...

    @property
    def environments(self) -> frozenset:
        """Environments this adapter may issue for. Explicit; no wildcard."""
        ...

    def acquire(
        self, request: CredentialRequest, *, expires_at: datetime, now: datetime
    ) -> Any:
        """Obtain a credential, expiring no later than ``expires_at``.

        ``now`` is the broker's clock reading, passed in rather than read.
        An adapter reading its own clock would let a request be simultaneously
        inside its authority window (per the broker) and outside it (per the
        adapter) — the same two-clock defect the invocation gateway closed by
        threading its clock into the worker runtime.

        Returns an ``IssuedCredential``. Raising, returning ``None``, or
        returning anything else is a refusal — never an allow.
        """
        ...

    def validate(self, ref: CredentialRef) -> CredentialState:
        """The authoritative current state. ``UNKNOWN`` when it cannot be told."""
        ...

    def revoke(self, ref: CredentialRef, *, reason: str) -> bool:
        """Withdraw the credential. ``False`` when the mechanism cannot."""
        ...


@runtime_checkable
class AuthorityRevalidator(Protocol):
    """Re-checks the authority chain immediately before material is handed over.

    The TOCTOU close for credentials. Between the gateway admitting an invocation
    and the credential being minted, a capability can be revoked, a binding
    invalidated, or a grant withdrawn — and a credential minted after that is a
    credential minted for something no longer permitted.

    Returns refusal reasons; empty means still valid. Implemented at the
    composition root over the same authorities the gateway already consults, so
    this is a re-read rather than a second opinion.
    """

    def still_valid(self, request: CredentialRequest) -> tuple: ...


class CredentialBroker:
    """Issues credentials, or explains precisely why it will not."""

    def __init__(
        self,
        *,
        adapters: Optional[Mapping[str, CredentialAdapter]] = None,
        revalidator: Optional[AuthorityRevalidator] = None,
        audit: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Callable[[], datetime]] = None,
        allow_partial_scope: bool = False,
    ) -> None:
        self._adapters: dict = dict(adapters or {})
        self._revalidator = revalidator
        self._audit = audit
        self._metrics = metrics
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._allow_partial_scope = allow_partial_scope
        """When false -- the default -- a provider issuing narrower scope than
        requested is a refusal. Only a caller that has actually thought about
        partial authorization may turn this on, and turning it on is a decision
        about that caller's operation rather than a global convenience."""

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, adapter: CredentialAdapter) -> None:
        """Attach a provider adapter. Explicit, and never silently replaced."""
        provider = adapter.provider_id
        if not isinstance(provider, str) or not provider.strip():
            raise ContractViolation("an adapter must name the provider it serves")
        if provider in self._adapters:
            raise ContractViolation(
                f"an adapter for {provider!r} is already registered; silently "
                "replacing one would change where credentials come from without "
                "anybody deciding"
            )
        if not adapter.environments:
            raise ContractViolation(
                f"adapter {provider!r} declares no environment; absence is not a "
                "wildcard, and an adapter entitled to nowhere would either never "
                "issue or -- read as 'anywhere' -- issue into production"
            )
        self._adapters[provider] = adapter

    @property
    def providers(self) -> tuple:
        return tuple(sorted(self._adapters))

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def acquire(self, request: CredentialRequest) -> IssuedCredential:
        """The only way a credential is obtained. Every path out is checked."""
        if not isinstance(request, CredentialRequest):
            raise ContractViolation("acquire takes a CredentialRequest")
        now = self._clock()

        # 1. The authority window -- specific reasons first.
        #
        # Ordering matters here. The aggregate window is the minimum of every
        # expiry, so an expired authorization also closes the window. Checking
        # the aggregate first would report AUTHORITY_WINDOW_CLOSED for every
        # cause and leave an operator to work out which of four clocks ran out.
        # The specific reasons are checked before the sum of them.
        if request.authorization_expires_at <= now:
            raise self._refuse(
                request,
                CredentialRefusal.AUTHORIZATION_EXPIRED,
                "the authorization behind this request has expired",
            )
        # 1a. Delegation. **Phase 4.4** -- the refusal ADR-040 declared and
        #     could not raise. Checked before the adapter is even looked up, so
        #     an unsanctioned delegation never reaches a secret store.
        #
        #     Defence in depth rather than the authority: the gateway refused
        #     this invocation before a credential request existed. It is checked
        #     twice because the consequence of missing it once is a live provider
        #     credential minted under a principal nobody authorized.
        if request.on_behalf_of is not None and not request.delegation_authorized:
            raise self._refuse(
                request,
                CredentialRefusal.DELEGATION_NOT_AUTHORIZED,
                "this request acts on behalf of another principal and no "
                "authorization sanctioned the delegation",
            )
        if request.approval_required:
            if not request.approval_artifact_id:
                raise self._refuse(
                    request,
                    CredentialRefusal.APPROVAL_REQUIRED,
                    "this action requires approval and none is recorded",
                )
            if (
                request.approval_expires_at is not None
                and request.approval_expires_at <= now
            ):
                raise self._refuse(
                    request,
                    CredentialRefusal.APPROVAL_EXPIRED,
                    "the approval behind this request has expired",
                )
        # Now the aggregate: the deadline, the requested lifetime, or simply no
        # time left once everything is taken together.
        if request.remaining_seconds(now) <= 0:
            raise self._refuse(
                request,
                CredentialRefusal.AUTHORITY_WINDOW_CLOSED,
                "no authority window remains for this action",
            )

        # 2. TOCTOU. Re-read the authority chain immediately before minting.
        self._revalidate(request)

        # 3. An adapter for this provider, in this environment. No default.
        adapter = self._adapters.get(request.provider)
        if adapter is None:
            raise self._refuse(
                request,
                CredentialRefusal.NO_PROVIDER,
                "no credential adapter is registered for this provider; there is "
                "no default credential and no fallback",
            )
        if request.environment not in adapter.environments:
            raise self._refuse(
                request,
                CredentialRefusal.ENVIRONMENT_MISMATCH,
                "the adapter is not registered for this environment",
            )

        expires_at = request.effective_expiry(now)

        # 4. The provider call. Anything other than a well-formed answer refuses.
        try:
            issued = adapter.acquire(request, expires_at=expires_at, now=now)
        except CredentialRefused:
            raise
        except Exception as exc:  # noqa: BLE001 - unavailable is never allow
            # Never str(exc) unguarded: an HTTP client's exception routinely
            # carries the request it was making, headers included.
            log.warning(
                "credential adapter %s failed: %s",
                request.provider,
                safe_exception_text(exc),
            )
            raise self._refuse(
                request,
                CredentialRefusal.PROVIDER_UNAVAILABLE,
                f"the credential provider could not be reached ({type(exc).__name__})",
            ) from None

        if issued is None:
            raise self._refuse(
                request,
                CredentialRefusal.PROVIDER_REFUSED,
                "the credential provider declined to issue",
            )
        if not isinstance(issued, IssuedCredential):
            raise self._refuse(
                request,
                CredentialRefusal.PROVIDER_MALFORMED,
                "the credential provider returned something uninterpretable",
            )

        # 5. What came back is checked against what was asked for.
        self._verify(request, issued, now=now, ceiling=expires_at)

        self._record(request, issued.grant)
        self._count("credential.acquisition.success", request)
        return issued

    # ------------------------------------------------------------------
    # Post-issuance verification -- the most important checks here
    # ------------------------------------------------------------------

    def _verify(
        self,
        request: CredentialRequest,
        issued: IssuedCredential,
        *,
        now: datetime,
        ceiling: datetime,
    ) -> None:
        """Everything an adapter could get wrong, checked before use."""
        grant = issued.grant

        if not grant.ref.belongs_to(request.tenant_id):
            # The worst thing an adapter can do: hand back another tenant's
            # credential. Checked first and refused unconditionally.
            raise self._refuse(
                request,
                CredentialRefusal.TENANT_MISMATCH,
                "the issued credential belongs to a different tenant",
            )
        if grant.tenant_id != request.tenant_id:
            raise self._refuse(
                request,
                CredentialRefusal.TENANT_MISMATCH,
                "the issued grant names a different tenant",
            )
        if grant.action_digest != request.action_digest:
            # The confused-deputy check. A credential minted for a different
            # action is a credential for a different resource.
            raise self._refuse(
                request,
                CredentialRefusal.ACTION_MISMATCH,
                "the issued credential is bound to a different action",
            )
        if grant.binding_digest != request.binding_digest:
            raise self._refuse(
                request,
                CredentialRefusal.BINDING_MISMATCH,
                "the issued credential is bound to a different capability binding",
            )
        if grant.provider != request.provider:
            raise self._refuse(
                request,
                CredentialRefusal.PROVIDER_MALFORMED,
                "the issued credential names a different provider",
            )
        if grant.environment is not request.environment:
            raise self._refuse(
                request,
                CredentialRefusal.ENVIRONMENT_MISMATCH,
                "the issued credential is for a different environment",
            )

        # -- state -----------------------------------------------------
        if grant.state is CredentialState.REVOKED:
            self._count("credential.revoked", request)
            raise self._refuse(
                request, CredentialRefusal.REVOKED, "the credential is revoked"
            )
        if grant.state is CredentialState.EXPIRED or grant.expires_at <= now:
            self._count("credential.expired", request)
            raise self._refuse(
                request, CredentialRefusal.EXPIRED, "the credential has already expired"
            )
        if grant.state is not CredentialState.ACTIVE:
            # UNKNOWN, or anything added later. Not known valid is not valid.
            self._count("credential.state_unknown", request)
            raise self._refuse(
                request,
                CredentialRefusal.STATE_UNKNOWN,
                "the credential state could not be established",
            )

        # -- lifetime ---------------------------------------------------
        if grant.expires_at > ceiling:
            # A credential outliving the authority that requested it. Refused
            # rather than truncated: truncating would mean the provider still
            # holds something valid that we have decided to stop using.
            raise self._refuse(
                request,
                CredentialRefusal.LIFETIME_UNSUPPORTED,
                "the provider issued a credential outliving the authority for it",
            )
        if issued.material.expires_at > ceiling:
            raise self._refuse(
                request,
                CredentialRefusal.LIFETIME_UNSUPPORTED,
                "the credential material outlives the authority for it",
            )

        # -- scope ------------------------------------------------------
        if grant.scope.resource != request.scope.resource:
            raise self._refuse(
                request,
                CredentialRefusal.RESOURCE_MISMATCH,
                "the issued credential is scoped to a different resource",
            )
        broadened = grant.scope.tokens - request.scope.tokens
        if broadened:
            # A credential stronger than the authority that asked for it.
            self._count("credential.scope_denied", request)
            raise self._refuse(
                request,
                CredentialRefusal.SCOPE_BROADENED,
                "the provider issued broader scope than was requested",
            )
        missing = request.scope.missing_from(grant.scope)
        if missing and not self._allow_partial_scope:
            self._count("credential.scope_denied", request)
            raise self._refuse(
                request,
                CredentialRefusal.INSUFFICIENT_SCOPE,
                "the provider could not issue the scope this action needs",
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def validate(self, ref: CredentialRef, *, tenant_id: str) -> CredentialState:
        """Ask the authoritative state. Fails closed to ``UNKNOWN``.

        Tenant-checked before anything else, and a foreign reference gets the
        same answer as an unknown one: confirming that another tenant's
        credential exists is itself a disclosure.
        """
        if not ref.belongs_to(tenant_id):
            return CredentialState.UNKNOWN
        adapter = self._adapter_for_ref(ref)
        if adapter is None:
            return CredentialState.UNKNOWN
        try:
            state = adapter.validate(ref)
        except Exception as exc:  # noqa: BLE001
            log.warning("credential validation failed: %s", safe_exception_text(exc))
            return CredentialState.UNKNOWN
        return state if isinstance(state, CredentialState) else CredentialState.UNKNOWN

    def revoke(self, ref: CredentialRef, *, tenant_id: str, reason: str) -> bool:
        """Withdraw a credential. Returns whether the provider confirmed it.

        ``False`` is an honest answer for a mechanism that cannot revoke — a
        static API key does not stop working because we asked it to, and
        reporting success would leave an operator believing a live secret is dead.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("revoking a credential requires a stated reason")
        if not ref.belongs_to(tenant_id):
            return False
        adapter = self._adapter_for_ref(ref)
        if adapter is None:
            return False
        try:
            return bool(adapter.revoke(ref, reason=reason))
        except Exception as exc:  # noqa: BLE001
            log.warning("credential revocation failed: %s", safe_exception_text(exc))
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _adapter_for_ref(self, ref: CredentialRef) -> Optional[CredentialAdapter]:
        """Find the adapter that issued a reference.

        Linear rather than indexed: the adapter set is small, fixed at
        composition, and an index would be a second place the mapping could be
        wrong.
        """
        for adapter in self._adapters.values():
            try:
                if adapter.validate(ref) is not CredentialState.UNKNOWN:
                    return adapter
            except Exception:  # noqa: BLE001
                continue
        return None

    def _revalidate(self, request: CredentialRequest) -> None:
        if self._revalidator is None:
            return
        try:
            problems = self._revalidator.still_valid(request)
        except Exception as exc:  # noqa: BLE001 - unverifiable is unusable
            raise self._refuse(
                request,
                CredentialRefusal.STATE_UNKNOWN,
                f"the authority could not be revalidated ({type(exc).__name__})",
            ) from None
        if problems:
            raise self._refuse(
                request,
                CredentialRefusal.AUTHORITY_WINDOW_CLOSED,
                "the authority changed between admission and credential issuance",
                detail={"reasons": [str(p) for p in problems]},
            )

    def _refuse(
        self,
        request: CredentialRequest,
        refusal: CredentialRefusal,
        message: str,
        *,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> CredentialRefused:
        self._count("credential.acquisition.failure", request, refusal=refusal.value)
        self._record_refusal(request, refusal, message)
        return CredentialRefused(
            refusal,
            message,
            correlation_id=request.correlation_id,
            detail=dict(detail or {}),
        )

    # -- audit and metrics ------------------------------------------------

    def _record(self, request: CredentialRequest, grant: CredentialGrant) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        self._safe_audit(
            AuditEventKind.IDENTITY_EVENT, request,
            subject_reference=grant.ref.value,
            detail={**request.audit_detail(), **grant.to_dict(), "issued": True},
        )

    def _record_refusal(
        self,
        request: CredentialRequest,
        refusal: CredentialRefusal,
        message: str,
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        self._safe_audit(
            AuditEventKind.EXECUTION_REFUSED, request,
            subject_reference=request.capability_ref,
            detail={
                **request.audit_detail(),
                "issued": False,
                "refusal": refusal.value,
                "reason": message,
                "security_relevant": refusal.is_security_relevant,
            },
        )

    def _safe_audit(self, kind: Any, request: Any, **fields: Any) -> None:
        """Audit failure never turns a refusal into an allow.

        The decision is already made by the time anything is written. A raise
        here would propagate out of a refusal path and could be caught as
        something other than a refusal.
        """
        try:
            from backend.contracts.tenant import TenantRef, TenantScope

            # AuditRuntime.record takes the tenant scope positionally; the
            # call without it raised TypeError on EVERY fact, swallowed here,
            # so no credential fact ever reached the chain (Phase 11.1-K).
            self._audit.record(
                kind, TenantScope(tenant=TenantRef(tenant_id=request.tenant_id)),
                actor=request.principal, **fields)
        except Exception as exc:  # noqa: BLE001
            log.error("recording a credential audit fact failed: %s: %s",
                      type(exc).__name__, str(exc)[:300], exc_info=False)

    def _count(
        self, name: str, request: CredentialRequest, **extra: str
    ) -> None:
        """Metrics carry the tenant and the provider. Never a secret, never a ref.

        A credential reference is not secret, but it is high-cardinality and
        identifies one credential — as a metric dimension it would turn a
        dashboard into a credential inventory.
        """
        if self._metrics is None:
            return
        try:
            self._metrics.increment(
                name,
                labels={
                    "tenant": request.tenant_id,
                    "provider": request.provider,
                    "environment": request.environment.value,
                    **extra,
                },
            )
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("credential metric failed", exc_info=False)
