"""The frozen choice: one capability, one version, one provider, one execution.

What a binding is
-------------------
The record that *this exact contract, from this exact provider, was chosen for
this exact execution under this exact authorization*. It is the artifact Phase
3.3 will consume, and the reason a worker can be handed something specific
rather than a name to look up again.

What a binding is not
-----------------------
**Permanent authority.** A binding proves identity continuity — that what runs
is what was chosen and authorized. It does not prove the world has not changed
since. `assert_usable` re-checks against the authoritative record at the point
of execution, which is where the TOCTOU window actually closes.

Immutable, and structurally so
--------------------------------
There is no ``update``, no ``rebind``, and no ``change_provider``. Not because
they are discouraged — because they do not exist. A binding whose provider could
be changed would let the thing that runs differ from the thing that was
authorized, with the same binding id vouching for both.

If a different provider is needed, that is a new resolution, a new authorization
if the digest differs, and a new binding. The old one stays exactly as it was,
because it is the record of a decision that was really made.

Replay is bounded by construction
-----------------------------------
The binding key includes the execution it was made for. A binding presented
against a different execution fails ``authorizes`` — it is not a bearer token
that happens to name an execution, it is a record that only matches one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.approval import PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.connector import CodeTrust
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.identity import PrincipalRef
from backend.contexts.connectivity.domain.authorization import CapabilityOperation
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityRef,
    CapabilityVersion,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState
from backend.platform.hashing import compute_digest, digests_match
from backend.platform.identity import monotonic_ulid

__all__ = [
    "BindingInvalidation",
    "BindingUnusable",
    "CapabilityBinding",
    "BINDING_ARTIFACT_KIND",
    "GOVERNED_BINDING_FIELDS",
]

BINDING_ARTIFACT_KIND = "cortexprime.connectivity.capability_binding"

#: What the binding digest covers. Provenance and counts are excluded: they
#: explain the choice, they are not the choice, and a digest that changed when
#: a rejection note was reworded would stop answering "is this the binding that
#: was made".
GOVERNED_BINDING_FIELDS = (
    "binding_id",
    "tenant_id",
    "principal_id",
    "capability_ref",
    "capability_digest",
    "provider",
    "operation",
    "authorization_digest",
    "execution_ref",
)


class BindingInvalidation(str, Enum):
    """Why a binding may no longer be used."""

    EXPIRED = "binding_expired"
    CAPABILITY_REVOKED = "capability_revoked"
    CAPABILITY_NOT_ENABLED = "capability_not_enabled"
    TRUST_DOWNGRADED = "trust_downgraded"
    DIGEST_CHANGED = "digest_changed"
    PROVIDER_CHANGED = "provider_changed"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    BINDING_MISMATCH = "binding_mismatch"
    TAMPERED = "tampered"


class BindingUnusable(ContractViolation):
    """A binding was presented and may not be used."""

    def __init__(self, binding_id: str, *reasons: BindingInvalidation) -> None:
        listed = ", ".join(r.value for r in reasons) or "unknown"
        super().__init__(
            f"binding {binding_id} may not be used: {listed}. Resolution does not "
            "silently re-resolve -- a new binding requires a new decision"
        )
        self.binding_id = binding_id
        self.reasons = tuple(reasons)


@dataclass(frozen=True)
class CapabilityBinding:
    """One frozen capability choice. Immutable and digest-bound."""

    binding_id: str
    tenant_id: str
    principal: PrincipalRef
    capability_id: CapabilityId
    version: CapabilityVersion
    capability_digest: str
    provider: str
    operation: CapabilityOperation

    authorization_digest: str
    authorization_policy_version: str
    resolution_policy_version: str

    resolved_at: datetime
    expires_at: datetime

    #: The declared effect at the moment of binding. Carried so the execution
    #: boundary can refuse a capability whose declaration changed without having
    #: to reason about what it used to say.
    code_trust: Optional[CodeTrust] = None
    """Which class of computation the bound capability performs (ADR-088).

    Projected into Execution beside the effect class, because worker selection
    needs both: the effect says what it does to the world, and this says what
    the code could do if it were something other than declared. Optional in the
    type and mandatory in practice -- ``project_binding`` refuses without it."""

    side_effect_class: Optional[SideEffectClass] = None
    effect_semantics: Optional[EffectSemantics] = None

    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: Optional[str] = None

    #: Why this candidate and not the others. Machine-readable facts only --
    #: never narrative, never reasoning traces.
    selection_reasons: tuple = ()
    rejected_candidates: tuple = ()
    candidate_count: int = 0

    provider_operation: Optional[str] = None
    """The provider catalog operation, copied from the capability contract.

    Distinct from ``operation``, which is the governance verb. Execution
    reads this to select a worker and to validate input against the
    provider's declared contract; ``None`` falls back to the verb, which
    refuses at selection for any adapter with a declared catalog.
    """

    digest: Optional[str] = None

    def __post_init__(self) -> None:
        for label in (
            "binding_id",
            "tenant_id",
            "capability_digest",
            "provider",
            "authorization_digest",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if not isinstance(self.operation, CapabilityOperation):
            raise ContractViolation("operation must be a CapabilityOperation")
        if self.expires_at <= self.resolved_at:
            raise ContractViolation(
                "a binding must expire after it is made; one that never expires is "
                "a standing grant to run a specific thing forever"
            )
        if self.operation.is_execution and not self.execution_id:
            raise ContractViolation(
                "a binding for execution must name the execution it is for; without "
                "it the binding is replayable against any run"
            )

    # ------------------------------------------------------------------
    # Identity and binding
    # ------------------------------------------------------------------

    @property
    def reference(self) -> CapabilityRef:
        return CapabilityRef(capability_id=self.capability_id, version=self.version)

    @property
    def binding_key(self) -> str:
        """What this binding matches, and nothing else."""
        return "|".join(
            [
                self.tenant_id,
                self.principal.principal_id,
                self.reference.value,
                self.operation.value,
                self.execution_id or "-",
                self.node_id or "-",
                self.workflow_id or "-",
                self.mission_id or "-",
            ]
        )

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def matches_execution(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        execution_id: Optional[str],
        node_id: Optional[str] = None,
    ) -> bool:
        """Whether this binding is the one for that run."""
        return (
            self.tenant_id == tenant_id
            and self.principal.principal_id == principal_id
            and (self.execution_id or None) == (execution_id or None)
            and (self.node_id or None) == (node_id or None)
        )

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict:
        return {
            "artifact_kind": BINDING_ARTIFACT_KIND,
            "binding_id": self.binding_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal.principal_id,
            "capability_ref": self.reference.value,
            "capability_digest": self.capability_digest,
            "provider": self.provider,
            "operation": self.operation.value,
            "provider_operation": self.provider_operation,
            "authorization_digest": self.authorization_digest,
            "authorization_policy_version": self.authorization_policy_version,
            "resolution_policy_version": self.resolution_policy_version,
            "binding_key": self.binding_key,
            "resolved_at": self.resolved_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def compute_digest(self) -> PayloadDigest:
        return compute_digest(self.digest_payload())

    def sealed(self) -> "CapabilityBinding":
        from dataclasses import replace

        return replace(self, digest=self.compute_digest().value)

    def verify_digest(self) -> None:
        if not self.digest:
            raise BindingUnusable(self.binding_id, BindingInvalidation.TAMPERED)
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise BindingUnusable(self.binding_id, BindingInvalidation.TAMPERED)

    # ------------------------------------------------------------------
    # The execution boundary
    # ------------------------------------------------------------------

    def invalidations_against(
        self,
        *,
        current_status: Optional[CapabilityStatus],
        current_trust: Optional[TrustState],
        current_digest: Optional[str],
        current_provider: Optional[str],
        authorization_live: bool,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Everything wrong with using this binding right now.

        Returns every reason rather than the first, so an operator sees the whole
        picture instead of fixing one and rediscovering the next. Absence of a
        current record is itself an invalidation -- a capability that can no
        longer be read is not one to run.
        """
        moment = now or datetime.now(timezone.utc)
        reasons: list = []

        if not self.is_live_at(moment):
            reasons.append(BindingInvalidation.EXPIRED)
        if not authorization_live:
            reasons.append(BindingInvalidation.AUTHORIZATION_EXPIRED)

        if current_status is None or current_digest is None:
            reasons.append(BindingInvalidation.CAPABILITY_REVOKED)
            return tuple(reasons)

        if current_status is CapabilityStatus.REVOKED:
            reasons.append(BindingInvalidation.CAPABILITY_REVOKED)
        elif not current_status.permits_execution:
            reasons.append(BindingInvalidation.CAPABILITY_NOT_ENABLED)

        if current_trust is None or not current_trust.permits_execution:
            reasons.append(BindingInvalidation.TRUST_DOWNGRADED)

        if current_digest != self.capability_digest:
            # The contract was republished. The binding names a contract that is
            # no longer what that version says, so it names nothing runnable.
            reasons.append(BindingInvalidation.DIGEST_CHANGED)

        if current_provider is not None and current_provider != self.provider:
            reasons.append(BindingInvalidation.PROVIDER_CHANGED)

        return tuple(reasons)

    def assert_usable(
        self,
        *,
        current_status: Optional[CapabilityStatus],
        current_trust: Optional[TrustState],
        current_digest: Optional[str],
        current_provider: Optional[str] = None,
        authorization_live: bool = True,
        now: Optional[datetime] = None,
    ) -> None:
        """Fail closed. Called at the execution boundary, never at binding time."""
        self.verify_digest()
        reasons = self.invalidations_against(
            current_status=current_status,
            current_trust=current_trust,
            current_digest=current_digest,
            current_provider=current_provider,
            authorization_live=authorization_live,
            now=now,
        )
        if reasons:
            raise BindingUnusable(self.binding_id, *reasons)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        principal: PrincipalRef,
        candidate,
        operation: CapabilityOperation,
        authorization_digest: str,
        authorization_policy_version: str,
        resolution_policy_version: str,
        expires_at: datetime,
        selection_reasons: tuple = (),
        rejected_candidates: tuple = (),
        candidate_count: int = 0,
        mission_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        node_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> "CapabilityBinding":
        moment = now or datetime.now(timezone.utc)
        return cls(
            binding_id=monotonic_ulid(),
            tenant_id=tenant_id,
            principal=principal,
            capability_id=candidate.capability_id,
            version=candidate.version,
            capability_digest=candidate.digest,
            provider=candidate.provider,
            operation=operation,
            provider_operation=getattr(candidate, "provider_operation", None),
            authorization_digest=authorization_digest,
            authorization_policy_version=authorization_policy_version,
            resolution_policy_version=resolution_policy_version,
            resolved_at=moment,
            expires_at=expires_at,
            code_trust=getattr(candidate, "code_trust", None),
            side_effect_class=candidate.side_effect_class,
            effect_semantics=candidate.effect_semantics,
            mission_id=mission_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            node_id=node_id,
            selection_reasons=tuple(selection_reasons),
            rejected_candidates=tuple(rejected_candidates),
            candidate_count=candidate_count,
        ).sealed()

    def to_dict(self) -> dict:
        return {
            **self.digest_payload(),
            "side_effect_class": (
                self.side_effect_class.value if self.side_effect_class else None
            ),
            "effect_semantics": (
                self.effect_semantics.value if self.effect_semantics else None
            ),
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "selection_reasons": list(self.selection_reasons),
            "rejected_candidates": [
                {"reference": ref, "reason": reason}
                for ref, reason in self.rejected_candidates
            ],
            "candidate_count": self.candidate_count,
            "digest": self.digest,
        }
