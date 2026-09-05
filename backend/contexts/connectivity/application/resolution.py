"""Resolution and binding.

The order is the security model
--------------------------------
1. **Verify the authorization** — live, digest-verifiable, and about *this*
   request. Nothing else happens until this passes.
2. **Snapshot the candidates** — one authoritative read, then no further reads.
3. **Filter** — remove everything ineligible, recording why.
4. **Rank** — only among survivors, on dimensions the registry actually holds.
5. **Refuse ambiguity** — equal candidates produce a refusal, not a coin toss.
6. **Bind** — freeze the choice, digest it, and give it an expiry.

Ranking never runs before filtering, so no score can promote a revoked,
untrusted or cross-tenant candidate. That is enforced by the shape of the code
rather than by a rule inside the ranker.

Resolution grants nothing
---------------------------
It consumes an ``AuthorizationDecision`` and re-verifies it rather than trusting
that a caller obtained one. A decision that is denied, requires approval, has
expired, does not recompute to its own digest, or was made about a different
request is refused — five separate checks, because each is a different way for
an unauthorized call to look authorized.

Deliberately absent
---------------------
No fallback rebinding. If the selected provider later fails, that is a runtime
decision about whether a retry is *safe* (Phase 3.1 already owns it), not a
licence for this service to quietly pick somebody else. No cache: a stale entry
could select a revoked capability, and correctness outranks the lookup cost.
No LLM anywhere — selection is deterministic and inspectable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from backend.contracts.audit import AuditEventKind
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics
from backend.contexts.connectivity.application.commands import ListVersions
from backend.contexts.connectivity.domain.binding import CapabilityBinding
from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
from backend.contexts.connectivity.domain.errors import CapabilityNotFound
from backend.contexts.connectivity.domain.events import (
    CapabilityBound,
    CapabilityResolved,
    CapabilityResolutionRefused,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState
from backend.contexts.connectivity.domain.resolution import (
    RESOLUTION_POLICY_VERSION,
    CandidateSnapshot,
    RankedCandidate,
    RejectionReason,
    ResolutionFailure,
    ResolutionRequest,
    ResolutionResult,
    VersionSelection,
    trust_rank_of,
)
from backend.platform.events import EventMetadata

__all__ = ["CapabilityResolutionService", "ResolutionOutcome", "DEFAULT_BINDING_TTL"]

#: A binding lives no longer than the authorization behind it, and no longer
#: than this. Short, because a binding is a statement about the world at one
#: instant and the world moves.
DEFAULT_BINDING_TTL = timedelta(minutes=5)

#: How strong an effect each semantics represents, for the "no stronger than
#: requested" check. UNKNOWN sits above everything declared: a caller who asked
#: for a read must never be bound to something whose behaviour nobody stated.
_EFFECT_STRENGTH = {
    EffectSemantics.READ_ONLY: 0,
    EffectSemantics.IDEMPOTENT_WRITE: 1,
    EffectSemantics.NON_IDEMPOTENT_WRITE: 2,
    EffectSemantics.UNKNOWN: 3,
}


class ResolutionOutcome:
    """A resolution result plus the binding it produced, if any."""

    __slots__ = ("result", "binding", "events")

    def __init__(self, result: ResolutionResult, binding=None, events: tuple = ()) -> None:
        self.result = result
        self.binding = binding
        self.events = events

    @property
    def resolved(self) -> bool:
        return self.binding is not None

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)

    def to_dict(self, *, redacted: bool = False) -> dict:
        return {
            "resolved": self.resolved,
            "result": (
                self.result.redacted() if redacted else self.result.to_dict()
            ),
            "binding": self.binding.to_dict() if self.binding else None,
            "events": list(self.event_types),
        }


class CapabilityResolutionService:
    """Selects one capability and freezes the choice. Executes nothing."""

    def __init__(
        self,
        *,
        registry: Any,
        bindings: Any = None,
        audit: Any = None,
        binding_ttl: timedelta = DEFAULT_BINDING_TTL,
    ) -> None:
        self._registry = registry
        self._bindings = bindings
        self._audit = audit
        self._binding_ttl = binding_ttl

    @property
    def policy_version(self) -> str:
        return RESOLUTION_POLICY_VERSION

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(
        self,
        context: Any,
        request: ResolutionRequest,
        *,
        bind: bool = True,
        now: Optional[datetime] = None,
    ) -> ResolutionOutcome:
        moment = now or datetime.now(timezone.utc)

        refusal = self._authorization_refusal(request, moment)
        if refusal is not None:
            return self._refused(context, request, refusal[0], refusal[1], moment)

        candidates = self._snapshot(context, request)
        if not candidates:
            return self._refused(
                context,
                request,
                ResolutionFailure.CAPABILITY_NOT_FOUND,
                # Same answer whether it does not exist or is invisible here.
                "no capability with that identity is visible to this tenant",
                moment,
            )

        eligible, rejected = self._filter(request, candidates)
        if not eligible:
            failure = (
                ResolutionFailure.VERSION_NOT_FOUND
                if all(r is RejectionReason.VERSION_MISMATCH for _, r in rejected)
                else ResolutionFailure.NO_ELIGIBLE_CANDIDATE
            )
            return self._refused(
                context,
                request,
                failure,
                f"{len(rejected)} candidate(s) were rejected; none remained",
                moment,
                rejected=rejected,
                candidate_count=len(candidates),
            )

        ranked = sorted(
            eligible, key=lambda c: (tuple(-v for v in c.sort_key), c.tie_breaker)
        )
        best = ranked[0]

        # Ambiguity: two survivors equal on every dimension the platform has real
        # data for. Choosing between them would be a hidden provider decision,
        # which is exactly what this phase exists to remove.
        #
        # **Currently unreachable, and kept deliberately.** An AuthorizationDecision
        # pins one exact capability digest (ADR-034), and (capability_id, version)
        # is unique in the registry -- so the eligibility filter narrows to at most
        # one candidate before ranking ever runs. The "three providers of the same
        # capability" case is therefore decided at authorization, not here.
        #
        # The branch stays because that is a property of the *current* authorization
        # model rather than of resolution. If a later policy ever issues
        # capability-scoped authorization without a digest, this refuses instead of
        # silently picking a provider -- which is the behaviour that must not have
        # to be remembered and re-added at that point.
        if len(ranked) > 1 and ranked[1].sort_key == best.sort_key:
            contenders = [c for c in ranked if c.sort_key == best.sort_key]
            return self._refused(
                context,
                request,
                ResolutionFailure.AMBIGUOUS_RESOLUTION,
                (
                    f"{len(contenders)} candidates are equally eligible "
                    f"({', '.join(sorted(c.candidate.provider for c in contenders))}); "
                    "constrain the request by version or provider rather than "
                    "letting the platform choose"
                ),
                moment,
                rejected=rejected,
                candidate_count=len(candidates),
            )

        result = ResolutionResult(
            request=request,
            policy_version=self.policy_version,
            resolved_at=moment,
            selected=best,
            rejected=tuple(rejected),
            candidate_count=len(candidates),
        )

        events: list = [
            CapabilityResolved(
                metadata=self._metadata(context, request),
                capability_id=request.capability_id.value,
                version=best.candidate.version.number,
                digest=best.candidate.digest,
                provider=best.candidate.provider,
                operation=request.operation.value,
                policy_version=self.policy_version,
                candidate_count=len(candidates),
                rejected_count=len(rejected),
            )
        ]

        if not bind:
            self._audit_fact(context, AuditEventKind.POLICY_EVALUATED, request, result)
            return ResolutionOutcome(result, None, tuple(events))

        binding = CapabilityBinding.create(
            tenant_id=request.tenant_id,
            principal=request.principal,
            candidate=best.candidate,
            operation=request.operation,
            authorization_digest=request.authorization.digest,
            authorization_policy_version=request.authorization.policy_version,
            resolution_policy_version=self.policy_version,
            # Never outlives the authorization behind it.
            expires_at=min(moment + self._binding_ttl, request.authorization.expires_at),
            selection_reasons=best.reasons,
            rejected_candidates=tuple((ref, r.value) for ref, r in rejected),
            candidate_count=len(candidates),
            mission_id=request.mission_id,
            workflow_id=request.workflow_id,
            execution_id=request.execution_id,
            node_id=request.node_id,
            now=moment,
        )

        if self._bindings is not None:
            self._bindings.save(context, binding)

        events.append(
            CapabilityBound(
                metadata=self._metadata(context, request),
                capability_id=request.capability_id.value,
                version=binding.version.number,
                digest=binding.capability_digest,
                provider=binding.provider,
                operation=binding.operation.value,
                binding_id=binding.binding_id,
                binding_digest=binding.digest or "",
                authorization_digest=binding.authorization_digest,
                expires_at=binding.expires_at.isoformat(),
            )
        )
        self._audit_fact(
            context, AuditEventKind.POLICY_EVALUATED, request, result, binding=binding
        )
        return ResolutionOutcome(result, binding, tuple(events))

    # ------------------------------------------------------------------
    # The execution boundary
    # ------------------------------------------------------------------

    def validate_binding(
        self,
        context: Any,
        binding: CapabilityBinding,
        *,
        tenant_id: str,
        principal_id: str,
        execution_id: Optional[str] = None,
        node_id: Optional[str] = None,
        authorization_live: bool = True,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Re-check a binding against authoritative state. Returns invalidations.

        The TOCTOU close. Resolution happened at T; this runs at T+N and re-reads
        rather than trusting what the binding remembers. Empty tuple means usable.
        """
        moment = now or datetime.now(timezone.utc)

        try:
            binding.verify_digest()
        except Exception:  # noqa: BLE001 - a tampered binding is unusable
            from backend.contexts.connectivity.domain.binding import BindingInvalidation

            return (BindingInvalidation.TAMPERED,)

        from backend.contexts.connectivity.domain.binding import BindingInvalidation

        if not binding.matches_execution(
            tenant_id=tenant_id,
            principal_id=principal_id,
            execution_id=execution_id,
            node_id=node_id,
        ):
            # Presented against a run it was not made for.
            self._audit_replay(context, binding, execution_id)
            return (BindingInvalidation.BINDING_MISMATCH,)

        current = self._current(context, binding)
        return binding.invalidations_against(
            current_status=current[0],
            current_trust=current[1],
            current_digest=current[2],
            current_provider=current[3],
            authorization_live=authorization_live,
            now=moment,
        )

    # ------------------------------------------------------------------
    # Authorization compatibility
    # ------------------------------------------------------------------

    def _authorization_refusal(
        self, request: ResolutionRequest, moment: datetime
    ) -> Optional[tuple]:
        """Five ways an unauthorized call can look authorized. All refused."""
        decision = request.authorization

        if not decision.allowed:
            return (
                ResolutionFailure.AUTHORIZATION_REQUIRED,
                f"authorization is {decision.effect.value}, not allow",
            )
        if not decision.is_live_at(moment):
            return (
                ResolutionFailure.AUTHORIZATION_EXPIRED,
                "the authorization decision has expired; renewal is a new decision",
            )

        # The decision must recompute to its own digest. A decision edited in
        # transit is not a decision.
        recomputed = decision.payload_digest().value
        if not decision.digest or recomputed != decision.digest:
            return (
                ResolutionFailure.AUTHORIZATION_UNVERIFIED,
                "the authorization decision does not match its own digest",
            )

        # And it must be about this request.
        if decision.request.capability_ref.capability_id != request.capability_id:
            return (
                ResolutionFailure.AUTHORIZATION_MISMATCH,
                "the authorization is for a different capability",
            )
        if decision.request.operation is not request.operation:
            return (
                ResolutionFailure.AUTHORIZATION_MISMATCH,
                "the authorization is for a different operation",
            )
        if (
            decision.request.tenant_id != request.tenant_id
            or decision.request.principal.principal_id != request.principal.principal_id
        ):
            return (
                ResolutionFailure.AUTHORIZATION_MISMATCH,
                "the authorization is for a different tenant or principal",
            )

        if (
            request.requires_execution_grade_selection
            and not request.version_selection.permits_execution
        ):
            return (
                ResolutionFailure.VERSION_SELECTION_NOT_PERMITTED,
                "execution requires an exact version; automatic selection would "
                "let the platform choose which contract to run",
            )
        return None

    # ------------------------------------------------------------------
    # Candidates
    # ------------------------------------------------------------------

    def _snapshot(self, context: Any, request: ResolutionRequest) -> tuple:
        """One authoritative read. Ranking never fetches anything after this."""
        try:
            versions = self._registry.versions(
                context, ListVersions(capability_id=request.capability_id.value)
            )
        except CapabilityNotFound:
            return ()
        except Exception:  # noqa: BLE001 - a registry that cannot answer resolves nothing
            return ()

        moment = datetime.now(timezone.utc)
        return tuple(
            CandidateSnapshot(
                capability_id=d.capability_id,
                version=d.version,
                digest=d.digest or "",
                provider=d.provider,
                status=d.status,
                trust=d.trust,
                tenancy=d.tenancy.value,
                tenant_id=d.tenant_id,
                source=d.source.value,
                is_self_declared=d.source.is_self_declared,
                code_trust=d.contract.code_trust,
                side_effect_class=d.contract.side_effect_class,
                effect_semantics=d.contract.effect_semantics,
                provider_operation=d.contract.provider_operation,
                supported_environments=d.contract.supported_environments,
                input_schema_digest=(
                    d.contract.input_schema.digest if d.contract.input_schema else None
                ),
                output_schema_digest=(
                    d.contract.output_schema.digest if d.contract.output_schema else None
                ),
                observed_at=moment,
            )
            for d in versions
            if d.digest
        )

    def _filter(self, request: ResolutionRequest, candidates: Sequence) -> tuple:
        """Remove everything ineligible. Nothing unsafe reaches the ranker."""
        eligible: list = []
        rejected: list = []
        authorized_digest = request.authorization.capability_digest
        authorized_version = request.authorization.request.capability_ref.version

        for candidate in candidates:
            reason = self._rejection_for(
                request, candidate, authorized_digest, authorized_version
            )
            if reason is not None:
                rejected.append((candidate.reference.value, reason))
                continue

            reasons: list = []
            exact = bool(request.version and candidate.version == request.version)
            if exact:
                reasons.append("exact_version")
            if candidate.trust is TrustState.TRUSTED:
                reasons.append("trusted")
            elif candidate.trust is TrustState.VERIFIED:
                reasons.append("verified")
            tenant_local = candidate.tenant_id == request.tenant_id
            if tenant_local:
                reasons.append("tenant_local")
            if candidate.effect_semantics.is_declared:
                reasons.append("effect_declared")

            eligible.append(
                RankedCandidate(
                    candidate=candidate,
                    exact_version=exact,
                    tenant_local=tenant_local,
                    trust_rank=trust_rank_of(candidate.trust),
                    declared_effect=candidate.effect_semantics.is_declared,
                    reasons=tuple(reasons),
                )
            )

        return tuple(eligible), tuple(rejected)

    def _rejection_for(
        self,
        request: ResolutionRequest,
        candidate: CandidateSnapshot,
        authorized_digest: Optional[str],
        authorized_version,
    ) -> Optional[RejectionReason]:
        """Why this candidate cannot be used. Fail-closed throughout."""
        # -- lifecycle and trust
        if candidate.status is CapabilityStatus.REVOKED:
            return RejectionReason.REVOKED
        if candidate.trust is TrustState.QUARANTINED:
            return RejectionReason.QUARANTINED
        if request.operation.is_execution:
            if not candidate.status.permits_execution:
                return RejectionReason.NOT_ENABLED
            if not candidate.trust.permits_execution:
                return RejectionReason.TRUST_INSUFFICIENT

        # -- tenancy. A candidate belonging to another tenant is not merely
        #    unranked; it is invisible, and the caller learns only a count.
        if candidate.tenancy == "tenant" and candidate.tenant_id != request.tenant_id:
            return RejectionReason.TENANT_MISMATCH

        # -- version
        if request.version is not None and candidate.version != request.version:
            return RejectionReason.VERSION_MISMATCH

        # -- the authorization is about one exact contract
        if authorized_version is not None and candidate.version != authorized_version:
            return RejectionReason.AUTHORIZATION_MISMATCH
        if authorized_digest and candidate.digest != authorized_digest:
            return RejectionReason.DIGEST_MISMATCH

        # -- environment. A staging provider never serves a production run.
        if request.environment is not None:
            if not candidate.supported_environments:
                return RejectionReason.MISSING_CONTRACT_INFORMATION
            if request.environment not in candidate.supported_environments:
                return RejectionReason.ENVIRONMENT_MISMATCH

        # -- effect semantics. Undeclared is ineligible for execution, never
        #    merely low-ranked: missing must not be able to win.
        if request.operation.is_execution and not candidate.effect_semantics.is_declared:
            return RejectionReason.EFFECT_UNDECLARED
        if request.max_effect is not None:
            allowed = _EFFECT_STRENGTH.get(request.max_effect, 3)
            offered = _EFFECT_STRENGTH.get(candidate.effect_semantics, 3)
            if offered > allowed:
                # A caller who asked for a read must not be bound to a delete.
                return RejectionReason.EFFECT_TOO_STRONG

        # -- contract compatibility, by digest rather than by parsing schemas
        if (
            request.required_input_schema_digest
            and candidate.input_schema_digest != request.required_input_schema_digest
        ):
            return RejectionReason.CONTRACT_MISMATCH
        if (
            request.required_output_schema_digest
            and candidate.output_schema_digest != request.required_output_schema_digest
        ):
            return RejectionReason.CONTRACT_MISMATCH

        # -- provider pinning narrows only; it can never widen eligibility
        if request.pinned_provider and candidate.provider != request.pinned_provider:
            return RejectionReason.PROVIDER_NOT_PERMITTED

        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _current(self, context: Any, binding: CapabilityBinding) -> tuple:
        from backend.contexts.connectivity.application.commands import GetCapability

        try:
            found = self._registry.get(
                context,
                GetCapability(
                    capability_id=binding.capability_id.value,
                    version=binding.version.number,
                ),
            )
        except Exception:  # noqa: BLE001 - unreadable means unusable
            return (None, None, None, None)
        return (found.status, found.trust, found.digest, found.provider)

    @staticmethod
    def _metadata(context: Any, request: ResolutionRequest) -> EventMetadata:
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=request.tenant_id))
        return EventMetadata.create(
            aggregate_id=request.capability_id.value,
            aggregate_type="capability_binding",
            scope=scope,
        )

    def _refused(
        self,
        context: Any,
        request: ResolutionRequest,
        failure: ResolutionFailure,
        detail: str,
        moment: datetime,
        *,
        rejected: tuple = (),
        candidate_count: int = 0,
    ) -> ResolutionOutcome:
        result = ResolutionResult(
            request=request,
            policy_version=self.policy_version,
            resolved_at=moment,
            failure=failure,
            detail=detail,
            rejected=tuple(rejected),
            candidate_count=candidate_count,
        )
        events = (
            CapabilityResolutionRefused(
                metadata=self._metadata(context, request),
                capability_id=request.capability_id.value,
                operation=request.operation.value,
                failure=failure.value,
                detail=detail,
                policy_version=self.policy_version,
                candidate_count=candidate_count,
            ),
        )
        self._audit_fact(context, AuditEventKind.EXECUTION_REFUSED, request, result)
        return ResolutionOutcome(result, None, events)

    def _audit_fact(
        self,
        context: Any,
        kind: Any,
        request: ResolutionRequest,
        result: ResolutionResult,
        *,
        binding=None,
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=request.tenant_id))
        detail = {
            "capability_id": request.capability_id.value,
            "operation": request.operation.value,
            "authorization_digest": request.authorization.digest,
            "resolution_policy_version": self.policy_version,
            "resolved": result.resolved,
            "failure": result.failure.value if result.failure else None,
            "candidate_count": result.candidate_count,
            "rejected": [
                {"reference": ref, "reason": reason.value}
                for ref, reason in result.rejected
            ],
            "selected_provider": (
                result.selected.candidate.provider if result.selected else None
            ),
            "selected_version": (
                result.selected.candidate.version.number if result.selected else None
            ),
            "selected_digest": (
                result.selected.candidate.digest if result.selected else None
            ),
            "binding_id": binding.binding_id if binding else None,
            "binding_digest": binding.digest if binding else None,
        }
        try:
            self._audit.record(
                kind,
                scope,
                subject_reference=request.capability_id.value,
                detail=detail,
                actor=request.principal,
                payload_digest=(binding.compute_digest() if binding else None),
            )
        except Exception:  # noqa: BLE001 - audit failure never changes the outcome
            import logging

            logging.getLogger(__name__).warning(
                "capability resolution audit failed", exc_info=True
            )

    def _audit_replay(
        self, context: Any, binding: CapabilityBinding, presented_execution
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.tenant import TenantRef, TenantScope

        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=binding.tenant_id))
        try:
            self._audit.record(
                AuditEventKind.REPLAY_ATTEMPT_DETECTED,
                scope,
                subject_reference=binding.reference.value,
                detail={
                    "binding_id": binding.binding_id,
                    "bound_execution": binding.execution_id,
                    "presented_execution": presented_execution,
                },
                actor=binding.principal,
            )
        except Exception:  # noqa: BLE001
            pass
