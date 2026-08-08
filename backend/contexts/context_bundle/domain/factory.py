"""Construction helpers, and the boundary signal derived from expansion history.

:func:`assemble` is the ergonomic path in: it builds a sealed, version-1 bundle
from plain values, so a bundle cannot be created unsealed by accident.

:func:`boundary_signals` is the reason the expansion log is worth keeping.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from backend.contexts.context_bundle.domain.bundle import ContextBundle
from backend.contexts.context_bundle.domain.expansion import Disposition, ExpansionRequest
from backend.contexts.context_bundle.domain.identifiers import BundleId
from backend.contexts.context_bundle.domain.layers import ContextLayer, ContextReference
from backend.contexts.context_bundle.domain.scope import (
    AdrBundle,
    BlastRadiusSpec,
    DependencyContract,
    RepositoryScope,
)

__all__ = ["assemble", "reference", "dependency", "BoundarySignal", "boundary_signals"]


def reference(
    path: str,
    layer: ContextLayer,
    *,
    content_digest: Optional[str] = None,
    note: Optional[str] = None,
) -> ContextReference:
    """A reference, with a placeholder digest for retrievable layers.

    Retrievable layers require a digest, so the convenience default keeps a
    caller from having to hash a file just to express intent in a test. Real
    assembly supplies the real digest -- the composition root reads the file.
    """
    if layer.carries_content and content_digest is None:
        content_digest = f"unhashed:{path}"
    return ContextReference(
        path=path, layer=layer, content_digest=content_digest, note=note
    )


def dependency(
    name: str,
    interfaces: Sequence[str],
    *,
    implementations: Sequence[str] = (),
    reason: Optional[str] = None,
) -> DependencyContract:
    return DependencyContract(
        name=name,
        interface_paths=tuple(interfaces),
        implementation_paths=tuple(implementations),
        reason=reason,
    )


def assemble(
    *,
    work_id: str,
    work_order_version: int,
    base_commit: str,
    blast_radius: Sequence[str],
    searchable: Sequence[str],
    adr_references: Sequence[str] = (),
    superseded_adrs: Sequence[str] = (),
    dependencies: Sequence[DependencyContract] = (),
    references: Iterable[ContextReference] = (),
    forbidden: Sequence[str] = (),
    read_only: Sequence[str] = (),
    excluded_from_search: Sequence[str] = (),
    assembled_by: str = "orchestrator",
) -> ContextBundle:
    """A sealed, version-1 bundle.

    Sealed here rather than left to the caller: an unsealed bundle has no
    manifest digest, and a bundle whose contents cannot be verified later is the
    thing this context exists to prevent.
    """
    bundle = ContextBundle(
        bundle_id=BundleId.new(),
        work_id=work_id,
        work_order_version=work_order_version,
        base_commit=base_commit,
        version=1,
        repository_scope=RepositoryScope(
            searchable=tuple(searchable), excluded=tuple(excluded_from_search)
        ),
        adr_bundle=AdrBundle(
            references=tuple(adr_references), superseded=tuple(superseded_adrs)
        ),
        dependencies=tuple(dependencies),
        blast_radius=BlastRadiusSpec(
            allowed=tuple(blast_radius), forbidden=tuple(forbidden), read_only=tuple(read_only)
        ),
        references=tuple(references),
        assembled_by=assembled_by,
    )
    return bundle.sealed()


@dataclass(frozen=True)
class BoundarySignal:
    """A path repeatedly requested from outside the bundles that hold it.

    The highest-value artifact this context produces, and the reason denied
    requests are kept rather than discarded.

    A path requested once is a scoping miss. The same path requested across
    several independent WorkOrders means the architectural boundary is drawn in
    the wrong place -- and that is a finding no code review surfaces, because
    each individual request looked reasonable to whoever made it.
    """

    path: str
    request_count: int
    work_orders: tuple
    questions: tuple
    denied_count: int

    @property
    def crosses_work_orders(self) -> bool:
        """One WorkOrder wanting a path repeatedly is a scoping miss.

        Several wanting it is an architecture finding.
        """
        return len(self.work_orders) > 1


def boundary_signals(
    bundles: Iterable[ContextBundle], *, minimum_requests: int = 2
) -> tuple:
    """Paths requested often enough to suggest the boundary is wrong.

    Counts every request regardless of disposition. A path that keeps being
    *granted* is as strong a signal as one that keeps being denied -- arguably
    stronger, since it means the boundary is routinely worked around rather than
    merely tested.
    """
    by_path: dict = {}
    for bundle in bundles:
        for request in bundle.expansions:
            entry = by_path.setdefault(
                request.requested_path,
                {"work_orders": set(), "questions": [], "denied": 0, "count": 0},
            )
            entry["count"] += 1
            entry["work_orders"].add(bundle.work_id)
            entry["questions"].append(request.question)
            if request.disposition is Disposition.DENIED:
                entry["denied"] += 1

    signals = [
        BoundarySignal(
            path=path,
            request_count=entry["count"],
            work_orders=tuple(sorted(entry["work_orders"])),
            questions=tuple(dict.fromkeys(entry["questions"])),
            denied_count=entry["denied"],
        )
        for path, entry in by_path.items()
        if entry["count"] >= minimum_requests
    ]
    return tuple(sorted(signals, key=lambda s: (-s.request_count, s.path)))
