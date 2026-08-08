"""The CapabilityDefinition aggregate: one version of one declared ability.

What this is
--------------
The authoritative answer to "what is this capability, who answers for it, and
may it run". It is the object an approval is *about*, which is why its contract
is digest-bound and why the fields that make up its security identity cannot be
changed after registration.

Immutability
--------------
``capability_id``, ``version``, ``contract``, ``owner``, ``tenancy`` and
``provider`` form the registered identity. There is no method on this class that
changes any of them. The mutating methods -- ``validated``, ``enabled``,
``disabled``, ``revoked``, ``trust_*`` -- move status and trust and nothing else.

That is deliberate rather than incidental: if a definition could be edited in
place, then every execution approved against it would silently be approved
against whatever it later became.

Two axes decide executability
-------------------------------
``status`` says whether it is meant to be available. ``trust`` says whether the
platform vouches for it. ``is_executable`` requires both, so that a later
resolver cannot treat "I found it in the registry" as "it is safe to run".
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Mapping, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalRef
from backend.contexts.connectivity.domain.contract import (
    CapabilityContract,
    CapabilityEnvironment,
)
from backend.contexts.connectivity.domain.errors import (
    CapabilityNotExecutable,
    CapabilityRevokedError,
    IllegalCapabilityTransition,
    IllegalTrustTransition,
    OwnerRequired,
    TenancyViolation,
)
from backend.contexts.connectivity.domain.identifiers import (
    CapabilityId,
    CapabilityNamespace,
    CapabilityRef,
    CapabilityVersion,
)
from backend.contexts.connectivity.domain.lifecycle import (
    CapabilityStatus,
    TrustState,
    is_legal_status_transition,
    is_legal_trust_transition,
    status_permitted_from,
    status_refusal_reason,
    trust_permitted_from,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "CapabilityTenancy",
    "CapabilitySource",
    "CapabilityDefinition",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
    "GOVERNED_FIELDS",
]

ARTIFACT_KIND: Final[str] = "cortexprime.connectivity.capability"
CANONICAL_FORM_VERSION: Final[int] = 1

#: What the contract digest covers. Status, trust, health and timestamps are
#: excluded on purpose: the digest answers "is this the contract that was
#: approved", and one that changed when a capability was disabled would make
#: that question unanswerable.
GOVERNED_FIELDS: Final[tuple] = (
    "capability_id",
    "version",
    "provider",
    "owner",
    "tenancy",
    "contract",
)


class CapabilityTenancy(str, Enum):
    """Who a capability belongs to and who may see it."""

    PLATFORM = "platform"
    """Supplied and owned by CortexPrime. Serves every tenant, and that fact is
    stated rather than inferred from an absent tenant id."""

    TENANT = "tenant"
    """Belongs to exactly one tenant. Never discoverable or executable by
    another -- the repository enforces this, not a convention."""

    SHARED = "shared"
    """Platform-registered, offered to a named set of tenants. Explicit because
    'shared' arrived at by omission is how one tenant's capability becomes
    everybody's."""

    @property
    def requires_tenant(self) -> bool:
        return self is CapabilityTenancy.TENANT


class CapabilitySource(str, Enum):
    """Where this definition came from. Provenance, not discovery.

    Recorded now so that when discovery arrives (Phase 3.2.2) a capability that
    a machine found can be told apart from one a human declared. They deserve
    different default trust, and that distinction is impossible to reconstruct
    afterwards.
    """

    INTERNAL = "internal"
    """Declared by the platform itself."""

    MANUAL = "manual"
    """Registered by a human through the API."""

    CONNECTOR_PACKAGE = "connector_package"
    """Declared by an installed connector package."""

    MCP = "mcp"
    """Advertised by an MCP server."""

    AGENT = "agent"
    """Declared by an agent about itself."""

    DISCOVERY = "discovery"
    """Found by automated discovery. Phase 3.2.2; recorded here so the seam
    exists before anything can use it."""

    IMPORT = "import"
    """Bulk-imported from another registry."""

    @property
    def is_self_declared(self) -> bool:
        """Whether the thing being described is what described it.

        A capability that vouches for itself is exactly the one that should not
        start out trusted.
        """
        return self in {CapabilitySource.MCP, CapabilitySource.AGENT}


@dataclass(frozen=True)
class CapabilityDefinition(Contract):
    """One version of one declared ability."""

    CONTRACT_NAME = "cortexprime.connectivity.capability_definition"

    capability_id: CapabilityId
    version: CapabilityVersion
    name: str
    description: str
    provider: str
    contract: CapabilityContract
    owner: PrincipalRef
    tenancy: CapabilityTenancy
    source: CapabilitySource

    tenant_id: Optional[str] = None
    shared_with: tuple = ()
    category: Optional[str] = None

    status: CapabilityStatus = CapabilityStatus.REGISTERED
    trust: TrustState = TrustState.UNVERIFIED
    digest: Optional[str] = None

    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    status_note: Optional[str] = None
    supersedes: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, CapabilityId):
            raise ContractViolation("capability_id must be a CapabilityId")
        if not isinstance(self.version, CapabilityVersion):
            raise ContractViolation("version must be a CapabilityVersion")
        if not isinstance(self.contract, CapabilityContract):
            raise ContractViolation("contract must be a CapabilityContract")
        if not isinstance(self.status, CapabilityStatus):
            raise ContractViolation("status must be a CapabilityStatus")
        if not isinstance(self.trust, TrustState):
            raise ContractViolation("trust must be a TrustState")
        if not isinstance(self.source, CapabilitySource):
            raise ContractViolation("source must be a CapabilitySource")
        if not isinstance(self.tenancy, CapabilityTenancy):
            raise ContractViolation("tenancy must be a CapabilityTenancy")

        for label in ("name", "description", "provider"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a capability nobody can read "
                    "the purpose of cannot be reviewed before it is trusted"
                )

        if not isinstance(self.owner, PrincipalRef):
            raise OwnerRequired(self.reference.value)

        # Tenancy must be stated, and must be consistent with the identity.
        if self.tenancy.requires_tenant and not self.tenant_id:
            raise TenancyViolation(
                self.reference.value,
                "tenant-scoped capabilities must name their tenant; one that does "
                "not is visible to whoever queries for it",
            )
        if self.tenancy is CapabilityTenancy.PLATFORM and self.tenant_id:
            raise TenancyViolation(
                self.reference.value,
                "a platform capability must not name a tenant; naming one makes it "
                "unclear whether the other tenants may use it",
            )
        if self.tenancy is CapabilityTenancy.SHARED and not self.shared_with:
            raise TenancyViolation(
                self.reference.value,
                "a shared capability must name the tenants it is shared with; "
                "'shared with nobody in particular' is shared with everybody",
            )
        if (
            self.capability_id.namespace is CapabilityNamespace.TENANT
            and self.tenancy is CapabilityTenancy.PLATFORM
        ):
            raise TenancyViolation(
                self.reference.value,
                "a capability in the tenant namespace cannot be platform-owned; "
                "the namespace exists so tenant declarations cannot become "
                "platform ones",
            )

        for tenant in self.shared_with:
            if not isinstance(tenant, str) or not tenant.strip():
                raise TenancyViolation(
                    self.reference.value, "shared_with must contain tenant ids"
                )

        if self.supersedes is not None and self.supersedes >= self.version.number:
            raise ContractViolation(
                "a version can only supersede an earlier one"
            )

        # A revoked capability may never be trusted: the two together would say
        # "withdrawn, and vouched for".
        if self.status is CapabilityStatus.REVOKED and self.trust.permits_execution:
            raise ContractViolation(
                "a revoked capability cannot be verified or trusted; withdrawing "
                "something and vouching for it are contradictory statements"
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def reference(self) -> CapabilityRef:
        return CapabilityRef(capability_id=self.capability_id, version=self.version)

    @property
    def is_executable(self) -> bool:
        """Both axes must agree. Registration alone is never enough."""
        return self.status.permits_execution and self.trust.permits_execution

    @property
    def is_discoverable(self) -> bool:
        return self.status.is_discoverable

    @property
    def effect_is_declared(self) -> bool:
        return self.contract.is_effect_declared

    def assert_executable(self) -> None:
        if not self.is_executable:
            raise CapabilityNotExecutable(
                capability_ref=self.reference.value,
                status=self.status.value,
                trust=self.trust.value,
            )

    def permits_environment(self, environment: CapabilityEnvironment) -> bool:
        return self.contract.permits_environment(environment)

    def visible_to(self, tenant_id: Optional[str]) -> bool:
        """Whether a given tenant may see this capability at all."""
        if self.tenancy is CapabilityTenancy.PLATFORM:
            return True
        if self.tenancy is CapabilityTenancy.TENANT:
            return bool(tenant_id) and tenant_id == self.tenant_id
        return bool(tenant_id) and tenant_id in self.shared_with

    def permitted_transitions(self) -> tuple:
        return status_permitted_from(self.status)

    def permitted_trust_transitions(self) -> tuple:
        return trust_permitted_from(self.trust)

    # ------------------------------------------------------------------
    # Digest
    # ------------------------------------------------------------------

    def digest_payload(self) -> dict:
        """The security-relevant definition, canonically ordered."""
        return {
            "artifact_kind": ARTIFACT_KIND,
            "canonical_form_version": CANONICAL_FORM_VERSION,
            "capability_id": self.capability_id.value,
            "version": self.version.number,
            "provider": self.provider,
            "owner": {
                "principal_id": self.owner.principal_id,
                "kind": self.owner.kind.value,
            },
            "tenancy": self.tenancy.value,
            "tenant_id": self.tenant_id,
            "shared_with": sorted(self.shared_with),
            "contract": self.contract.digest_payload(),
        }

    def compute_digest(self, algorithm: HashAlgorithm = HashAlgorithm.SHA256) -> PayloadDigest:
        return compute_digest(self.digest_payload(), algorithm)

    def sealed(self) -> "CapabilityDefinition":
        """Bind the digest. Done once, at registration."""
        return replace(self, digest=self.compute_digest().value)

    def verify_digest(self) -> None:
        from backend.contexts.connectivity.domain.errors import CapabilityError

        if not self.digest:
            raise CapabilityError(
                f"{self.reference.value} carries no contract digest; an unsealed "
                "definition cannot be shown to be the one that was approved"
            )
        recomputed = self.compute_digest()
        if not digests_match(
            recomputed, PayloadDigest(algorithm=recomputed.algorithm, value=self.digest)
        ):
            raise CapabilityError(
                f"{self.reference.value} does not match its recorded contract digest; "
                f"recorded {self.digest[:16]}..., recomputed {recomputed.value[:16]}.... "
                "The stored definition changed after registration"
            )

    def has_same_contract_as(self, other: "CapabilityDefinition") -> bool:
        """Whether two registrations describe the identical contract.

        What separates an idempotent re-registration from an attempt to redefine
        a version that something has already been approved against.
        """
        return self.compute_digest().value == other.compute_digest().value

    # ------------------------------------------------------------------
    # Transitions -- status and trust only. Never identity.
    # ------------------------------------------------------------------

    def _moved(
        self,
        target: CapabilityStatus,
        note: Optional[str],
        **also: Any,
    ) -> "CapabilityDefinition":
        if self.status is CapabilityStatus.REVOKED:
            raise CapabilityRevokedError(self.reference.value, f"moving to {target.value}")
        if not is_legal_status_transition(self.status, target):
            raise IllegalCapabilityTransition(
                capability_ref=self.reference.value,
                source=self.status.value,
                target=target.value,
                permitted=status_permitted_from(self.status),
                reason=status_refusal_reason(self.status, target) or "",
            )
        # ``also`` lands in the *same* construction as the status change. A move
        # that needs two edits to be legal must not be applied as two edits: the
        # halfway object -- revoked but still trusted -- is one the invariants
        # correctly refuse, and building it at all is the bug.
        return replace(
            self,
            status=target,
            status_note=note,
            updated_at=datetime.now(timezone.utc),
            **also,
        )

    def validated(self, note: str = "contract checked") -> "CapabilityDefinition":
        return self._moved(CapabilityStatus.VALIDATED, note)

    def enabled(self, note: str = "made available") -> "CapabilityDefinition":
        return self._moved(CapabilityStatus.ENABLED, note)

    def disabled(self, reason: str) -> "CapabilityDefinition":
        if not reason.strip():
            raise ContractViolation(
                "disabling a capability must say why; an unexplained withdrawal "
                "tells whoever depended on it nothing"
            )
        return self._moved(CapabilityStatus.DISABLED, reason)

    def deprecated(self, reason: str) -> "CapabilityDefinition":
        if not reason.strip():
            raise ContractViolation("deprecating a capability must say why")
        return self._moved(CapabilityStatus.DEPRECATED, reason)

    def revoked(self, reason: str) -> "CapabilityDefinition":
        """Withdraw permanently, and drop trust with it."""
        if not reason.strip():
            raise ContractViolation(
                "revoking a capability must say why; revocation is permanent and "
                "the reason is the only thing that explains it afterwards"
            )
        # Trust cannot outlive the capability: leaving it TRUSTED would let a
        # withdrawn definition still read as vouched-for. Dropped in the same
        # construction as the revocation.
        return self._moved(
            CapabilityStatus.REVOKED, reason, trust=TrustState.UNTRUSTED
        )

    def _trust_moved(self, target: TrustState, note: Optional[str]) -> "CapabilityDefinition":
        if self.status is CapabilityStatus.REVOKED:
            raise CapabilityRevokedError(self.reference.value, f"trusting as {target.value}")
        if not is_legal_trust_transition(self.trust, target):
            raise IllegalTrustTransition(
                capability_ref=self.reference.value,
                source=self.trust.value,
                target=target.value,
                permitted=trust_permitted_from(self.trust),
            )
        return replace(
            self, trust=target, status_note=note, updated_at=datetime.now(timezone.utc)
        )

    def verified(self, note: str = "declaration checked against behaviour"):
        return self._trust_moved(TrustState.VERIFIED, note)

    def trusted(self, note: str = "cleared for consequential work"):
        return self._trust_moved(TrustState.TRUSTED, note)

    def quarantined(self, reason: str) -> "CapabilityDefinition":
        if not reason.strip():
            raise ContractViolation("quarantining a capability must say why")
        return self._trust_moved(TrustState.QUARANTINED, reason)

    def distrusted(self, reason: str) -> "CapabilityDefinition":
        if not reason.strip():
            raise ContractViolation("declaring a capability untrusted must say why")
        return self._trust_moved(TrustState.UNTRUSTED, reason)

    def released_from_quarantine(self, note: str = "released for re-checking"):
        return self._trust_moved(TrustState.UNVERIFIED, note)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def register(
        cls,
        *,
        capability_id: CapabilityId,
        version: CapabilityVersion,
        name: str,
        description: str,
        provider: str,
        contract: CapabilityContract,
        owner: PrincipalRef,
        tenancy: CapabilityTenancy,
        source: CapabilitySource,
        tenant_id: Optional[str] = None,
        shared_with: tuple = (),
        category: Optional[str] = None,
        supersedes: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> "CapabilityDefinition":
        """A newly registered capability: REGISTERED, UNVERIFIED, sealed.

        Never ENABLED and never trusted on arrival. Something that describes
        itself and is immediately usable is a self-signed certificate.
        """
        return cls(
            capability_id=capability_id,
            version=version,
            name=name.strip(),
            description=description.strip(),
            provider=provider.strip(),
            contract=contract,
            owner=owner,
            tenancy=tenancy,
            source=source,
            tenant_id=tenant_id,
            shared_with=tuple(shared_with),
            category=category,
            status=CapabilityStatus.REGISTERED,
            trust=TrustState.UNVERIFIED,
            supersedes=supersedes,
            metadata=dict(metadata or {}),
        ).sealed()

    def to_dict(self) -> dict:
        return {
            **self.digest_payload(),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "source": self.source.value,
            "status": self.status.value,
            "trust": self.trust.value,
            "is_executable": self.is_executable,
            "digest": self.digest,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status_note": self.status_note,
            "supersedes": self.supersedes,
            "metadata": dict(self.metadata),
        }
