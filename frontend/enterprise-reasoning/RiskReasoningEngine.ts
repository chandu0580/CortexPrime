import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseDecision } from "./types"
import { buildDecisionBase } from "./shared"

export const RiskReasoningEngine = {
  async analyzeRisks(report: MissionIntelligenceReport): Promise<EnterpriseDecision[]> {
    const risks = report.risks

    return risks.map((risk) => {
      const likelihoodLabel = risk.likelihood >= 0.7 ? "high" : risk.likelihood >= 0.4 ? "medium" : "low"

      const steps = [
        {
          id: `risk-step-${risk.id}-1`,
          order: 1,
          description: "Evaluate risk likelihood",
          input: `Likelihood score: ${risk.likelihood}`,
          output: `${likelihoodLabel} likelihood — ${risk.likelihood >= 0.7 ? "requires active monitoring" : risk.likelihood >= 0.4 ? "standard monitoring recommended" : "low priority but trackable"}`,
          confidence: { level: "high" as const, score: 0.85, rationale: "Likelihood derived from mission priority and domain analysis" },
        },
        {
          id: `risk-step-${risk.id}-2`,
          order: 2,
          description: "Assess risk impact",
          input: `Impact level: ${risk.impact}`,
          output: risk.impact === "critical" ? "Critical impact — requires immediate mitigation planning" : `${risk.impact} impact — standard mitigation sufficient`,
          confidence: { level: "high" as const, score: 0.8, rationale: "Impact assessment based on enterprise risk categorization" },
        },
        {
          id: `risk-step-${risk.id}-3`,
          order: 3,
          description: "Validate mitigation strategy",
          input: `Mitigation: ${risk.mitigation}`,
          output: `Mitigation assigned to ${risk.owner} with defined action plan`,
          confidence: { level: "medium" as const, score: 0.7, rationale: "Mitigation strategy is defined but effectiveness depends on execution" },
        },
      ]

      const decision: EnterpriseDecision = {
        ...buildDecisionBase("risk", risk.id, `${risk.category}: ${risk.description}`),
        explanation: {
          summary: `${risk.category} risk with ${likelihoodLabel} likelihood and ${risk.impact} impact. ${risk.mitigation}`,
          detailed: `This ${risk.category.toLowerCase()} risk was identified because: "${risk.description}". The likelihood is ${likelihoodLabel} (score: ${risk.likelihood}) and the potential impact is ${risk.impact}. The recommended mitigation is: ${risk.mitigation}. Responsibility is assigned to: ${risk.owner}.`,
          trace: { id: `trace-risk-${risk.id}-${Date.now()}`, steps, conclusion: `${risk.category} risk requires ${likelihoodLabel === "high" ? "active" : "standard"} monitoring with ${risk.impact} impact preparation`, confidence: { level: "high", score: 0.82, rationale: "Risk assessment covers likelihood, impact, and mitigation" } },
        },
        evidence: [
          { id: `ev-risk-${risk.id}-1`, source: "Mission Context", content: `Priority: ${report.strategy.priority}`, relevance: "Priority influences risk likelihood scaling", confidence: { level: "high", score: 0.85, rationale: "Priority directly affects risk exposure" } },
          { id: `ev-risk-${risk.id}-2`, source: "Risk Assessment", content: risk.description, relevance: "Core risk definition", confidence: { level: "high", score: 0.8, rationale: "Risk description derived from domain analysis" } },
        ],
        assumptions: [
          { id: `ass-risk-${risk.id}-1`, statement: "Risk mitigation plan can be executed within existing resource constraints", impact: "Resource constraints may limit mitigation effectiveness", confidence: "medium" },
          { id: `ass-risk-${risk.id}-2`, statement: "Risk owner has authority to implement mitigation measures", impact: "Without authority, mitigation may be delayed", confidence: "high" },
        ],
        alternatives: [
          {
            id: `alt-risk-${risk.id}-1`,
            title: "Risk Acceptance",
            description: "Accept the risk without active mitigation",
            pros: ["No resource allocation needed", "Simpler execution path"],
            cons: ["Exposure to potential impact", "May require contingency planning", "Stakeholder concerns may arise"],
            rationale: `Not recommended because ${risk.impact} impact requires active mitigation`,
            confidence: { level: "low", score: 0.35, rationale: "Acceptance is only appropriate for low-impact risks" },
          },
          {
            id: `alt-risk-${risk.id}-2`,
            title: "Risk Transfer",
            description: "Transfer risk to third party or insurance",
            pros: ["Reduces internal exposure", "Leverages external expertise"],
            cons: ["May introduce new dependencies", "Cost implications", "Loss of direct control"],
            rationale: "Not selected because most mission risks are best managed internally",
            confidence: { level: "low", score: 0.3, rationale: "Transfer is only appropriate for specific risk categories" },
          },
        ],
        confidence: { level: "high", score: 0.82, rationale: "Risk assessment is comprehensive with likelihood, impact, and mitigation defined" },
      }

      return decision
    })
  },
}
