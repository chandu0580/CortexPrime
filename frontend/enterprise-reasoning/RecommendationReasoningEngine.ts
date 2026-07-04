import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseDecision } from "./types"
import { buildDecisionBase } from "./shared"

export const RecommendationReasoningEngine = {
  async analyzeRecommendations(report: MissionIntelligenceReport): Promise<EnterpriseDecision[]> {
    const recommendations = report.strategy.recommendations

    return recommendations.map((rec) => {
      const steps = [
        {
          id: `rec-step-${rec.id}-1`,
          order: 1,
          description: "Evaluate recommendation category",
          input: `Category: ${rec.category}`,
          output: `Recommendation addresses ${rec.category.toLowerCase()} aspect of mission execution`,
          confidence: { level: "high" as const, score: 0.85, rationale: "Category provides clear context for recommendation" },
        },
        {
          id: `rec-step-${rec.id}-2`,
          order: 2,
          description: "Assess priority alignment",
          input: `Priority: ${rec.priority}`,
          output: rec.priority === "critical" || rec.priority === "high" ? "High priority — requires immediate attention during planning" : "Standard priority — should be addressed during normal execution",
          confidence: { level: "high" as const, score: 0.8, rationale: "Priority derived from mission context and risk assessment" },
        },
        {
          id: `rec-step-${rec.id}-3`,
          order: 3,
          description: "Validate action items",
          input: `${rec.actionItems.length} action items defined`,
          output: `${rec.actionItems.length} concrete actions for implementation`,
          confidence: { level: "medium" as const, score: 0.7, rationale: "Action items are actionable but may need refinement during planning" },
        },
      ]

      const outcomeDescriptions: Record<string, string> = {
        Governance: "Clear decision authority reduces execution delays and prevents bottlenecks",
        Communication: "Regular stakeholder communication ensures alignment and early issue detection",
        Quality: "Continuous validation reduces rework and ensures objective alignment",
        Assessment: "Structured assessment improves decision quality and risk awareness",
      }

      const decision: EnterpriseDecision = {
        ...buildDecisionBase("recommendation", rec.id, `${rec.category}: ${rec.description}`),
        explanation: {
          summary: `${rec.category} recommendation: ${rec.description}. Priority: ${rec.priority}.`,
          detailed: `This ${rec.category.toLowerCase()} recommendation was generated because: ${rec.rationale}. The priority is ${rec.priority}. ${rec.actionItems.length} action items provide concrete implementation steps. Expected outcome: ${outcomeDescriptions[rec.category] || "Improved mission execution quality and risk management"}.`,
          trace: { id: `trace-rec-${rec.id}-${Date.now()}`, steps, conclusion: `${rec.category} recommendation is ${rec.priority} priority with ${rec.actionItems.length} actionable steps`, confidence: { level: "high", score: 0.83, rationale: "Recommendation is well-supported by context, priority, and action items" } },
        },
        evidence: [
          { id: `ev-rec-${rec.id}-1`, source: "Mission Strategy", content: `Priority: ${rec.priority}, Category: ${rec.category}`, relevance: "Strategy provides context for recommendation", confidence: { level: "high", score: 0.85, rationale: "Recommendation derived from strategy analysis" } },
          { id: `ev-rec-${rec.id}-2`, source: "Rationale", content: rec.rationale, relevance: "Direct justification for the recommendation", confidence: { level: "high", score: 0.8, rationale: "Rationale provides clear justification" } },
        ],
        assumptions: [
          { id: `ass-rec-${rec.id}-1`, statement: "Recommended actions can be implemented within existing governance framework", impact: "Framework constraints may limit implementation options", confidence: "medium" },
          { id: `ass-rec-${rec.id}-2`, statement: "Stakeholders will support and adopt the recommendation", impact: "Lack of adoption would reduce recommendation effectiveness", confidence: "medium" },
        ],
        alternatives: [
          {
            id: `alt-rec-${rec.id}-1`,
            title: `Defer ${rec.category} Recommendation`,
            description: `Postpone ${rec.category.toLowerCase()} actions to a later phase`,
            pros: ["Reduces initial workload", "Allows more time for planning"],
            cons: ["May miss critical early actions", "Increased risk exposure", "Harder to implement retroactively"],
            rationale: `Not recommended because ${rec.category.toLowerCase()} actions are most effective when addressed early`,
            confidence: { level: "low", score: 0.3, rationale: "Deferral increases risk and reduces effectiveness" },
          },
        ],
        confidence: { level: "high", score: 0.83, rationale: "Recommendation is supported by clear rationale, priority alignment, and actionable steps" },
      }

      return decision
    })
  },
}
