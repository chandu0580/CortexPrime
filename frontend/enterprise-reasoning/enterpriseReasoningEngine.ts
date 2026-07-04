import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseReasoningReport } from "./types"
import { StrategyReasoningEngine } from "./StrategyReasoningEngine"
import { CapabilityReasoningEngine } from "./CapabilityReasoningEngine"
import { RiskReasoningEngine } from "./RiskReasoningEngine"
import { DependencyReasoningEngine } from "./DependencyReasoningEngine"
import { RecommendationReasoningEngine } from "./RecommendationReasoningEngine"

export const enterpriseReasoningEngine = {
  async generateReasoningReport(report: MissionIntelligenceReport): Promise<EnterpriseReasoningReport> {
    const strategyDecision = await StrategyReasoningEngine.analyzeStrategy(report)
    const capabilityDecisions = await CapabilityReasoningEngine.analyzeCapabilities(report)
    const riskDecisions = await RiskReasoningEngine.analyzeRisks(report)
    const dependencyDecisions = await DependencyReasoningEngine.analyzeDependencies(report)
    const recommendationDecisions = await RecommendationReasoningEngine.analyzeRecommendations(report)

    const allDecisions = [
      strategyDecision,
      ...capabilityDecisions,
      ...riskDecisions,
      ...dependencyDecisions,
      ...recommendationDecisions,
    ]

    const totalConfidence = allDecisions.reduce((sum, d) => sum + d.confidence.score, 0)

    return {
      decisions: allDecisions,
      summary: `Enterprise reasoning report covering ${allDecisions.length} decisions across strategy, capability, risk, dependency, and recommendation domains. Average confidence: ${(totalConfidence / allDecisions.length * 100).toFixed(0)}%.`,
      traceCount: allDecisions.reduce((sum, d) => sum + d.explanation.trace.steps.length, 0),
      averageConfidence: totalConfidence / allDecisions.length,
      timestamp: new Date().toISOString(),
    }
  },
}
