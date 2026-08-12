"""World Plane application layer — ports and the ingestion service.

Depends on the epistemic contracts and the platform secret detector only. It
does not import a database, a connector, the gateway, the harness, or the
execution plane — composition supplies the repository, and the caller supplies
an already-read external result plus its governed context.
"""

from backend.world.application.ingestion import (
    ObservationIngestion,
    ObservationRejected,
    ObservationRepository,
    ReadObservation,
    observation_identity,
)
from backend.world.application.bitemporal import (
    ConflictingValue,
    FactStateView,
    FactVersion,
    HistoryEntry,
    as_known,
    as_of_valid,
    current_state,
    history,
    knowledge_current,
    project_valid_at,
)
from backend.world.application.fact_derivation import (
    DerivationOutcome,
    DerivationResult,
    FactDerivation,
    FactDerivationRejected,
    FactRepository,
    fact_semantic_identity,
    fact_version_identity,
)
from backend.world.application.freshness import (
    FreshnessPolicy,
    FreshnessResult,
    FreshnessRule,
    FreshnessState,
)
from backend.world.application.authority import (
    AuthorityAlternative,
    AuthorityDecision,
    AuthorityPolicy,
    AuthorityRule,
    AuthorityStatus,
)
from backend.world.application.world_query import (
    FactVersionReader,
    ObservationEvidence,
    ObservationReader,
    WorldQuery,
    WorldQueryResult,
)

__all__ = [
    # observation ingestion (Phase 7.2)
    "ObservationRepository",
    "ObservationIngestion",
    "ObservationRejected",
    "ReadObservation",
    "observation_identity",
    # fact derivation (Phase 7.3)
    "FactRepository",
    "FactDerivation",
    "FactDerivationRejected",
    "DerivationOutcome",
    "DerivationResult",
    "fact_semantic_identity",
    "fact_version_identity",
    # bitemporal projection + queries (Phase 7.3)
    "FactVersion",
    "FactStateView",
    "ConflictingValue",
    "HistoryEntry",
    "knowledge_current",
    "project_valid_at",
    "current_state",
    "as_of_valid",
    "as_known",
    "history",
    # freshness (Phase 7.4)
    "FreshnessPolicy",
    "FreshnessRule",
    "FreshnessResult",
    "FreshnessState",
    # authority (Phase 7.4)
    "AuthorityPolicy",
    "AuthorityRule",
    "AuthorityDecision",
    "AuthorityAlternative",
    "AuthorityStatus",
    # world query (Phase 7.4)
    "WorldQuery",
    "WorldQueryResult",
    "ObservationEvidence",
    "FactVersionReader",
    "ObservationReader",
]
