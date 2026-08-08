"""ContextBundle domain: layers, scope, expansion, and the bundle itself.

Pure. No I/O, no persistence, no framework.
"""

from backend.contexts.context_bundle.domain.bundle import (
    ARTIFACT_KIND, CANONICAL_FORM_VERSION, BundleStatus, ContextBundle, ResolvedContext,
)
from backend.contexts.context_bundle.domain.errors import (
    BundleInvalidated, BundleNotFound, BundleSuperseded, ContextBundleError,
    DuplicateBundle, ExpansionAlreadyDecided, ExpansionDenied, ImplicitExpansion,
    IncompleteBundle, InvalidIdentifier, LayerViolation, ManifestMismatch,
    StaleBaseCommit, UnknownExpansion,
)
from backend.contexts.context_bundle.domain.events import (
    CONTEXT_EVENT_TYPES, ContextBundleCreated, ContextExpanded, ContextInvalidated,
    ContextResolved, ContextSuperseded, ContextVersioned,
)
from backend.contexts.context_bundle.domain.expansion import (
    AUTO_GRANT_PREFIXES, Disposition, ExpansionRequest, auto_grant_reason,
)
from backend.contexts.context_bundle.domain.factory import (
    BoundarySignal, assemble, boundary_signals, dependency, reference,
)
from backend.contexts.context_bundle.domain.identifiers import BundleId, ExpansionRequestId
from backend.contexts.context_bundle.domain.layers import (
    LAYER_ACCESS, AccessMode, ContextLayer, ContextReference,
)
from backend.contexts.context_bundle.domain.scope import (
    AdrBundle, BlastRadiusSpec, DependencyContract, RepositoryScope,
)

__all__ = [
    "ContextBundle", "ResolvedContext", "BundleStatus", "BundleId", "ExpansionRequestId",
    "ContextLayer", "AccessMode", "ContextReference", "LAYER_ACCESS",
    "RepositoryScope", "AdrBundle", "DependencyContract", "BlastRadiusSpec",
    "ExpansionRequest", "Disposition", "auto_grant_reason", "AUTO_GRANT_PREFIXES",
    "assemble", "reference", "dependency", "boundary_signals", "BoundarySignal",
    "ARTIFACT_KIND", "CANONICAL_FORM_VERSION",
    "ContextBundleCreated", "ContextExpanded", "ContextResolved", "ContextInvalidated",
    "ContextVersioned", "ContextSuperseded", "CONTEXT_EVENT_TYPES",
    "ContextBundleError", "InvalidIdentifier", "LayerViolation", "ImplicitExpansion",
    "ExpansionDenied", "ExpansionAlreadyDecided", "UnknownExpansion", "BundleSuperseded",
    "BundleInvalidated", "StaleBaseCommit", "ManifestMismatch", "IncompleteBundle",
    "BundleNotFound", "DuplicateBundle",
]
