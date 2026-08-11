"""Choosing which implementation of a capability to use.

Resolution answers a different question from authorization
------------------------------------------------------------
Authorization: *may this principal use capability X?*
Resolution:    *which eligible implementation of X should serve this request?*

The second question only arises once the first is answered yes, and answering
it must never quietly answer the first again. Nothing here grants anything: the
service consumes an ``AuthorizationDecision`` and refuses to proceed without a
live, verified one.

Filter, then rank
-------------------
Ineligible candidates are removed **before** ranking, not scored badly and hoped
about. A ranker that can see a revoked capability is a ranker that can be
written wrongly; one that never sees it cannot. Every rejection is recorded with
a reason, so "why did it not pick that one?" is answerable.

Unknown is never an advantage
-------------------------------
A candidate missing a security-relevant fact is ineligible, not merely
low-ranked. The field most often absent is the effect class, and a scoring model
that treats absence as neutral will eventually rank an undeclared destructive
tool above a declared safe one.

Ambiguity is an outcome, not a coin toss
------------------------------------------
When two candidates are genuinely equally preferred on every dimension the
platform has real data for, resolution returns ``AMBIGUOUS_RESOLUTION`` rather
than picking one. A hidden provider choice is exactly the thing this phase
exists to eliminate, and the caller can always constrain the request further.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass
from backend.contracts.identity import PrincipalRef
from backend.contexts.connectivity.domain.authorization import (
    AuthorizationDecision,
    CapabilityOperation,
)
from backend.contexts.connectivity.domain.contract import CapabilityEnvironment
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityRef,
    CapabilityVersion,
)
from backend.contexts.connectivity.domain.lifecycle import CapabilityStatus, TrustState

__all__ = [
    "VersionSelection",
    "RejectionReason",
    "ResolutionFailure",
    "CandidateSnapshot",
    "ResolutionRequest",
    "RankedCandidate",
    "ResolutionResult",
    "RESOLUTION_POLICY_VERSION",
]

#: Bumped whenever eligibility or ranking changes. Recorded on every binding so
#: a historical choice can be explained by the rules that actually made it.
RESOLUTION_POLICY_VERSION = "resolution/1"


class VersionSelection(str, Enum):
    """How a request names the version it wants."""

    EXACT = "exact"
    """One version, stated. The only mode permitted for execution, because it is
    the only one where the caller and the platform demonstrably agree on which
    contract is being run."""

    HIGHEST_AUTHORIZED = "highest_authorized"
    """The highest version this request is already authorized for. Never a
    silent upgrade: the authorization decision pins a digest, so this can only
    select the version that decision was about. Present for administrative
    reads, not for invocation."""

    @property
    def permits_execution(self) -> bool:
        return self is VersionSelection.EXACT


class RejectionReason(str, Enum):
    """Why a candidate was removed. Every rejection carries one."""

    NOT_ENABLED = "not_enabled"
    REVOKED = "revoked"
    QUARANTINED = "quarantined"
    TRUST_INSUFFICIENT = "trust_insufficient"
    TENANT_MISMATCH = "tenant_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    OPERATION_UNSUPPORTED = "operation_unsupported"
    CONTRACT_MISMATCH = "contract_mismatch"
    EFFECT_UNDECLARED = "effect_undeclared"
    EFFECT_TOO_STRONG = "effect_too_strong"
    VERSION_MISMATCH = "version_mismatch"
    DIGEST_MISMATCH = "digest_mismatch"
    AUTHORIZATION_MISMATCH = "authorization_mismatch"
    MISSING_CONTRACT_INFORMATION = "missing_contract_information"
    PROVIDER_NOT_PERMITTED = "provider_not_permitted"

    @property
    def is_security_relevant(self) -> bool:
        """Whether disclosing this to an unauthorized caller would leak.

        Tenant mismatches are the sharp case: telling somebody a candidate was
        rejected for tenancy confirms it exists.
        """
        return self in {
            RejectionReason.TENANT_MISMATCH,
            RejectionReason.TRUST_INSUFFICIENT,
            RejectionReason.QUARANTINED,
            RejectionReason.REVOKED,
        }


class ResolutionFailure(str, Enum):
    """Why resolution produced no binding."""

    CAPABILITY_NOT_FOUND = "capability_not_found"
    VERSION_NOT_FOUND = "version_not_found"
    NO_ELIGIBLE_CANDIDATE = "no_eligible_candidate"
    AUTHORIZATION_REQUIRED = "authorization_required"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    AUTHORIZATION_MISMATCH = "authorization_mismatch"
    AUTHORIZATION_UNVERIFIED = "authorization_unverified"
    AMBIGUOUS_RESOLUTION = "ambiguous_resolution"
    STALE_CANDIDATE = "stale_candidate"
    VERSION_SELECTION_NOT_PERMITTED = "version_selection_not_permitted"


@dataclass(frozen=True)
class CandidateSnapshot:
    """One capability version, frozen at read time.

    Everything ranking needs is here. Nothing is fetched during ranking — a
    ranker that could reach out would produce different answers depending on
    what it happened to reach for, and resolution has to be reproducible from
    the snapshot alone.
    """

    capability_id: CapabilityId
    version: CapabilityVersion
    digest: str
    provider: str
    status: CapabilityStatus
    trust: TrustState
    tenancy: str
    tenant_id: Optional[str]
    source: str
    is_self_declared: bool
    side_effect_class: SideEffectClass
    effect_semantics: EffectSemantics
    supported_environments: tuple = ()
    input_schema_digest: Optional[str] = None
    output_schema_digest: Optional[str] = None
    provider_operation: Optional[str] = None
    """The provider catalog operation this capability performs, from its
    contract. Carried so the binding can hand Execution the operation an
    adapter can actually look up."""
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise ContractViolation("capability_id must be a CapabilityId")
        if not self.digest:
            raise ContractViolation(
                "a candidate without a contract digest cannot be resolved; there "
                "would be nothing to bind the choice to"
            )

    @property
    def reference(self) -> CapabilityRef:
        return CapabilityRef(capability_id=self.capability_id, version=self.version)

    @property
    def is_tenant_local(self) -> bool:
        return self.tenancy == "tenant"

    def to_dict(self) -> dict:
        return {
            "reference": self.reference.value,
            "digest": self.digest,
            "provider": self.provider,
            "status": self.status.value,
            "trust": self.trust.value,
            "tenancy": self.tenancy,
            "source": self.source,
            "is_self_declared": self.is_self_declared,
            "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "supported_environments": sorted(
                e.value for e in self.supported_environments
            ),
        }


@dataclass(frozen=True)
class ResolutionRequest:
    """What is being resolved, and under what authority."""

    tenant_id: str
    principal: PrincipalRef
    capability_id: CapabilityId
    operation: CapabilityOperation
    authorization: AuthorizationDecision
    version: Optional[CapabilityVersion] = None
    version_selection: VersionSelection = VersionSelection.EXACT
    environment: Optional[CapabilityEnvironment] = None

    #: The strongest effect the caller will accept. A request that says it
    #: expects a read must not bind to something that can delete.
    max_effect: Optional[EffectSemantics] = None
    required_input_schema_digest: Optional[str] = None
    required_output_schema_digest: Optional[str] = None

    #: A provider the caller insists on. Honoured only as a *narrowing*
    #: constraint -- it can never widen what is eligible, so naming a provider
    #: cannot conjure one that policy and trust would otherwise exclude.
    pinned_provider: Optional[str] = None

    mission_id: Optional[str] = None
    workflow_id: Optional[str] = None
    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ContractViolation("tenant_id is required")
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if not isinstance(self.capability_id, CapabilityId):
            raise ContractViolation(
                "capability_id must be a CapabilityId; a provider name, URL or "
                "class name is an implementation detail, not an identity"
            )
        if not isinstance(self.authorization, AuthorizationDecision):
            raise ContractViolation(
                "resolution consumes an authorization decision; it does not grant "
                "permission and cannot proceed without one"
            )
        if (
            self.version_selection is VersionSelection.EXACT
            and self.version is None
        ):
            raise ContractViolation(
                "exact version selection requires a version; resolving without one "
                "would let the platform choose which contract to run"
            )

    @property
    def requires_execution_grade_selection(self) -> bool:
        return self.operation.is_execution

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "principal": self.principal.principal_id,
            "capability_id": self.capability_id.value,
            "operation": self.operation.value,
            "version": self.version.number if self.version else None,
            "version_selection": self.version_selection.value,
            "environment": self.environment.value if self.environment else None,
            "max_effect": self.max_effect.value if self.max_effect else None,
            "pinned_provider": self.pinned_provider,
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
        }


#: Trust ordering used by ranking. Only the two states that permit execution
#: appear -- anything else is filtered out before ranking, so a "less trusted
#: but available" candidate can never win by scoring.
_TRUST_RANK = {TrustState.TRUSTED: 2, TrustState.VERIFIED: 1}


@dataclass(frozen=True)
class RankedCandidate:
    """A candidate that survived filtering, with the reasons it scored as it did."""

    candidate: CandidateSnapshot
    exact_version: bool
    tenant_local: bool
    trust_rank: int
    declared_effect: bool
    reasons: tuple = ()

    @property
    def sort_key(self) -> tuple:
        """The whole ranking model, in one place and fully explicit.

        Higher is better; the service sorts descending on this and ascending on
        the tie-breaker. Every dimension is backed by data the registry actually
        holds -- there are no invented metrics, no weights tuned to produce a
        winner, and no latency or cost estimates the platform cannot measure.

        **Version number is deliberately absent.** Including it would make the
        higher version win every tie, and because provider is a property of a
        (capability, version) record, that would silently choose between
        *providers* -- the exact hidden selection this phase exists to remove.
        A caller who has not pinned a version and faces two equally eligible
        providers gets ``AMBIGUOUS_RESOLUTION`` and can then say which it wants.
        """
        return (
            1 if self.exact_version else 0,
            self.trust_rank,
            1 if self.tenant_local else 0,
            1 if self.declared_effect else 0,
        )

    @property
    def tie_breaker(self) -> tuple:
        """Canonical, stable, and derived from identity rather than storage order.

        Provider then digest: both are stable identifiers that mean the same
        thing in every process. Registration order and dictionary order are
        deliberately not used -- they would make the same request resolve
        differently on a different machine.
        """
        return (self.candidate.provider, self.candidate.digest)

    def to_dict(self) -> dict:
        return {
            **self.candidate.to_dict(),
            "exact_version": self.exact_version,
            "tenant_local": self.tenant_local,
            "trust_rank": self.trust_rank,
            "declared_effect": self.declared_effect,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class ResolutionResult:
    """What resolution concluded, and why.

    Carries the rejected candidates as well as the selected one. "Why did it not
    pick the other provider?" is the question an operator asks, and a result
    that cannot answer it makes provider selection feel arbitrary even when it
    is not.
    """

    request: ResolutionRequest
    policy_version: str
    resolved_at: datetime
    selected: Optional[RankedCandidate] = None
    rejected: tuple = ()
    failure: Optional[ResolutionFailure] = None
    detail: Optional[str] = None
    candidate_count: int = 0

    def __post_init__(self) -> None:
        if self.selected is None and self.failure is None:
            raise ContractViolation(
                "a resolution that selected nothing must say why; an unexplained "
                "empty result is indistinguishable from a capability that does "
                "not exist"
            )
        if self.selected is not None and self.failure is not None:
            raise ContractViolation(
                "a resolution cannot both select a candidate and report a failure"
            )

    @property
    def resolved(self) -> bool:
        return self.selected is not None

    def to_dict(self, *, include_rejections: bool = True) -> dict:
        body: dict = {
            "request": self.request.to_dict(),
            "policy_version": self.policy_version,
            "resolved_at": self.resolved_at.isoformat(),
            "resolved": self.resolved,
            "candidate_count": self.candidate_count,
            "failure": self.failure.value if self.failure else None,
            "detail": self.detail,
            "selected": self.selected.to_dict() if self.selected else None,
        }
        if include_rejections:
            body["rejected"] = [
                {"reference": ref, "reason": reason.value}
                for ref, reason in self.rejected
            ]
        return body

    def redacted(self) -> dict:
        """What an ordinary caller may see.

        Security-relevant rejections are withheld: telling a caller a candidate
        was rejected for tenancy or trust confirms it exists and describes its
        state. Only the count survives, so the resolver never becomes a provider
        inventory leak.
        """
        body = self.to_dict(include_rejections=False)
        body["rejected_count"] = len(self.rejected)
        body["rejected"] = [
            {"reference": ref, "reason": reason.value}
            for ref, reason in self.rejected
            if not reason.is_security_relevant
        ]
        return body


def trust_rank_of(trust: TrustState) -> int:
    return _TRUST_RANK.get(trust, 0)
