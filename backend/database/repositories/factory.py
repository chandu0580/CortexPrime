from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.engine import AsyncSessionLocal
from backend.database.repositories.agents import AgentConfigRepository, AgentStateRepository
from backend.database.repositories.billing import InvoiceRepository, UsageRecordRepository
from backend.database.repositories.connectors import (
    ConnectorActivityRepository,
    ConnectorConfigRepository,
)
from backend.database.repositories.digital_twin import (
    InfrastructureMetricRepository,
    InfrastructureModelRepository,
    InfrastructureRelationshipRepository,
)
from backend.database.repositories.executions import ExecutionEventRepository, ExecutionRepository
from backend.database.repositories.governance import (
    ApprovalRequestRepository,
    ComplianceRuleRepository,
    PolicyRepository,
)
from backend.database.repositories.iam import ApiKeyRepository, RoleRepository, UserRepository
from backend.database.repositories.knowledge import (
    KnowledgeEntryRepository,
    KnowledgeRelationshipRepository,
)
from backend.database.repositories.learning import LearningPatternRepository, LearningSessionRepository
from backend.database.repositories.missions import MissionRepository, MissionStepRepository
from backend.database.repositories.platform import FeatureFlagRepository, PlatformSettingRepository


class RepositoryFactory:
    def __init__(self, session: Optional[AsyncSession] = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        if self._session is None:
            return AsyncSessionLocal()
        return self._session

    async def user_repo(self) -> UserRepository:
        return UserRepository(await self._get_session())

    async def role_repo(self) -> RoleRepository:
        return RoleRepository(await self._get_session())

    async def api_key_repo(self) -> ApiKeyRepository:
        return ApiKeyRepository(await self._get_session())

    async def mission_repo(self) -> MissionRepository:
        return MissionRepository(await self._get_session())

    async def mission_step_repo(self) -> MissionStepRepository:
        return MissionStepRepository(await self._get_session())

    async def execution_repo(self) -> ExecutionRepository:
        return ExecutionRepository(await self._get_session())

    async def execution_event_repo(self) -> ExecutionEventRepository:
        return ExecutionEventRepository(await self._get_session())

    async def knowledge_entry_repo(self) -> KnowledgeEntryRepository:
        return KnowledgeEntryRepository(await self._get_session())

    async def knowledge_rel_repo(self) -> KnowledgeRelationshipRepository:
        return KnowledgeRelationshipRepository(await self._get_session())

    async def learning_session_repo(self) -> LearningSessionRepository:
        return LearningSessionRepository(await self._get_session())

    async def learning_pattern_repo(self) -> LearningPatternRepository:
        return LearningPatternRepository(await self._get_session())

    async def infra_model_repo(self) -> InfrastructureModelRepository:
        return InfrastructureModelRepository(await self._get_session())

    async def infra_rel_repo(self) -> InfrastructureRelationshipRepository:
        return InfrastructureRelationshipRepository(await self._get_session())

    async def infra_metric_repo(self) -> InfrastructureMetricRepository:
        return InfrastructureMetricRepository(await self._get_session())

    async def policy_repo(self) -> PolicyRepository:
        return PolicyRepository(await self._get_session())

    async def compliance_rule_repo(self) -> ComplianceRuleRepository:
        return ComplianceRuleRepository(await self._get_session())

    async def approval_request_repo(self) -> ApprovalRequestRepository:
        return ApprovalRequestRepository(await self._get_session())

    async def connector_config_repo(self) -> ConnectorConfigRepository:
        return ConnectorConfigRepository(await self._get_session())

    async def connector_activity_repo(self) -> ConnectorActivityRepository:
        return ConnectorActivityRepository(await self._get_session())

    async def agent_config_repo(self) -> AgentConfigRepository:
        return AgentConfigRepository(await self._get_session())

    async def agent_state_repo(self) -> AgentStateRepository:
        return AgentStateRepository(await self._get_session())

    async def feature_flag_repo(self) -> FeatureFlagRepository:
        return FeatureFlagRepository(await self._get_session())

    async def platform_setting_repo(self) -> PlatformSettingRepository:
        return PlatformSettingRepository(await self._get_session())

    async def usage_record_repo(self) -> UsageRecordRepository:
        return UsageRecordRepository(await self._get_session())

    async def invoice_repo(self) -> InvoiceRepository:
        return InvoiceRepository(await self._get_session())


repo_factory = RepositoryFactory()
