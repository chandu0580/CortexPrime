"""The ContextBundle application service.

Assembles, expands, resolves, and versions bundles. Events are returned, never
published -- this context owns no bus, the same arrangement as every other
context in the engineering layer.

Expansion is three explicit steps
----------------------------------
``request_expansion`` records the ask. ``decide_expansion`` records the answer
(auto-granting deterministically where the path is already conceptually inside
the bundle). ``apply_expansion`` widens and versions.

Collapsing them into one call would make the common failure -- a grant whose
assembly then fails -- indistinguishable from a denial. Keeping them apart means
a granted-but-unapplied request is a visible state: the bundle knows it owes
someone a path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef, TenantScope
from backend.contexts.context_bundle.application.commands import (
    AssembleBundle,
    DecideExpansion,
    GetBundle,
    InvalidateBundle,
    ListBundles,
    RequestExpansion,
    ResolveBundle,
)
from backend.contexts.context_bundle.domain.bundle import ContextBundle
from backend.contexts.context_bundle.domain.errors import (
    BundleNotFound,
    ExpansionDenied,
    UnknownExpansion,
)
from backend.contexts.context_bundle.domain.events import (
    AGGREGATE_TYPE,
    ContextBundleCreated,
    ContextExpanded,
    ContextInvalidated,
    ContextResolved,
    ContextSuperseded,
    ContextVersioned,
)
from backend.contexts.context_bundle.domain.expansion import Disposition, ExpansionRequest
from backend.contexts.context_bundle.domain.factory import assemble, dependency, reference
from backend.contexts.context_bundle.domain.identifiers import BundleId, ExpansionRequestId
from backend.contexts.context_bundle.domain.layers import ContextLayer
from backend.platform.events import EventMetadata

__all__ = ["ContextBundleService", "CommandResult"]


@dataclass(frozen=True)
class CommandResult:
    bundle: ContextBundle
    events: tuple

    @property
    def event_types(self) -> tuple:
        return tuple(getattr(type(e), "EVENT_TYPE", "?") for e in self.events)


class ContextBundleService:
    def __init__(self, repository: Any) -> None:
        self._repository = repository

    @staticmethod
    def _metadata(context: Any, bundle: ContextBundle) -> EventMetadata:
        scope = getattr(context, "scope", None)
        if scope is None:
            scope = TenantScope(tenant=TenantRef(tenant_id=context.tenant_id))
        return EventMetadata.create(
            aggregate_id=str(bundle.bundle_id),
            aggregate_type=AGGREGATE_TYPE,
            scope=scope,
        )

    def _load(self, context: Any, bundle_id: str) -> ContextBundle:
        found = self._repository.find(context, BundleId(bundle_id))
        if found is None:
            raise BundleNotFound(bundle_id)
        return found

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------

    def assemble(self, context: Any, command: AssembleBundle) -> CommandResult:
        bundle = assemble(
            work_id=command.work_id,
            work_order_version=command.work_order_version,
            base_commit=command.base_commit,
            blast_radius=command.blast_radius_allowed,
            forbidden=command.blast_radius_forbidden,
            read_only=command.blast_radius_read_only,
            searchable=command.searchable,
            excluded_from_search=command.excluded_from_search,
            adr_references=command.adr_references,
            superseded_adrs=command.superseded_adrs,
            dependencies=tuple(
                dependency(name, interfaces, implementations=implementations)
                for name, interfaces, implementations in command.dependencies
            ),
            references=tuple(
                reference(path, ContextLayer(layer), content_digest=digest)
                for path, layer, digest in command.references
            ),
            assembled_by=command.assembled_by,
        )
        self._repository.save(context, bundle)
        return CommandResult(
            bundle=bundle,
            events=(
                ContextBundleCreated(
                    metadata=self._metadata(context, bundle),
                    bundle_id=str(bundle.bundle_id),
                    work_id=bundle.work_id,
                    work_order_version=bundle.work_order_version,
                    version=bundle.version,
                    base_commit=bundle.base_commit,
                    manifest_digest=bundle.manifest_digest or "",
                    reference_count=len(bundle.references),
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Expansion
    # ------------------------------------------------------------------

    def request_expansion(self, context: Any, command: RequestExpansion) -> CommandResult:
        """Record the ask. Recording is not granting."""
        bundle = self._load(context, command.bundle_id)
        request = ExpansionRequest.create(
            command.requested_path,
            command.question,
            command.requested_by,
            target_layer=ContextLayer(command.target_layer),
        )
        updated = bundle.request_expansion(request)
        self._repository.replace(context, updated)
        return CommandResult(bundle=updated, events=())

    def decide_expansion(self, context: Any, command: DecideExpansion) -> CommandResult:
        """Answer the ask, auto-granting where the path is already inside.

        Auto-grant is checked first and beats an explicit denial: a caller
        denying an ADR the bundle's own index already names is denying something
        the agent was effectively promised, and honouring that would produce a
        bundle inconsistent with itself.
        """
        bundle = self._load(context, command.bundle_id)
        request_id = ExpansionRequestId(command.request_id)
        request = bundle.expansion(request_id)
        if request is None:
            raise UnknownExpansion(bundle_id=command.bundle_id, request_id=command.request_id)

        auto = bundle.auto_grant_candidate(request.requested_path)
        if auto is not None:
            decided = request.auto_grant(auto)
        elif command.grant:
            decided = request.grant(command.decided_by, command.reason)
        else:
            decided = request.deny(command.decided_by, command.reason or "outside the declared boundary")

        updated = bundle.decide_expansion(request_id, decided)
        self._repository.replace(context, updated)
        return CommandResult(bundle=updated, events=())

    def apply_expansion(
        self, context: Any, bundle_id: str, request_id: str, references: tuple
    ) -> CommandResult:
        """Widen and version, or refuse.

        A denied request raises rather than returning quietly. Silently
        no-op'ing would let a caller believe the bundle grew.
        """
        bundle = self._load(context, bundle_id)
        rid = ExpansionRequestId(request_id)
        request = bundle.expansion(rid)
        if request is None:
            raise UnknownExpansion(bundle_id=bundle_id, request_id=request_id)
        if request.disposition is Disposition.DENIED:
            raise ExpansionDenied(
                request_id=request_id,
                path=request.requested_path,
                reason=request.decision_reason or "unstated",
            )

        widened = bundle.apply_expansion(
            rid,
            tuple(
                reference(path, ContextLayer(layer), content_digest=digest)
                for path, layer, digest in references
            ),
        )
        retired = bundle.supersede(widened.bundle_id)

        self._repository.replace(context, retired)
        self._repository.save(context, widened)

        return CommandResult(
            bundle=widened,
            events=(
                ContextExpanded(
                    metadata=self._metadata(context, widened),
                    bundle_id=str(widened.bundle_id),
                    work_id=widened.work_id,
                    request_id=request_id,
                    requested_path=request.requested_path,
                    question=request.question,
                    disposition=request.disposition.value,
                    decided_by=request.decided_by or "orchestrator",
                    paths_added=len(widened.references) - len(bundle.references),
                ),
                ContextVersioned(
                    metadata=self._metadata(context, widened),
                    bundle_id=str(widened.bundle_id),
                    work_id=widened.work_id,
                    from_version=bundle.version,
                    to_version=widened.version,
                    manifest_digest=widened.manifest_digest or "",
                    predecessor=str(bundle.bundle_id),
                ),
                ContextSuperseded(
                    metadata=self._metadata(context, retired),
                    bundle_id=str(retired.bundle_id),
                    work_id=retired.work_id,
                    superseded_by=str(widened.bundle_id),
                    reason="expanded",
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, context: Any, command: ResolveBundle):
        """Hand the bundle to an agent, or refuse.

        The last point at which giving an agent a description of a tree nobody is
        working on can still be prevented.
        """
        bundle = self._load(context, command.bundle_id)
        resolved = bundle.resolve(current_commit=command.current_commit)
        return resolved, (
            ContextResolved(
                metadata=self._metadata(context, bundle),
                bundle_id=str(bundle.bundle_id),
                work_id=bundle.work_id,
                version=bundle.version,
                manifest_digest=bundle.manifest_digest or "",
                readable_paths=len(resolved.readable),
                writable_paths=len(resolved.writable),
                resolved_for=command.resolved_for,
            ),
        )

    def invalidate(self, context: Any, command: InvalidateBundle) -> CommandResult:
        bundle = self._load(context, command.bundle_id)
        updated = bundle.invalidate(command.reason)
        self._repository.replace(context, updated)
        return CommandResult(
            bundle=updated,
            events=(
                ContextInvalidated(
                    metadata=self._metadata(context, updated),
                    bundle_id=str(updated.bundle_id),
                    work_id=updated.work_id,
                    version=updated.version,
                    reason=command.reason,
                    current_commit=command.current_commit or "",
                ),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, context: Any, query: GetBundle) -> ContextBundle:
        return self._load(context, query.bundle_id)

    def current_for(self, context: Any, work_id: str) -> Optional[ContextBundle]:
        """The active bundle for a WorkOrder, or ``None``.

        Superseded and invalidated bundles are skipped: neither is what an agent
        should be working from.
        """
        active = [
            b for b in self._repository.for_work_order(context, work_id) if b.is_usable
        ]
        if not active:
            return None
        return max(active, key=lambda b: (b.version, b.bundle_id.value))

    def list(self, context: Any, query: ListBundles) -> tuple:
        found = (
            self._repository.for_work_order(context, query.work_id)
            if query.work_id
            else self._repository.all(context)
        )
        if query.active_only:
            found = tuple(b for b in found if b.is_usable)
        return tuple(found)

    def boundary_signals(self, context: Any, *, minimum_requests: int = 2) -> tuple:
        """Paths requested often enough to suggest the boundary is wrong."""
        from backend.contexts.context_bundle.domain.factory import boundary_signals

        return boundary_signals(
            self._repository.all(context), minimum_requests=minimum_requests
        )
