"""Composition root: Connectivity's binding meets Execution's runtime.

**This is the only module that imports both contexts.** Execution does not import
Connectivity and Connectivity does not import Execution — verified in both
directions by architecture tests. Everything they exchange crosses here, as
primitives.

Three adapters, three ports
-----------------------------
``BindingProjector``   — ``CapabilityBinding`` → ``BoundCapability``. A one-way
                         projection into primitives: Execution receives what was
                         authorized and gains no way to mint one.
``BindingValidatorAdapter`` — implements Execution's ``BindingValidator`` over
                         Connectivity's ``validate_binding`` (ADR-035), so the
                         authoritative lifecycle/trust/digest re-check happens
                         where that state actually lives.
``WorkerKindAdapter``  — implements Execution's ``WorkerKindPort`` over the
                         existing ``WorkerKindResolver`` (ADR-030), which is
                         unchanged and remains the single execution attachment
                         seam.

Deliberately absent
---------------------
No worker. ``StaticWorkerDirectory`` maps kinds to adapters and starts empty, so
every invocation refuses with ``worker_unavailable`` until Phase 3.3.2 registers
something real. That is the correct behaviour for a platform with no workers: it
refuses rather than inventing a default.

No credential provider. The seam exists in Execution; nothing implements it here.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from backend.contexts.connectivity import CapabilityBinding
from backend.contexts.execution import (
    BoundCapability,
    WorkerKind,
    WorkerRuntime,
)

__all__ = [
    "project_binding",
    "BindingValidatorAdapter",
    "WorkerKindAdapter",
    "StaticWorkerDirectory",
    "build_worker_runtime",
]

log = logging.getLogger(__name__)


def project_binding(binding: CapabilityBinding) -> BoundCapability:
    """Project a Connectivity binding into the primitives Execution may hold.

    One-way on purpose. There is no inverse: Execution cannot reconstruct a
    ``CapabilityBinding``, so it can never produce authority — only carry it.
    """
    if binding.digest is None:
        raise ValueError(
            f"binding {binding.binding_id} is unsealed; an unsealed binding "
            "cannot be shown to be the one that was made"
        )
    if binding.effect_semantics is None or binding.side_effect_class is None:
        raise ValueError(
            f"binding {binding.binding_id} does not declare its effect; Execution "
            "decides retry safety from that declaration and will not infer one"
        )
    return BoundCapability(
        binding_id=binding.binding_id,
        binding_digest=binding.digest,
        capability_ref=binding.reference.value,
        capability_digest=binding.capability_digest,
        provider=binding.provider,
        operation=binding.operation.value,
        authorization_digest=binding.authorization_digest,
        tenant_id=binding.tenant_id,
        principal_id=binding.principal.principal_id,
        expires_at=binding.expires_at,
        side_effect_class=binding.side_effect_class,
        effect_semantics=binding.effect_semantics,
        execution_id=binding.execution_id,
        node_id=binding.node_id,
        workflow_id=binding.workflow_id,
        mission_id=binding.mission_id,
        resolution_policy_version=binding.resolution_policy_version,
        authorization_policy_version=binding.authorization_policy_version,
    )


class BindingValidatorAdapter:
    """Execution's ``BindingValidator``, answered by Connectivity.

    Looks the binding up by id and asks ``validate_binding`` — the same
    authoritative re-check ADR-035 defined. Execution never sees the aggregate;
    it receives the invalidation reasons.

    A binding that cannot be found is invalid, not absent-and-therefore-fine.
    """

    def __init__(self, resolution_service: Any) -> None:
        self._resolution = resolution_service

    def invalidations(self, context: Any, binding: BoundCapability) -> tuple:
        stored = self._resolution._bindings.find(  # noqa: SLF001
            context, binding.binding_id
        )
        if stored is None:
            return ("binding_not_found",)
        if stored.digest != binding.binding_digest:
            # The projection disagrees with the record it claims to describe.
            return ("binding_digest_mismatch",)
        return tuple(
            self._resolution.validate_binding(
                context,
                stored,
                tenant_id=binding.tenant_id,
                principal_id=binding.principal_id,
                execution_id=binding.execution_id,
                node_id=binding.node_id,
            )
        )


class WorkerKindAdapter:
    """Execution's ``WorkerKindPort``, answered by the existing resolver.

    ``WorkerKindResolver`` (ADR-030) is unchanged. It was written to answer
    "which kind of worker runs this node?" from a workflow node; here it is
    asked the same question about a bound capability, and the mapping key is the
    capability reference.

    A resolver that cannot answer returns ``None``, and Execution refuses.
    Nothing here supplies a default.
    """

    def __init__(self, resolver: Any) -> None:
        self._resolver = resolver

    def kind_for(self, binding: BoundCapability) -> Optional[str]:
        # The resolver's node-shaped interface, satisfied by the capability.
        probe = _CapabilityAsNode(binding)
        try:
            return self._resolver.kind_for(binding.capability_ref, probe)
        except Exception:  # noqa: BLE001 - unresolvable is a refusal, not a guess
            log.warning("worker kind resolution failed", exc_info=True)
            return None


class _CapabilityAsNode:
    """Adapts a bound capability to the shape ``WorkerKindResolver`` reads.

    The resolver takes something with a ``node_id``. Rather than change its
    semantics — which ADR-030 and every later phase have preserved — the
    capability reference is presented as the node identity, so an existing
    resolver keyed by capability works unmodified.
    """

    __slots__ = ("node_id", "binding")

    def __init__(self, binding: BoundCapability) -> None:
        self.node_id = binding.capability_ref
        self.binding = binding


class StaticWorkerDirectory:
    """Maps a worker kind to an adapter. Starts empty, and stays empty here.

    Not a registry, not discovery, no health, no ranking, and no fallback. One
    lookup that can answer ``None``, because a missing adapter must be a refusal
    rather than a substitution.

    Phase 3.3.2 populates this with real adapters. Until then every invocation
    refuses with ``worker_unavailable``, which is the correct behaviour for a
    platform that has no workers.
    """

    def __init__(self, adapters: Optional[Mapping[WorkerKind, Any]] = None) -> None:
        self._adapters = dict(adapters or {})

    def register(self, kind: WorkerKind, adapter: Any) -> None:
        if kind in self._adapters:
            raise ValueError(
                f"an adapter for {kind.value} is already registered; silently "
                "replacing one would change what runs without anybody deciding"
            )
        self._adapters[kind] = adapter

    def adapter_for(self, kind: WorkerKind) -> Optional[Any]:
        return self._adapters.get(kind)

    def __len__(self) -> int:
        return len(self._adapters)


def build_worker_runtime(
    *,
    resolution_service: Any,
    worker_kind_resolver: Any,
    directory: Optional[StaticWorkerDirectory] = None,
    input_validator: Optional[Any] = None,
    observer: Optional[Any] = None,
) -> WorkerRuntime:
    """Assemble the runtime. Refuses everything until workers exist."""
    return WorkerRuntime(
        binding_validator=BindingValidatorAdapter(resolution_service),
        worker_kinds=WorkerKindAdapter(worker_kind_resolver),
        directory=directory if directory is not None else StaticWorkerDirectory(),
        input_validator=input_validator,
        observer=observer,
    )
