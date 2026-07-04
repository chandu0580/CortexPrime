import type { MissionAnalysis } from "@/types/intelligence"
import type { MissionIntelligenceReport } from "./types"
import { MissionStrategyEngine } from "./MissionStrategyEngine"
import { MissionPlanningEngine } from "./MissionPlanningEngine"
import { MissionCapabilityEngine } from "./MissionCapabilityEngine"
import { MissionRiskEngine } from "./MissionRiskEngine"
import { MissionGraphBuilder } from "./MissionGraphBuilder"

export const missionIntelligenceEngine = {
  async analyze(analysis: MissionAnalysis): Promise<MissionIntelligenceReport> {
    const strategy = await MissionStrategyEngine.buildStrategy(analysis)
    const plan = await MissionPlanningEngine.buildPlan(analysis)
    const capabilities = await MissionCapabilityEngine.recommendCapabilities(analysis)
    const risks = await MissionRiskEngine.evaluateRisks(analysis)
    const graph = await MissionGraphBuilder.buildMissionGraph(plan)

    return {
      strategy,
      plan,
      capabilities,
      risks,
      graph,
      timestamp: new Date().toISOString(),
    }
  },
}
