"""Choosing an implementation for an authorized binding. Deterministically.

What selection is allowed to be
---------------------------------
Field comparison, and nothing else. Every axis below is an exact match against a
declared value: capability reference, provider, operation, contract digest,
effect semantics, environment, tenant, interface, worker kind, protocol version.

No fuzzy matching, no embeddings, no similarity, and **no model**. A capability
is an authority; selecting the mechanism that performs it decides what
credentials are used, what network is reachable and what isolation applies, so a
selection that could be persuaded is a security boundary that can be talked past.

Why no fallback
-----------------
There is no "worker A is down, worker B will do". A different implementation can
have different credentials, different network reach, different isolation and
different side effects -- so substituting one changes what the execution *means*
while the binding, the approval and the audit trail all still say the first
thing. When the selected implementation is unusable, execution refuses, and what
happens next is a recovery decision made with the facts visible.

Why ambiguity is an answer
----------------------------
Two eligible workers is not a tie to be broken by registration order, recency,
locality, speed or cost. Each of those is a policy, and none of them has been
decided. Until one is modelled explicitly, two eligible workers is a refusal that
names both -- which is a question an operator can answer, unlike a silent
preference nobody chose.

Why the selection is re-checked before it is used
----------------------------------------------------
A selection is a record of what was true when it was made. Between selection and
invocation a worker can be disabled, quarantined or revoked. ``revalidate``
re-reads the authoritative entry and compares the implementation digest, and a
selection that no longer matches is refused -- never quietly replaced with
another worker, because that is a substitution wearing a recovery's clothes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Sequence

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.errors import ExecutionError
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_directory import (
    WORKER_PROTOCOL_VERSION,
    WorkerEntry,
    WorkerInterface,
)
from backend.platform.hashing import compute_digest

__all__ = [
    "WorkerRefusal",
    "WorkerSelectionRequest",
    "WorkerSelection",
    "WorkerSelectionRefused",
    "CandidateAssessment",
    "SELECTION_POLICY_VERSION",
    "SELECTION_ARTIFACT_KIND",
    "DEFAULT_SELECTION_TTL_SECONDS",
    "incompatibilities",
    "select_worker",
]

SELECTION_ARTIFACT_KIND = "cortexprime.execution.worker_selection"

SELECTION_POLICY_VERSION = "worker-selection/1"
"""Recorded on every selection. When the rules below change this changes, so a
past selection can be read against the policy that actually produced it rather
than against whatever the code says today."""

DEFAULT_SELECTION_TTL_SECONDS = 300
"""A selection is short-lived on purpose. It is not a grant; it is a note about
what was true a moment ago, and the authoritative re-read at invocation is what
actually decides."""


class WorkerRefusal(str, Enum):
    """Why a worker may not perform a binding.

    One value per distinct cause. Collapsing these into ``worker_not_found``
    would make "nobody registered one", "it is quarantined" and "it is registered
    for staging" indistinguishable during an incident, and those have three
    different fixes.
    """

    # -- the directory ---------------------------------------------------
    NOT_REGISTERED = "worker_not_registered"
    NOT_VALIDATED = "worker_not_validated"
    NOT_ENABLED = "worker_not_enabled"
    DISABLED = "worker_disabled"
    REVOKED = "worker_revoked"

    # -- trust ------------------------------------------------------------
    UNVERIFIED = "worker_unverified"
    QUARANTINED = "worker_quarantined"
    UNTRUSTED = "worker_untrusted"

    # -- availability ------------------------------------------------------
    UNAVAILABLE = "worker_unavailable"
    UNHEALTHY = "worker_unhealthy"
    DRAINING = "worker_draining"

    # -- compatibility ------------------------------------------------------
    KIND_MISMATCH = "worker_kind_mismatch"
    INTERFACE_MISMATCH = "worker_interface_mismatch"
    PROTOCOL_UNSUPPORTED = "worker_protocol_unsupported"
    PROVIDER_UNSUPPORTED = "provider_unsupported"
    CAPABILITY_UNSUPPORTED = "capability_unsupported"
    OPERATION_UNSUPPORTED = "operation_unsupported"
    CONTRACT_DIGEST_UNSUPPORTED = "contract_digest_unsupported"
    EFFECT_UNSUPPORTED = "effect_semantics_unsupported"
    ISOLATION_INSUFFICIENT = "isolation_insufficient"
    ENVIRONMENT_UNSUPPORTED = "environment_unsupported"
    ENVIRONMENT_UNKNOWN = "environment_unknown"
    TENANT_MISMATCH = "tenant_mismatch"

    # -- selection ----------------------------------------------------------
    NONE_ELIGIBLE = "no_eligible_worker"
    AMBIGUOUS = "ambiguous_worker_selection"
    DIGEST_CHANGED = "worker_digest_changed"
    SELECTION_EXPIRED = "worker_selection_expired"
    SELECTION_MISMATCH = "worker_selection_mismatch"


@dataclass(frozen=True)
class WorkerSelectionRequest:
    """Everything selection compares against. All of it explicit."""

    worker_kind: WorkerKind
    binding: BoundCapability
    tenant_id: str
    environment: Optional[ExecutionEnvironment] = None
    """Taken from the binding when it carries one. Absent means every candidate
    is refused -- see ``ENVIRONMENT_UNKNOWN``. There is no wildcard."""

    interface: Optional[WorkerInterface] = None
    protocol_version: str = WORKER_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.binding, BoundCapability):
            raise ContractViolation("binding must be a BoundCapability")
        if self.tenant_id != self.binding.tenant_id:
            raise ContractViolation(
                "the selection tenant and the binding tenant disagree; one of them "
                "is somebody else's, and guessing which would be the whole breach"
            )
        if self.environment is not None and not isinstance(
            self.environment, ExecutionEnvironment
        ):
            raise ContractViolation("environment must be an ExecutionEnvironment")
        if self.interface is not None and not isinstance(self.interface, WorkerInterface):
            raise ContractViolation("interface must be a WorkerInterface")

    @classmethod
    def for_binding(
        cls,
        *,
        worker_kind: WorkerKind,
        binding: BoundCapability,
        protocol_version: str = WORKER_PROTOCOL_VERSION,
    ) -> "WorkerSelectionRequest":
        """Derive the request from the binding, adding nothing.

        The interface and environment come from the binding or they are absent.
        Nothing is defaulted: a default here would be this layer deciding
        something Connectivity was supposed to have decided.
        """
        interface: Optional[WorkerInterface] = None
        if binding.interface:
            try:
                interface = WorkerInterface(binding.interface)
            except ValueError:
                # An interface this platform has no adapter shape for. Left as
                # None would read as "unconstrained"; it is the opposite, so the
                # mismatch is surfaced by refusing every candidate below.
                interface = None
        return cls(
            worker_kind=worker_kind,
            binding=binding,
            tenant_id=binding.tenant_id,
            environment=binding.environment,
            interface=interface,
            protocol_version=protocol_version,
        )

    @property
    def interface_is_unrecognised(self) -> bool:
        return bool(self.binding.interface) and self.interface is None


@dataclass(frozen=True)
class CandidateAssessment:
    """One worker, and every reason it was not chosen. Never just the first."""

    worker_id: str
    worker_digest: str
    refusals: tuple = ()

    @property
    def eligible(self) -> bool:
        return not self.refusals

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "worker_digest": self.worker_digest,
            "refusals": [r.value for r in self.refusals],
        }


class WorkerSelectionRefused(ExecutionError):
    """No worker was selected, and execution stops here.

    Carries every candidate's assessment rather than a summary. An operator who
    is told "no eligible worker" and nothing else has to go and reconstruct why
    each of four registrations was passed over.
    """

    def __init__(
        self,
        *,
        worker_kind: WorkerKind,
        capability_ref: str,
        refusals: Sequence[WorkerRefusal],
        candidates: Sequence[CandidateAssessment] = (),
    ) -> None:
        listed = ", ".join(r.value for r in refusals) or "unspecified"
        super().__init__(
            f"no worker was selected for {capability_ref} ({worker_kind.value}): "
            f"{listed}. Execution does not substitute an implementation -- a "
            "different one can have different credentials, isolation and effects, "
            "so running it would change what the approved binding meant"
        )
        self.worker_kind = worker_kind
        self.capability_ref = capability_ref
        self.refusals = tuple(refusals)
        self.candidates = tuple(candidates)

    @property
    def is_ambiguous(self) -> bool:
        return WorkerRefusal.AMBIGUOUS in self.refusals

    def to_dict(self) -> dict:
        return {
            "worker_kind": self.worker_kind.value,
            "capability_ref": self.capability_ref,
            "refusals": [r.value for r in self.refusals],
            "ambiguous": self.is_ambiguous,
            "candidates": [c.to_dict() for c in self.candidates],
        }


# ----------------------------------------------------------------------
# Compatibility
# ----------------------------------------------------------------------


def incompatibilities(
    entry: WorkerEntry, request: WorkerSelectionRequest
) -> tuple:
    """Every reason this worker may not perform this binding.

    Returns all of them rather than the first: an operator who fixes one and
    rediscovers the next has been told half the truth twice.

    Reads only declared values on both sides. Nothing here consults a registry,
    an authorization engine or a resolver -- by the time a binding reaches this
    function those questions are answered, and asking them again would create a
    second place where the answer could differ.
    """
    binding = request.binding
    implementation = entry.implementation
    reasons: list = []

    # -- governed state -------------------------------------------------
    if entry.lifecycle.is_terminal:
        reasons.append(WorkerRefusal.REVOKED)
    elif not entry.lifecycle.permits_execution:
        reasons.append(
            {
                "registered": WorkerRefusal.NOT_VALIDATED,
                "validated": WorkerRefusal.NOT_ENABLED,
                "disabled": WorkerRefusal.DISABLED,
            }.get(entry.lifecycle.value, WorkerRefusal.NOT_ENABLED)
        )

    if not entry.trust.permits_execution:
        reasons.append(
            {
                "unverified": WorkerRefusal.UNVERIFIED,
                "quarantined": WorkerRefusal.QUARANTINED,
                "untrusted": WorkerRefusal.UNTRUSTED,
            }.get(entry.trust.value, WorkerRefusal.UNTRUSTED)
        )

    if not entry.availability.accepts_work:
        reasons.append(
            {
                "unavailable": WorkerRefusal.UNAVAILABLE,
                "unhealthy": WorkerRefusal.UNHEALTHY,
                "draining": WorkerRefusal.DRAINING,
            }.get(entry.availability.value, WorkerRefusal.UNAVAILABLE)
        )

    # -- tenancy ---------------------------------------------------------
    if not implementation.visible_to(request.tenant_id):
        # Not "this tenant has no worker" -- this worker belongs to another
        # tenant, and offering it here would cross the boundary that matters most.
        reasons.append(WorkerRefusal.TENANT_MISMATCH)

    # -- mechanism -------------------------------------------------------
    if implementation.worker_kind is not request.worker_kind:
        reasons.append(WorkerRefusal.KIND_MISMATCH)
    if implementation.protocol_version != request.protocol_version:
        reasons.append(WorkerRefusal.PROTOCOL_UNSUPPORTED)
    if request.interface_is_unrecognised or (
        request.interface is not None and implementation.interface is not request.interface
    ):
        reasons.append(WorkerRefusal.INTERFACE_MISMATCH)

    # -- what was bound ---------------------------------------------------
    if binding.provider not in implementation.supported_providers:
        reasons.append(WorkerRefusal.PROVIDER_UNSUPPORTED)
    if (
        implementation.supported_capability_refs
        and binding.capability_ref not in implementation.supported_capability_refs
    ):
        reasons.append(WorkerRefusal.CAPABILITY_UNSUPPORTED)
    if (
        implementation.supported_operations
        and binding.operation not in implementation.supported_operations
    ):
        reasons.append(WorkerRefusal.OPERATION_UNSUPPORTED)
    if (
        implementation.pinned_capability_digests
        and binding.capability_digest not in implementation.pinned_capability_digests
    ):
        # The adapter was built against a contract shape that has since been
        # republished. It may still work; it was never checked against this.
        reasons.append(WorkerRefusal.CONTRACT_DIGEST_UNSUPPORTED)

    # -- effects and isolation ---------------------------------------------
    if binding.effect_semantics not in implementation.supported_effects:
        reasons.append(WorkerRefusal.EFFECT_UNSUPPORTED)
    if not implementation.permits(binding.code_trust, binding.side_effect_class):
        reasons.append(WorkerRefusal.ISOLATION_INSUFFICIENT)

    # -- environment --------------------------------------------------------
    if request.environment is None:
        # Absence is never "anywhere". A binding that does not say where it is to
        # be performed cannot be matched against a worker that says where it may.
        reasons.append(WorkerRefusal.ENVIRONMENT_UNKNOWN)
    elif request.environment not in implementation.supported_environments:
        reasons.append(WorkerRefusal.ENVIRONMENT_UNSUPPORTED)

    return tuple(reasons)


# ----------------------------------------------------------------------
# The selection
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class WorkerSelection:
    """Which implementation was chosen, and what it was chosen for.

    Immutable and digest-bound. There is no ``rebind``, no ``reselect`` and no
    corresponding event, because a selection that could be changed would let the
    thing that runs differ from the thing that was selected with the same
    selection id vouching for both.
    """

    selection_id: str
    worker_id: str
    worker_kind: WorkerKind
    worker_version: str
    worker_digest: str

    binding_id: str
    binding_digest: str
    capability_digest: str
    capability_ref: str
    provider: str
    operation: str

    tenant_id: str
    principal_id: str
    environment: ExecutionEnvironment
    interface: WorkerInterface

    selected_at: datetime
    expires_at: datetime
    policy_version: str = SELECTION_POLICY_VERSION
    reasons: tuple = ()
    """Machine-readable facts about why this worker was eligible. Never
    narrative, and never a model's explanation."""

    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    digest: Optional[str] = None

    def __post_init__(self) -> None:
        for label in (
            "selection_id",
            "worker_id",
            "worker_version",
            "worker_digest",
            "binding_id",
            "binding_digest",
            "capability_digest",
            "capability_ref",
            "provider",
            "operation",
            "tenant_id",
            "principal_id",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a selection missing it cannot "
                    "be checked, and an uncheckable selection is not a record"
                )
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation("environment must be an ExecutionEnvironment")
        if not isinstance(self.interface, WorkerInterface):
            raise ContractViolation("interface must be a WorkerInterface")
        for label in ("selected_at", "expires_at"):
            if getattr(self, label).tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")
        if self.expires_at <= self.selected_at:
            raise ContractViolation(
                "a selection must expire after it is made; one that never expires "
                "is a standing claim that a worker was fit, made once"
            )

    # -- digest ----------------------------------------------------------

    def digest_payload(self) -> dict:
        return {
            "artifact_kind": SELECTION_ARTIFACT_KIND,
            "selection_id": self.selection_id,
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind.value,
            "worker_version": self.worker_version,
            "worker_digest": self.worker_digest,
            "binding_id": self.binding_id,
            "binding_digest": self.binding_digest,
            "capability_digest": self.capability_digest,
            "capability_ref": self.capability_ref,
            "provider": self.provider,
            "operation": self.operation,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "environment": self.environment.value,
            "interface": self.interface.value,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "policy_version": self.policy_version,
            "selected_at": self.selected_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    def sealed(self) -> "WorkerSelection":
        from dataclasses import replace

        return replace(self, digest=compute_digest(self.digest_payload()).value)

    # -- queries -----------------------------------------------------------

    def is_live_at(self, moment: datetime) -> bool:
        return moment < self.expires_at

    def revalidate(
        self,
        entry: Optional[WorkerEntry],
        *,
        binding: Optional[BoundCapability] = None,
        now: Optional[datetime] = None,
    ) -> tuple:
        """Re-check against the authoritative record. The TOCTOU close.

        A worker that was enabled and trusted when it was selected may have been
        disabled, quarantined or revoked since. This is read immediately before
        invocation, against a freshly read entry -- never against the entry the
        selection was made from, which is a memory of a state, not the state.

        Returns refusals; empty means the selection still holds. A non-empty
        answer stops execution. It never nominates a replacement.
        """
        moment = now or datetime.now(timezone.utc)
        reasons: list = []

        if not self.is_live_at(moment):
            reasons.append(WorkerRefusal.SELECTION_EXPIRED)

        if entry is None:
            # Deregistered between selection and invocation.
            reasons.append(WorkerRefusal.NOT_REGISTERED)
            return tuple(reasons)

        if entry.worker_id != self.worker_id:
            reasons.append(WorkerRefusal.SELECTION_MISMATCH)
        if entry.worker_digest != self.worker_digest:
            # Same id, different implementation. The most dangerous shape this
            # can take: the audit trail would name the worker that was chosen
            # while a different build performed the work.
            reasons.append(WorkerRefusal.DIGEST_CHANGED)

        if entry.lifecycle.is_terminal:
            reasons.append(WorkerRefusal.REVOKED)
        elif not entry.lifecycle.permits_execution:
            reasons.append(
                WorkerRefusal.DISABLED
                if entry.lifecycle.value == "disabled"
                else WorkerRefusal.NOT_ENABLED
            )
        if not entry.trust.permits_execution:
            reasons.append(
                WorkerRefusal.QUARANTINED
                if entry.trust.value == "quarantined"
                else WorkerRefusal.UNTRUSTED
            )
        if not entry.availability.accepts_work:
            reasons.append(
                WorkerRefusal.DRAINING
                if entry.availability.value == "draining"
                else WorkerRefusal.UNAVAILABLE
            )

        if binding is not None:
            if binding.binding_id != self.binding_id:
                reasons.append(WorkerRefusal.SELECTION_MISMATCH)
            elif binding.binding_digest != self.binding_digest:
                reasons.append(WorkerRefusal.SELECTION_MISMATCH)

        return tuple(reasons)

    def to_dict(self) -> dict:
        return {
            **self.digest_payload(),
            "reasons": list(self.reasons),
            "digest": self.digest,
        }


def select_worker(
    candidates: Sequence[WorkerEntry],
    request: WorkerSelectionRequest,
    *,
    selection_id: str,
    ttl_seconds: int = DEFAULT_SELECTION_TTL_SECONDS,
    now: Optional[datetime] = None,
) -> WorkerSelection:
    """The one eligible worker, or a refusal saying why there isn't one.

    Every candidate is assessed in full before anything is chosen, so a refusal
    can say what was wrong with each. Exactly one eligible candidate is a
    selection; zero and two-or-more are both refusals.

    Two-or-more is deliberately not resolved. Preferring the first registered,
    the newest, the local one, the faster one or the cheaper one are five
    different policies and none has been decided -- so the ambiguity is returned
    for somebody to settle rather than silently settled here.
    """
    moment = now or datetime.now(timezone.utc)
    if ttl_seconds < 1:
        raise ContractViolation("a selection must be live for at least a second")

    assessments = tuple(
        CandidateAssessment(
            worker_id=entry.worker_id,
            worker_digest=entry.worker_digest,
            refusals=incompatibilities(entry, request),
        )
        for entry in candidates
    )
    eligible = [
        entry
        for entry, assessment in zip(candidates, assessments)
        if assessment.eligible
    ]

    if not eligible:
        # Every distinct reason seen across the candidates, so the refusal names
        # the actual obstacles instead of "none matched".
        seen: list = []
        for assessment in assessments:
            for refusal in assessment.refusals:
                if refusal not in seen:
                    seen.append(refusal)
        raise WorkerSelectionRefused(
            worker_kind=request.worker_kind,
            capability_ref=request.binding.capability_ref,
            refusals=tuple(seen) or (WorkerRefusal.NONE_ELIGIBLE,),
            candidates=assessments,
        )

    if len(eligible) > 1:
        raise WorkerSelectionRefused(
            worker_kind=request.worker_kind,
            capability_ref=request.binding.capability_ref,
            refusals=(WorkerRefusal.AMBIGUOUS,),
            candidates=tuple(
                a for a in assessments if a.worker_id in {e.worker_id for e in eligible}
            ),
        )

    chosen = eligible[0]
    binding = request.binding
    assert request.environment is not None  # an absent one refuses above
    interface = request.interface or chosen.implementation.interface
    return WorkerSelection(
        selection_id=selection_id,
        worker_id=chosen.worker_id,
        worker_kind=chosen.worker_kind,
        worker_version=chosen.worker_version,
        worker_digest=chosen.worker_digest,
        binding_id=binding.binding_id,
        binding_digest=binding.binding_digest,
        capability_digest=binding.capability_digest,
        capability_ref=binding.capability_ref,
        provider=binding.provider,
        operation=binding.operation,
        tenant_id=binding.tenant_id,
        principal_id=binding.principal_id,
        environment=request.environment,
        interface=interface,
        selected_at=moment,
        expires_at=moment + timedelta(seconds=ttl_seconds),
        policy_version=SELECTION_POLICY_VERSION,
        reasons=(
            "sole_eligible_candidate",
            f"candidates_assessed={len(assessments)}",
            f"kind={request.worker_kind.value}",
            f"provider={binding.provider}",
            f"environment={request.environment.value}",
            f"scope={chosen.implementation.scope.value}",
        ),
        execution_id=binding.execution_id,
        node_id=binding.node_id,
    ).sealed()
