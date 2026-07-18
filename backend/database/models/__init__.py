from backend.database.models.audit_log import AuditLog
from backend.database.models.embedding_cache import EmbeddingCacheRecord
from backend.database.models.episodic_memory import EpisodicMemoryRecord
from backend.database.models.reflection_history import ReflectionHistoryRecord
from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
from backend.database.models.semantic_memory import SemanticMemoryRecord

__all__ = [
    "EpisodicMemoryRecord",
    "SemanticMemoryRecord",
    "ReflectionHistoryRecord",
    "RuntimeAnalyticsRecord",
    "EmbeddingCacheRecord",
    "AuditLog",
]

_IMPORTED_BC_MODELS = False


def _ensure_bc_models() -> None:
    global _IMPORTED_BC_MODELS
    if _IMPORTED_BC_MODELS:
        return
    import backend.database.repositories.billing  # noqa: F401
    import backend.database.repositories.connectors  # noqa: F401
    import backend.database.repositories.digital_twin  # noqa: F401
    import backend.database.repositories.executions  # noqa: F401
    import backend.database.repositories.governance  # noqa: F401
    import backend.database.repositories.iam  # noqa: F401
    import backend.database.repositories.knowledge  # noqa: F401
    import backend.database.repositories.learning  # noqa: F401
    import backend.database.repositories.missions  # noqa: F401
    import backend.database.repositories.platform  # noqa: F401
    import backend.database.repositories.agents  # noqa: F401
    _IMPORTED_BC_MODELS = True
