"""The ContextBundle aggregate.

Immutable and versioned, as the Constitution requires. Every expansion returns a
*new* bundle at ``version + 1``; the prior version is superseded rather than
mutated, so "what did the agent see?" always has an answer even after the bundle
grew.

Identity is four values
-----------------------
``(work_id, work_order_version, base_commit, version)``. A bundle is fully
derivable from those plus the assembly rules, which makes it **derived memory**
under Engineering Constitution §8.3 -- regenerable, never hand-edited.

``base_commit`` is part of identity rather than metadata because a bundle
describes a particular tree. The same four-tuple with a different commit is not a
newer version of the same bundle; it is a bundle of a different thing.

The manifest digest
-------------------
``manifest_digest`` is what turns "this is what the agent saw" from an assertion
about the past into a verifiable claim. A verifier can recompute it and say
whether the record still describes what it claims.

Versioned canonicalisation and domain separation, for the same reasons as the
WorkOrder digest in ADR-019: silent serialisation changes make every stored
digest unverifiable with no error to announce it, and an undifferentiated hash
could be replayed as a digest over some other artifact.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Final, Iterable, Optional

from backend.contracts._contract import Contract
from backend.contracts.approval import HashAlgorithm, PayloadDigest
from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle.domain.errors import (
    BundleInvalidated,
    BundleSuperseded,
    ImplicitExpansion,
    IncompleteBundle,
    ManifestMismatch,
    StaleBaseCommit,
    UnknownExpansion,
)
from backend.contexts.context_bundle.domain.expansion import (
    Disposition,
    ExpansionRequest,
    auto_grant_reason,
)
from backend.contexts.context_bundle.domain.identifiers import (
    BundleId,
    ExpansionRequestId,
)
from backend.contexts.context_bundle.domain.layers import ContextLayer, ContextReference
from backend.contexts.context_bundle.domain.scope import (
    AdrBundle,
    BlastRadiusSpec,
    DependencyContract,
    RepositoryScope,
)
from backend.platform.hashing import compute_digest, digests_match

__all__ = [
    "BundleStatus",
    "ContextBundle",
    "ResolvedContext",
    "ARTIFACT_KIND",
    "CANONICAL_FORM_VERSION",
]

ARTIFACT_KIND: Final[str] = "cortexprime.engineering.contextbundle"
CANONICAL_FORM_VERSION: Final[int] = 1


class BundleStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALIDATED = "invalidated"

    @property
    def is_usable(self) -> bool:
        return self is BundleStatus.ACTIVE


@dataclass(frozen=True)
class ResolvedContext:
    """What an agent actually receives. The output of resolution.

    Separate from the bundle because they answer different questions. The bundle
    is the record of what was assembled and why; this is the view handed to a
    role, flattened and grouped by access. Handing the aggregate over directly
    would let a consumer reach the expansion history and the superseded chain,
    neither of which is context.
    """

    bundle_id: str
    work_id: str
    version: int
    base_commit: str
    readable: tuple
    writable: tuple
    searchable: tuple
    adr_references: tuple
    dependencies: tuple
    manifest_digest: str
    resolved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_paths(self) -> int:
        return len(self.readable) + len(self.writable)


@dataclass(frozen=True)
class ContextBundle(Contract):
    """Everything one role instance may see, for one WorkOrder version."""

    CONTRACT_NAME = "cortexprime.engineering.context_bundle"

    bundle_id: BundleId
    work_id: str
    work_order_version: int
    base_commit: str
    version: int

    # The four mandatory members.
    repository_scope: RepositoryScope
    adr_bundle: AdrBundle
    dependencies: tuple
    blast_radius: BlastRadiusSpec

    references: tuple = ()
    expansions: tuple = ()
    status: BundleStatus = BundleStatus.ACTIVE
    manifest_digest: Optional[str] = None
    assembled_by: str = "orchestrator"
    assembled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    supersedes: Optional[BundleId] = None
    superseded_by: Optional[BundleId] = None
    invalidation_reason: Optional[str] = None

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if not isinstance(self.bundle_id, BundleId):
            raise ContractViolation("bundle_id must be a BundleId")
        for label, value in (("work_id", self.work_id), ("base_commit", self.base_commit)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        for label, value in (
            ("work_order_version", self.work_order_version),
            ("version", self.version),
        ):
            if not isinstance(value, int) or value < 1:
                raise ContractViolation(f"{label} must be a positive integer starting at 1")

        missing: list = []
        if not isinstance(self.repository_scope, RepositoryScope):
            missing.append("repository scope")
        if not isinstance(self.adr_bundle, AdrBundle):
            missing.append("ADR references")
        if not isinstance(self.blast_radius, BlastRadiusSpec):
            missing.append("blast radius")
        if not isinstance(self.dependencies, tuple):
            missing.append("dependency contracts")
        if missing:
            raise IncompleteBundle(missing=missing)

        for item in self.dependencies:
            if not isinstance(item, DependencyContract):
                raise ContractViolation(
                    f"dependencies contains {item!r}, which is not a DependencyContract"
                )

        for label, items, expected in (
            ("references", self.references, ContextReference),
            ("expansions", self.expansions, ExpansionRequest),
        ):
            if not isinstance(items, tuple):
                raise ContractViolation(f"{label} must be a tuple")
            for item in items:
                if not isinstance(item, expected):
                    raise ContractViolation(
                        f"{label} contains {item!r}, which is not a {expected.__name__}"
                    )

        paths = [r.path for r in self.references]
        if len(set(paths)) != len(paths):
            raise ContractViolation(
                "references contains the same path twice; a path in two layers would "
                "have two access modes"
            )

        request_ids = [str(e.request_id) for e in self.expansions]
        if len(set(request_ids)) != len(request_ids):
            raise ContractViolation("expansions contains duplicate request ids")

        if self.status is BundleStatus.SUPERSEDED and self.superseded_by is None:
            raise ContractViolation("a superseded bundle must name its successor")
        if self.status is BundleStatus.INVALIDATED and not (
            self.invalidation_reason and self.invalidation_reason.strip()
        ):
            raise ContractViolation(
                "an invalidated bundle must say why; an unexplained invalidation tells "
                "a reader nothing they can act on"
            )
        for label, value in (("supersedes", self.supersedes), ("superseded_by", self.superseded_by)):
            if value is not None and not isinstance(value, BundleId):
                raise ContractViolation(f"{label} must be a BundleId when present")
        if self.assembled_at.tzinfo is None:
            raise ContractViolation("assembled_at must be timezone-aware")

        # A version above 1 exists because something was granted. Version 1 with
        # a granted expansion means the widening was applied without versioning,
        # which is the same defect from the other direction.
        granted = sum(1 for e in self.expansions if e.widens_bundle)
        if self.version > 1 and granted == 0:
            raise ContractViolation(
                f"bundle is at version {self.version} with no granted expansion; a "
                "version exists because something was explicitly widened"
            )

    # ------------------------------------------------------------------
    # Identity and queries
    # ------------------------------------------------------------------

    @property
    def identity(self) -> tuple:
        return (self.work_id, self.work_order_version, self.base_commit, self.version)

    @property
    def is_usable(self) -> bool:
        return self.status.is_usable

    def by_layer(self, layer: ContextLayer) -> tuple:
        return tuple(r for r in self.references if r.layer is layer)

    @property
    def writable_paths(self) -> tuple:
        return tuple(sorted(r.path for r in self.references if r.writable))

    @property
    def readable_paths(self) -> tuple:
        return tuple(
            sorted(r.path for r in self.references if r.access.permits_read and not r.writable)
        )

    @property
    def dependency_interfaces(self) -> tuple:
        return tuple(sorted(p for d in self.dependencies for p in d.interface_paths))

    def expansion(self, request_id: ExpansionRequestId) -> Optional[ExpansionRequest]:
        for item in self.expansions:
            if item.request_id == request_id:
                return item
        return None

    @property
    def pending_expansions(self) -> tuple:
        return tuple(e for e in self.expansions if not e.disposition.is_decided)

    @property
    def denied_expansions(self) -> tuple:
        """Kept deliberately. A denial is information."""
        return tuple(e for e in self.expansions if e.disposition is Disposition.DENIED)

    def contains(self, path: str) -> bool:
        normalised = path.strip().replace("\\", "/")
        return any(r.path == normalised for r in self.references)

    # ------------------------------------------------------------------
    # Manifest digest
    # ------------------------------------------------------------------

    def manifest_payload(self) -> dict[str, Any]:
        """The exact structure the manifest digest covers.

        Exposed so a verifier can recompute it and say which member diverged,
        rather than reporting only that two hex strings differ.

        Expansion *decisions* are excluded: they are recorded after assembly and
        including them would mean deciding a request invalidated the digest of
        the bundle that request was made against. Granted expansions change the
        references, and those are covered.
        """
        return {
            "__artifact__": ARTIFACT_KIND,
            "__canonical_form__": CANONICAL_FORM_VERSION,
            "work_id": self.work_id,
            "work_order_version": self.work_order_version,
            "base_commit": self.base_commit,
            "version": self.version,
            "repository_scope": {
                "searchable": list(self.repository_scope.searchable),
                "excluded": list(self.repository_scope.excluded),
            },
            "adr_bundle": {
                "references": list(self.adr_bundle.references),
                "superseded": list(self.adr_bundle.superseded),
            },
            "dependencies": sorted(
                (
                    {
                        "name": d.name,
                        "interface_paths": list(d.interface_paths),
                        "implementation_paths": list(d.implementation_paths),
                    }
                    for d in self.dependencies
                ),
                key=lambda item: item["name"],
            ),
            "blast_radius": {
                "allowed": list(self.blast_radius.allowed),
                "forbidden": list(self.blast_radius.forbidden),
                "read_only": list(self.blast_radius.read_only),
            },
            "references": sorted(
                (
                    {
                        "path": r.path,
                        "layer": r.layer.value,
                        "content_digest": r.content_digest,
                    }
                    for r in self.references
                ),
                key=lambda item: (item["layer"], item["path"]),
            ),
        }

    def compute_manifest_digest(
        self, algorithm: HashAlgorithm = HashAlgorithm.SHA256
    ) -> PayloadDigest:
        return compute_digest(self.manifest_payload(), algorithm)

    def sealed(self) -> "ContextBundle":
        """Record the manifest digest. Done once, at assembly."""
        return replace(self, manifest_digest=self.compute_manifest_digest().value)

    def verify_manifest(self) -> None:
        """Raise unless the bundle still hashes to its recorded manifest."""
        if not self.manifest_digest:
            raise ContractViolation(
                f"bundle {self.bundle_id} has no manifest digest; it was never sealed, so "
                "there is nothing to verify it against"
            )
        recomputed = self.compute_manifest_digest()
        if not digests_match(
            recomputed,
            PayloadDigest(algorithm=recomputed.algorithm, value=self.manifest_digest),
        ):
            raise ManifestMismatch(
                bundle_id=str(self.bundle_id),
                recorded=self.manifest_digest,
                recomputed=recomputed.value,
            )

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _require_usable(self) -> None:
        if self.status is BundleStatus.SUPERSEDED:
            raise BundleSuperseded(
                bundle_id=str(self.bundle_id), successor=str(self.superseded_by)
            )
        if self.status is BundleStatus.INVALIDATED:
            raise BundleInvalidated(
                bundle_id=str(self.bundle_id), reason=self.invalidation_reason or "unstated"
            )

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def request_expansion(self, request: ExpansionRequest) -> "ContextBundle":
        """Record a request. Recording it is not granting it."""
        self._require_usable()
        if not isinstance(request, ExpansionRequest):
            raise ContractViolation("request must be an ExpansionRequest")
        if self.expansion(request.request_id) is not None:
            raise ContractViolation(f"expansion {request.request_id} is already recorded")
        return replace(self, expansions=self.expansions + (request,))

    def auto_grant_candidate(self, path: str) -> Optional[str]:
        """Why ``path`` could be auto-granted for this bundle, or ``None``."""
        return auto_grant_reason(path, dependency_interfaces=self.dependency_interfaces)

    def decide_expansion(
        self, request_id: ExpansionRequestId, decided: ExpansionRequest
    ) -> "ContextBundle":
        """Record a decision without applying it.

        Deciding and widening are separate steps on purpose. A granted request
        that has not been applied is a visible state -- the bundle knows it owes
        someone a path -- whereas a combined operation would make an
        assembly failure look like a denial.
        """
        self._require_usable()
        existing = self.expansion(request_id)
        if existing is None:
            raise UnknownExpansion(
                bundle_id=str(self.bundle_id), request_id=str(request_id)
            )
        return replace(
            self,
            expansions=tuple(
                decided if e.request_id == request_id else e for e in self.expansions
            ),
        )

    def apply_expansion(
        self, request_id: ExpansionRequestId, references: Iterable[ContextReference]
    ) -> "ContextBundle":
        """Widen the bundle under a granted request, producing a new version.

        The only path by which a bundle grows. Every reference added must fall
        under the granted path, and a request that was denied or is still pending
        widens nothing.
        """
        self._require_usable()
        request = self.expansion(request_id)
        if request is None:
            raise UnknownExpansion(
                bundle_id=str(self.bundle_id), request_id=str(request_id)
            )
        if not request.widens_bundle:
            raise ImplicitExpansion(
                bundle_id=str(self.bundle_id), path=request.requested_path
            )

        added = tuple(references)
        granted_root = request.requested_path.rstrip("/")
        for reference in added:
            if not isinstance(reference, ContextReference):
                raise ContractViolation("references must be ContextReference values")
            if reference.path != granted_root and not reference.path.startswith(
                granted_root + "/"
            ):
                raise ImplicitExpansion(
                    bundle_id=str(self.bundle_id), path=reference.path
                )
            if reference.layer is ContextLayer.OWNED:
                raise ImplicitExpansion(
                    bundle_id=str(self.bundle_id), path=reference.path
                )

        existing = {r.path for r in self.references}
        fresh = tuple(r for r in added if r.path not in existing)

        widened = replace(
            self,
            version=self.version + 1,
            references=self.references + fresh,
            manifest_digest=None,
            supersedes=self.bundle_id,
            bundle_id=BundleId.new(),
            assembled_at=datetime.now(timezone.utc),
        )
        return widened.sealed()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def supersede(self, successor: BundleId) -> "ContextBundle":
        if not isinstance(successor, BundleId):
            raise ContractViolation("successor must be a BundleId")
        if successor == self.bundle_id:
            raise ContractViolation("a bundle cannot supersede itself")
        if self.superseded_by is not None:
            raise ContractViolation(
                f"bundle {self.bundle_id} is already superseded by {self.superseded_by}"
            )
        return replace(self, status=BundleStatus.SUPERSEDED, superseded_by=successor)

    def invalidate(self, reason: str) -> "ContextBundle":
        if not reason or not reason.strip():
            raise ContractViolation("invalidating a bundle must say why")
        return replace(
            self, status=BundleStatus.INVALIDATED, invalidation_reason=reason.strip()
        )

    def check_freshness(self, current_commit: str) -> None:
        """Raise if the tree moved under this bundle."""
        if current_commit and current_commit != self.base_commit:
            raise StaleBaseCommit(
                bundle_id=str(self.bundle_id),
                assembled_at=self.base_commit,
                current=current_commit,
            )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, *, current_commit: Optional[str] = None) -> ResolvedContext:
        """Produce the view an agent receives.

        Refuses a superseded, invalidated, or stale bundle. Resolution is the
        moment an agent is about to reason from this, which is the last point at
        which handing it a description of a tree nobody is working on can still
        be prevented.
        """
        self._require_usable()
        if current_commit:
            self.check_freshness(current_commit)
        self.verify_manifest()

        return ResolvedContext(
            bundle_id=str(self.bundle_id),
            work_id=self.work_id,
            version=self.version,
            base_commit=self.base_commit,
            readable=self.readable_paths,
            writable=self.writable_paths,
            searchable=tuple(self.repository_scope.searchable),
            adr_references=tuple(self.adr_bundle.references),
            dependencies=tuple(sorted(d.name for d in self.dependencies)),
            manifest_digest=self.manifest_digest or "",
        )
