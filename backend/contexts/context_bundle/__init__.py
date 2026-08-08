"""The ContextBundle bounded context.

Constructs, validates, versions and resolves the context every engineering
WorkOrder is worked from. It is the canonical answer to "what did the agent see?"

Every bundle is immutable, versioned, and carries the four members the
Engineering Constitution requires: a repository scope, ADR references, dependency
contracts, and a blast radius. It grows only through a recorded expansion request
-- there is no path by which a bundle widens implicitly.

    domain/          pure -- layers, scope, expansion, the bundle
    application/     commands, queries, the service
    infrastructure/  repository, record mapping

Named ``context_bundle`` rather than ``context`` because ``backend/platform/context``
already holds ``ExecutionContext`` (ADR-017), which appears as a parameter in
nearly every method in this codebase. Two things called "context" one layer apart
would be genuinely confusing. See ADR-022.

This context imports ``contracts/`` and ``platform/`` and nothing else.
"""

from backend.contexts.context_bundle.application import (
    ApplyExpansion, AssembleBundle, CommandResult, ContextBundleService, DecideExpansion,
    GetBoundarySignals, GetBundle, InvalidateBundle, ListBundles, RequestExpansion,
    ResolveBundle,
)
from backend.contexts.context_bundle.domain import (
    ARTIFACT_KIND, AUTO_GRANT_PREFIXES, AccessMode, AdrBundle, BlastRadiusSpec,
    BoundarySignal, BundleId, BundleInvalidated, BundleNotFound, BundleStatus,
    BundleSuperseded, CANONICAL_FORM_VERSION, CONTEXT_EVENT_TYPES, ContextBundle,
    ContextBundleCreated, ContextBundleError, ContextExpanded, ContextInvalidated,
    ContextLayer, ContextReference, ContextResolved, ContextSuperseded, ContextVersioned,
    DependencyContract, Disposition, DuplicateBundle, ExpansionAlreadyDecided,
    ExpansionDenied, ExpansionRequest, ExpansionRequestId, ImplicitExpansion,
    IncompleteBundle, LAYER_ACCESS, LayerViolation, ManifestMismatch, RepositoryScope,
    ResolvedContext, StaleBaseCommit, UnknownExpansion, assemble, auto_grant_reason,
    boundary_signals, dependency, reference,
)
from backend.contexts.context_bundle.infrastructure import (
    ContextRepository, InMemoryContextRepository,
)

__all__ = [
    "ContextBundle", "ResolvedContext", "BundleStatus", "BundleId", "ExpansionRequestId",
    "ContextLayer", "AccessMode", "ContextReference", "LAYER_ACCESS",
    "RepositoryScope", "AdrBundle", "DependencyContract", "BlastRadiusSpec",
    "ExpansionRequest", "Disposition", "auto_grant_reason", "AUTO_GRANT_PREFIXES",
    "assemble", "reference", "dependency", "boundary_signals", "BoundarySignal",
    "ARTIFACT_KIND", "CANONICAL_FORM_VERSION",
    "ContextBundleService", "CommandResult",
    "AssembleBundle", "RequestExpansion", "DecideExpansion", "ApplyExpansion",
    "ResolveBundle", "InvalidateBundle", "GetBundle", "ListBundles", "GetBoundarySignals",
    "ContextRepository", "InMemoryContextRepository",
    "ContextBundleCreated", "ContextExpanded", "ContextResolved", "ContextInvalidated",
    "ContextVersioned", "ContextSuperseded", "CONTEXT_EVENT_TYPES",
    "ContextBundleError", "LayerViolation", "ImplicitExpansion", "ExpansionDenied",
    "ExpansionAlreadyDecided", "UnknownExpansion", "BundleSuperseded", "BundleInvalidated",
    "StaleBaseCommit", "ManifestMismatch", "IncompleteBundle", "BundleNotFound",
    "DuplicateBundle",
]
