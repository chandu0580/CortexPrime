# Phase 10.22 (ADR-116): the fleet, workflow-designer and cost-intelligence models
# are gitignored v2.0 components ("not part of v1.0.0 GA") and must NOT be imported
# here. Their re-export made a clean checkout unable to import this package,
# load Alembic metadata, or boot. See docs/PHASE_10_21_DISCOVERY.md.
from backend.database.models.audit_log import AuditLog
from backend.database.models.connector_activity import ConnectorActivityModel
from backend.database.models.cost_tracking import CostRecord
from backend.database.models.embedding_cache import EmbeddingCacheRecord
from backend.database.models.episodic_memory import EpisodicMemoryRecord
from backend.database.models.mission import MissionRecord
from backend.database.models.reflection_history import ReflectionHistoryRecord
from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
from backend.database.models.semantic_memory import SemanticMemoryRecord

__all__ = [
    "EpisodicMemoryRecord",
    "SemanticMemoryRecord",
    "MissionRecord",
    "ReflectionHistoryRecord",
    "RuntimeAnalyticsRecord",
    "CostRecord",
    "EmbeddingCacheRecord",
    "AuditLog",
    "ConnectorActivityModel",
]

_IMPORTED_BC_MODELS = False


def _ensure_bc_models() -> None:
    global _IMPORTED_BC_MODELS
    if _IMPORTED_BC_MODELS:
        return
    import backend.database.repositories.agents  # noqa: F401
    import backend.database.repositories.billing  # noqa: F401
    import backend.database.repositories.connectors  # noqa: F401
    import backend.database.repositories.digital_twin  # noqa: F401
    import backend.database.repositories.executions  # noqa: F401
    import backend.database.repositories.governance  # noqa: F401
    # Phase 10.14: the IAM models were retired. Re-adding this
    # import would put iam_users, iam_roles and iam_api_keys back
    # on Base.metadata, and init_db()'s create_all would recreate
    # the tables migration 0023 drops.
    import backend.database.repositories.knowledge  # noqa: F401
    import backend.database.repositories.learning  # noqa: F401
    import backend.database.repositories.missions  # noqa: F401
    import backend.database.repositories.platform  # noqa: F401
    _IMPORTED_BC_MODELS = True
