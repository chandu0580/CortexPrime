from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.mission_intel.analyzer import mission_analyzer, MissionAnalyzer
from backend.mission_intel.capability_planner import capability_planner, CapabilityPlanner
from backend.mission_intel.decomposer import mission_decomposer, MissionDecomposer
from backend.mission_intel.execution_planner import execution_planner, ExecutionPlanner
from backend.mission_intel.governance_planner import governance_planner, GovernancePlanner
from backend.mission_intel.knowledge_planner import knowledge_planner, KnowledgePlanner
from backend.mission_intel.learning_planner import learning_planner, LearningPlanner
from backend.mission_intel.models import (
    CapabilityPlan,
    ExecutionPlan,
    GovernancePlan,
    KnowledgeInsight,
    LearningInsight,
    MissionAnalysis,
    MissionDecomposition,
    MissionTimeline,
    MissionVerification,
)
from backend.mission_intel.timeline import mission_timeline_builder, MissionTimelineBuilder
from backend.mission_intel.verification import mission_verifier, MissionVerifier

log = logging.getLogger(__name__)


class MissionIntelligenceService:

    def __init__(
        self,
        analyzer: Optional[MissionAnalyzer] = None,
        decomposer: Optional[MissionDecomposer] = None,
        capability_planner_: Optional[CapabilityPlanner] = None,
        knowledge_planner_: Optional[KnowledgePlanner] = None,
        learning_planner_: Optional[LearningPlanner] = None,
        governance_planner_: Optional[GovernancePlanner] = None,
        execution_planner_: Optional[ExecutionPlanner] = None,
        verifier: Optional[MissionVerifier] = None,
        timeline_builder: Optional[MissionTimelineBuilder] = None,
    ) -> None:
        self._analyzer = analyzer or mission_analyzer
        self._decomposer = decomposer or mission_decomposer
        self._capability_planner = capability_planner_ or capability_planner
        self._knowledge_planner = knowledge_planner_ or knowledge_planner
        self._learning_planner = learning_planner_ or learning_planner
        self._governance_planner = governance_planner_ or governance_planner
        self._execution_planner = execution_planner_ or execution_planner
        self._verifier = verifier or mission_verifier
        self._timeline_builder = timeline_builder or mission_timeline_builder

    async def analyze(self, goal: str, context: Optional[Dict[str, Any]] = None) -> MissionAnalysis:
        return await self._analyzer.analyze(goal, context)

    async def decompose(self, analysis: MissionAnalysis) -> MissionDecomposition:
        return await self._decomposer.decompose(analysis)

    async def plan_capability(
        self,
        decomposition: MissionDecomposition,
        connector_registry: Any = None,
    ) -> CapabilityPlan:
        return await self._capability_planner.plan(decomposition, connector_registry)

    async def plan_knowledge(self, analysis: MissionAnalysis) -> KnowledgeInsight:
        return await self._knowledge_planner.plan(analysis)

    async def plan_learning(
        self,
        analysis: MissionAnalysis,
        knowledge_insight: KnowledgeInsight,
    ) -> LearningInsight:
        return await self._learning_planner.plan(analysis, knowledge_insight)

    async def plan_governance(
        self,
        analysis: MissionAnalysis,
        learning_insight: LearningInsight,
    ) -> GovernancePlan:
        return await self._governance_planner.plan(analysis, learning_insight)

    async def plan_execution(
        self,
        decomposition: MissionDecomposition,
        capability_plan: CapabilityPlan,
        governance_plan: GovernancePlan,
    ) -> ExecutionPlan:
        return await self._execution_planner.plan(decomposition, capability_plan, governance_plan)

    async def verify(
        self,
        decomposition: MissionDecomposition,
        execution_plan: ExecutionPlan,
    ) -> MissionVerification:
        return await self._verifier.verify(decomposition, execution_plan)

    async def build_timeline(
        self,
        analysis: MissionAnalysis,
        decomposition: MissionDecomposition,
        execution_plan: ExecutionPlan,
    ) -> MissionTimeline:
        return await self._timeline_builder.build(analysis, decomposition, execution_plan)

    async def run_full_pipeline(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        connector_registry: Any = None,
    ) -> Dict[str, Any]:
        analysis = await self.analyze(goal, context)
        decomposition = await self.decompose(analysis)
        capability_plan = await self.plan_capability(decomposition, connector_registry)
        knowledge_insight = await self.plan_knowledge(analysis)
        learning_insight = await self.plan_learning(analysis, knowledge_insight)
        governance_plan = await self.plan_governance(analysis, learning_insight)
        execution_plan = await self.plan_execution(decomposition, capability_plan, governance_plan)
        verification = await self.verify(decomposition, execution_plan)
        timeline = await self.build_timeline(analysis, decomposition, execution_plan)
        return {
            "analysis": analysis,
            "decomposition": decomposition,
            "capability_plan": capability_plan,
            "knowledge_insight": knowledge_insight,
            "learning_insight": learning_insight,
            "governance_plan": governance_plan,
            "execution_plan": execution_plan,
            "verification": verification,
            "timeline": timeline,
        }


mission_intel_service = MissionIntelligenceService()
