"""
database.models — import all ORM models so that Base.metadata is populated.

Always import from this package rather than from individual model modules
to guarantee all tables are registered before create_all / Alembic runs.
"""
from backend.database.models.episodic_memory   import EpisodicMemoryRecord      # noqa: F401
from backend.database.models.semantic_memory   import SemanticMemoryRecord      # noqa: F401
from backend.database.models.reflection_history import ReflectionHistoryRecord  # noqa: F401
from backend.database.models.runtime_analytics  import RuntimeAnalyticsRecord   # noqa: F401
from backend.database.models.embedding_cache    import EmbeddingCacheRecord     # noqa: F401
from backend.database.models.audit_log          import AuditLog                 # noqa: F401

__all__ = [
    "EpisodicMemoryRecord",
    "SemanticMemoryRecord",
    "ReflectionHistoryRecord",
    "RuntimeAnalyticsRecord",
    "EmbeddingCacheRecord",
    "AuditLog",
]
