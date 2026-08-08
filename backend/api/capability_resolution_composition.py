"""Composition root for capability resolution and binding.

Assembles the resolution service over the registry, the binding repository and
audit. Kept in one named module for the same reason the other composition roots
are: a reviewer asking "what actually selects providers on this platform?" reads
one file.

Nothing here imports Execution, Workflow, Mission, Intent or Planner, and none
of those import this. When Phase 3.3 attaches, the flow is:

    CapabilityBinding  →  composition root adapter  →  WorkerKindResolver
                                                    →  worker / connector

`WorkerKindResolver` (ADR-030) remains untouched and remains the only execution
attachment seam. Resolution produces the binding it will eventually be handed;
it does not reach across the boundary itself.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.contexts.connectivity import (
    CapabilityResolutionService,
    InMemoryBindingRepository,
)

__all__ = ["build_resolution"]


def build_resolution(
    registry: Any,
    *,
    bindings: Optional[Any] = None,
    audit: Optional[Any] = None,
) -> CapabilityResolutionService:
    """The resolver this deployment runs.

    ``bindings=None`` creates an in-memory repository. Bindings expire in
    minutes and a lost one simply means re-resolving, so non-durability here is
    survivable -- but it is not durable, and that is stated rather than implied.
    """
    return CapabilityResolutionService(
        registry=registry,
        bindings=bindings if bindings is not None else InMemoryBindingRepository(),
        audit=audit,
    )
