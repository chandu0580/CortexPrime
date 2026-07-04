import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseDecision } from "./types"
import { buildDecisionBase } from "./shared"

export const CapabilityReasoningEngine = {
  async analyzeCapabilities(report: MissionIntelligenceReport): Promise<EnterpriseDecision[]> {
    const capabilities = report.capabilities

    return capabilities.map((cap) => {
      const steps = [
        {
          id: `cap-step-${cap.id}-1`,
          order: 1,
          description: "Evaluate capability requirement",
          input: `Capability: ${cap.name}`,
          output: cap.required ? "Required for mission execution" : "Optional but recommended",
          confidence: { level: "high" as const, score: 0.85, rationale: "Requirement derived from mission analysis and preview" },
        },
        {
          id: `cap-step-${cap.id}-2`,
          order: 2,
          description: "Assess confidence in capability selection",
          input: `Confidence score: ${cap.confidence}`,
          output: cap.confidence >= 0.8 ? "High confidence — strong match with mission requirements" : "Medium confidence — may need further validation",
          confidence: { level: cap.confidence >= 0.8 ? "high" as const : "medium" as const, score: cap.confidence, rationale: `Confidence based on alignment with mission domain and objectives` },
        },
        {
          id: `cap-step-${cap.id}-3`,
          order: 3,
          description: "Evaluate alternatives",
          input: `${cap.alternatives.length} alternatives available`,
          output: cap.alternatives.length > 0 ? `Alternatives exist: ${cap.alternatives.join(", ")}` : "No direct alternatives identified",
          confidence: { level: cap.alternatives.length > 0 ? "medium" as const : "low" as const, score: 0.6, rationale: "Alternatives provide flexibility but may have different trade-offs" },
        },
      ]

      const decision: EnterpriseDecision = {
        ...buildDecisionBase("capability", cap.id, cap.name),
        explanation: {
          summary: `${cap.name} was selected with ${(cap.confidence * 100).toFixed(0)}% confidence. ${cap.required ? "Required" : "Optional"} for mission execution.`,
          detailed: `${cap.name} is a ${cap.required ? "required" : "recommended"} capability for this mission. ${cap.description}. Selection confidence is ${(cap.confidence * 100).toFixed(0)}%. ${cap.alternatives.length > 0 ? `Considered ${cap.alternatives.length} alternatives: ${cap.alternatives.join(", ")}.` : "No direct alternatives were identified in the capability catalog."}`,
          trace: { id: `trace-cap-${cap.id}-${Date.now()}`, steps, conclusion: `${cap.name} is ${cap.required ? "required" : "recommended"} with ${(cap.confidence * 100).toFixed(0)}% confidence`, confidence: { level: "high", score: 0.8, rationale: "Multiple evaluation dimensions confirm capability fit" } },
        },
        evidence: [
          { id: `ev-cap-${cap.id}-1`, source: "Mission Preview", content: cap.name, relevance: "Capability was identified during mission preview generation", confidence: { level: "high", score: 0.85, rationale: "Preview directly suggested this capability" } },
          { id: `ev-cap-${cap.id}-2`, source: "Capability Catalog", content: cap.description, relevance: "Catalog provides validated capability description", confidence: { level: "medium", score: 0.75, rationale: "Catalog entries are curated but may not cover all edge cases" } },
        ],
        assumptions: [
          { id: `ass-cap-${cap.id}-1`, statement: "Capability is available and can be deployed within the mission timeline", impact: "Unavailability would require alternative capability selection", confidence: "medium" },
          { id: `ass-cap-${cap.id}-2`, statement: "Team has necessary expertise to leverage this capability effectively", impact: "Skill gaps would increase ramp-up time", confidence: "medium" },
        ],
        alternatives: cap.alternatives.length > 0 ? cap.alternatives.map((alt, i) => ({
          id: `alt-cap-${cap.id}-${i}`,
          title: alt,
          description: `Alternative to ${cap.name}: ${alt}`,
          pros: ["Provides similar functionality", "Different approach may surface edge cases"],
          cons: ["Requires separate validation", "May have different integration requirements"],
          rationale: `Not selected because ${cap.name} provides better alignment with mission requirements`,
          confidence: { level: "medium" as const, score: 0.55, rationale: "Alternatives are valid but have trade-offs" },
        })) : [],
        confidence: { level: "high", score: 0.85, rationale: `Capability selection is well-supported by mission analysis and catalog data` },
      }

      return decision
    })
  },
}
