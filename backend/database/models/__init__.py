from backend.database.models.audit_log import AuditLog
from backend.database.models.connector_activity import ConnectorActivityModel
from backend.database.models.cost_intelligence import (
    CostRecordModel,
    OptimizationRecommendationModel,
    ProviderRateModel,
)
from backend.database.models.embedding_cache import EmbeddingCacheRecord
from backend.database.models.episodic_memory import EpisodicMemoryRecord
from backend.database.models.fleet import FleetAgentModel, FleetDeploymentModel, FleetMetricsSnapshotModel, FleetModel
from backend.database.models.reflection_history import ReflectionHistoryRecord
from backend.database.models.runtime_analytics import RuntimeAnalyticsRecord
from backend.database.models.semantic_memory import SemanticMemoryRecord
from backend.database.models.workflow import WorkflowEdgeModel, WorkflowModel, WorkflowNodeModel

__all__ = [
    "EpisodicMemoryRecord",
    "SemanticMemoryRecord",
    "ReflectionHistoryRecord",
    "RuntimeAnalyticsRecord",
    "EmbeddingCacheRecord",
    "AuditLog",
    "ConnectorActivityModel",
    "FleetModel",
    "FleetAgentModel",
    "FleetDeploymentModel",
    "FleetMetricsSnapshotModel",
    "WorkflowModel",
    "WorkflowNodeModel",
    "WorkflowEdgeModel",
    "ProviderRateModel",
    "CostRecordModel",
    "OptimizationRecommendationModel",
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
    import backend.database.repositories.iam  # noqa: F401
    import backend.database.repositories.knowledge  # noqa: F401
    import backend.database.repositories.learning  # noqa: F401
    import backend.database.repositories.missions  # noqa: F401
    import backend.database.repositories.platform  # noqa: F401
    _IMPORTED_BC_MODELS = True
