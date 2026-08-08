"""A capability candidate: something a source *claims* it can do.

Candidate is not definition
-----------------------------
A ``CapabilityDefinition`` is what CortexPrime asserts about an ability. A
``CapabilityCandidate`` is what somebody else told us. Keeping them as separate
types is the whole design: if discovery produced definitions directly, then
"an MCP server said so" and "the platform vouches for this" would be the same
object, and nothing downstream could tell them apart.

Everything on a candidate is a claim, including the parts that sound
authoritative. A source saying ``"provider": "github"`` does not make it GitHub.

Two fingerprints, deliberately
--------------------------------
``observation_digest`` covers *what the source said, as it said it* -- including
the description text and the raw schema. It answers "has this source changed
what it is telling us since last time", which is a drift question.

``contract_digest`` is computed by the **registry** over the normalised,
authoritative contract, and is the security binding. It excludes description
text, because a capability whose digest changed when somebody fixed a typo would
make "is this what was approved?" unanswerable.

They are different questions and must not share an answer. A source can rewrite
its description every hour without the contract changing, and a source can keep
its description identical while changing the effect class -- the second is the
dangerous one, and only the contract digest catches it.

Completeness
--------------
A candidate that is missing information the registry requires is ``INCOMPLETE``
and cannot be ingested. This is a real and common case: MCP servers frequently
publish tools with no output schema and nothing that says whether the tool
mutates anything. The correct response is to hold an incomplete candidate and
say what is missing -- never to invent the missing facts, because the field most
often absent is the effect class, and guessing that is how a destructive tool
gets registered as a read.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contexts.connectivity.domain.contract import CapabilityContract
from backend.contexts.connectivity.domain.definition import CapabilitySource
from backend.contexts.connectivity.domain.endpoint import DiscoveryEndpoint
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityRef,
    CapabilityVersion,
)
from backend.platform.hashing import compute_digest

__all__ = [
    "CandidateStatus",
    "SourceRef",
    "CapabilityCandidate",
]


class CandidateStatus(str, Enum):
    """How usable a candidate is, before anything is registered."""

    COMPLETE = "complete"
    """Everything the registry requires is present. May be ingested."""

    INCOMPLETE = "incomplete"
    """Structurally valid, but missing facts the registry requires. Held, not
    ingested, and it says which facts are missing. Never filled in by guesswork."""

    REJECTED = "rejected"
    """Structurally unusable -- an unparseable identity, a schema past the depth
    budget, metadata that is not what it claims to be."""

    @property
    def may_be_ingested(self) -> bool:
        return self is CandidateStatus.COMPLETE


@dataclass(frozen=True)
class SourceRef:
    """Which source made this claim."""

    source_id: str
    source_type: CapabilitySource
    endpoint: Optional[DiscoveryEndpoint] = None
    server_name: Optional[str] = None
    """For MCP: the server exposing the tool.

    A server is a *provider*; a tool is the capability. Collapsing the two would
    make one unreachable server look like one broken capability, when it is
    actually every capability that server exposes.
    """

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ContractViolation("source_id must be non-blank text")
        if not isinstance(self.source_type, CapabilitySource):
            raise ContractViolation("source_type must be a CapabilitySource")

    @property
    def is_self_declared(self) -> bool:
        """Whether the thing being described is what described it."""
        return self.source_type.is_self_declared

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "endpoint": self.endpoint.to_dict() if self.endpoint else None,
            "server_name": self.server_name,
            "is_self_declared": self.is_self_declared,
        }


@dataclass(frozen=True)
class CapabilityCandidate:
    """One observed claim that some ability exists."""

    candidate_id: str
    capability_id: CapabilityId
    version: CapabilityVersion
    name: str
    description: str
    provider: str

    source: SourceRef
    status: CandidateStatus

    contract: Optional[CapabilityContract] = None
    """Present only when the observation carried everything required. A candidate
    with no contract cannot be registered, and that is the point."""

    missing: tuple = ()
    """Exactly what the source failed to provide. The operator-facing half of
    INCOMPLETE, and the reason nothing is guessed."""

    rejections: tuple = ()
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)
    """What the source actually said, kept for audit. Never interpreted, never
    executed, never passed to a model."""

    claims: Mapping[str, Any] = field(default_factory=dict)
    """Assertions the source made about itself -- 'official', 'verified',
    'internal'. Preserved as claims and deliberately never read as trust."""

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise ContractViolation("capability_id must be a CapabilityId")
        if not isinstance(self.version, CapabilityVersion):
            raise ContractViolation("version must be a CapabilityVersion")
        if not isinstance(self.source, SourceRef):
            raise ContractViolation("source must be a SourceRef")
        if not isinstance(self.status, CandidateStatus):
            raise ContractViolation("status must be a CandidateStatus")
        if self.observed_at.tzinfo is None:
            raise ContractViolation("observed_at must be timezone-aware")

        if self.status is CandidateStatus.COMPLETE and self.contract is None:
            raise ContractViolation(
                "a complete candidate must carry a contract; one without is "
                "missing exactly the part the registry needs, and calling it "
                "complete would let it be ingested"
            )
        if self.status is CandidateStatus.INCOMPLETE and not self.missing:
            raise ContractViolation(
                "an incomplete candidate must say what is missing; otherwise "
                "nobody can supply it and the candidate is stuck for reasons "
                "nobody can read"
            )
        if self.status is CandidateStatus.REJECTED and not self.rejections:
            raise ContractViolation("a rejected candidate must say why")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def reference(self) -> CapabilityRef:
        return CapabilityRef(capability_id=self.capability_id, version=self.version)

    @property
    def may_be_ingested(self) -> bool:
        return self.status.may_be_ingested

    @property
    def is_self_declared(self) -> bool:
        return self.source.is_self_declared

    def observation_payload(self) -> dict:
        """What the source said, canonically ordered.

        Includes the description and the raw metadata on purpose: this
        fingerprint exists to detect a source changing its story, and a source
        that rewrites every description while keeping its contracts identical
        has changed its story.
        """
        return {
            "capability_id": self.capability_id.value,
            "version": self.version.number,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "source_id": self.source.source_id,
            "source_type": self.source.source_type.value,
            "server_name": self.source.server_name,
            "endpoint": self.source.endpoint.value if self.source.endpoint else None,
            "contract": self.contract.digest_payload() if self.contract else None,
            "claims": dict(sorted(self.claims.items())),
        }

    @property
    def observation_digest(self) -> str:
        """Fingerprint of what was observed. Not the security binding."""
        return compute_digest(self.observation_payload()).value

    def describes_same_observation_as(self, other: "CapabilityCandidate") -> bool:
        return self.observation_digest == other.observation_digest

    def incomplete(self, *missing: str) -> "CapabilityCandidate":
        return replace(
            self,
            status=CandidateStatus.INCOMPLETE,
            missing=tuple(sorted(set(self.missing) | set(missing))),
            contract=None,
        )

    def rejected(self, *reasons: str) -> "CapabilityCandidate":
        return replace(
            self,
            status=CandidateStatus.REJECTED,
            rejections=tuple(sorted(set(self.rejections) | set(reasons))),
            contract=None,
        )

    def to_dict(self) -> dict:
        return {
            "candidate_id": self.candidate_id,
            "reference": self.reference.value,
            "capability_id": self.capability_id.value,
            "version": self.version.number,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "status": self.status.value,
            "may_be_ingested": self.may_be_ingested,
            "missing": list(self.missing),
            "rejections": list(self.rejections),
            "source": self.source.to_dict(),
            "is_self_declared": self.is_self_declared,
            "observed_at": self.observed_at.isoformat(),
            "observation_digest": self.observation_digest,
            "contract": self.contract.to_dict() if self.contract else None,
            "claims": dict(self.claims),
        }
