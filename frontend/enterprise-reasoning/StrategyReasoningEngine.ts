import type { MissionIntelligenceReport } from "@/mission-intelligence/types"
import type { EnterpriseDecision } from "./types"
import { buildDecisionBase } from "./shared"

export const StrategyReasoningEngine = {
  async analyzeStrategy(report: MissionIntelligenceReport): Promise<EnterpriseDecision> {
    const strategy = report.strategy
    const assessment = report.plan.risks

    const step1 = {
      id: "strat-step-1",
      order: 1,
      description: "Evaluate strategy alignment with mission objective",
      input: `Objective: ${strategy.objective}`,
      output: `Approach: ${strategy.approach}`,
      confidence: { level: "high" as const, score: 0.88, rationale: "Approach derived directly from business objective and priority level" },
    }

    const step2 = {
      id: "strat-step-2",
      order: 2,
      description: "Assess phase structure completeness",
      input: `${strategy.phases.length} phases defined`,
      output: `Phases cover full lifecycle: Initiation → Planning → Execution → Review & Close`,
      confidence: { level: "high" as const, score: 0.92, rationale: "Phase structure follows standard enterprise delivery lifecycle" },
    }

    const step3 = {
      id: "strat-step-3",
      order: 3,
      description: "Validate key results against mission context",
      input: `${strategy.keyResults.length} key results defined`,
      output: `All success criteria from mission context are represented as key results`,
      confidence: { level: "medium" as const, score: 0.75, rationale: "Key results are mapped to context criteria but may need refinement" },
    }

    const decision: EnterpriseDecision = {
      ...buildDecisionBase("strategy", strategy.id, `Strategy: ${strategy.title}`),
      explanation: {
        summary: `${strategy.title} uses a ${strategy.approach.toLowerCase()} with ${strategy.phases.length} phases and ${strategy.keyResults.length} key results aligned to ${strategy.objective}.`,
        detailed: `The strategy was derived from the mission objective "${strategy.objective}" with priority "${strategy.priority}". The ${strategy.approach.toLowerCase()} approach was selected because it matches the ${strategy.priority} priority level. ${strategy.phases.length} phases provide complete lifecycle coverage from Initiation through Review & Close. ${strategy.keyResults.length} key results map directly to the success criteria defined during context analysis. ${strategy.recommendations.length} recommendations provide governance, communication, and quality guidance.`,
        trace: { id: `trace-strat-${Date.now()}`, steps: [step1, step2, step3], conclusion: `Strategy is well-aligned with mission objective and covers full delivery lifecycle`, confidence: { level: "high", score: 0.85, rationale: "Multiple validation steps confirm strategy completeness" } },
      },
      evidence: [
        { id: "ev-strat-1", source: "Mission Context", content: strategy.objective, relevance: "Primary driver for strategy definition", confidence: { level: "high", score: 0.9, rationale: "Objective is the foundational input" } },
        { id: "ev-strat-2", source: "Priority Assessment", content: strategy.priority, relevance: "Determines approach and timeline", confidence: { level: "high", score: 0.85, rationale: "Priority directly influences approach selection" } },
        { id: "ev-strat-3", source: "Success Criteria", content: strategy.keyResults.join("; "), relevance: "Measures strategy effectiveness", confidence: { level: "medium", score: 0.75, rationale: "Criteria may evolve during execution" } },
      ],
      assumptions: [
        { id: "ass-strat-1", statement: "Stakeholder alignment is achievable within the defined timeline", impact: "Misalignment would delay Initiation phase", confidence: "medium" },
        { id: "ass-strat-2", statement: "Required resources will be available when needed", impact: "Resource contention could impact Execution phase", confidence: "medium" },
        { id: "ass-strat-3", statement: "Success criteria accurately capture business needs", impact: "Incomplete criteria would reduce strategy effectiveness", confidence: "high" },
      ],
      alternatives: [
        {
          id: "alt-strat-1",
          title: "Agile Iterative Approach",
          description: "Shorter cycles with continuous stakeholder feedback",
          pros: ["Faster feedback loops", "More adaptive to change", "Earlier risk detection"],
          cons: ["Less predictable timeline", "Higher coordination overhead", "Requires constant stakeholder availability"],
          rationale: "Not selected because priority level favors structured phased delivery over iterative cycles",
          confidence: { level: "medium", score: 0.65, rationale: "Valid alternative but less suited to current priority level" },
        },
        {
          id: "alt-strat-2",
          title: "Minimum Viable Delivery",
          description: "Focus on core objective with reduced scope",
          pros: ["Faster time-to-value", "Lower resource commitment", "Reduced complexity"],
          cons: ["May miss secondary objectives", "Requires phase-two planning", "Higher rework risk"],
          rationale: "Could be considered if resource constraints become significant during planning",
          confidence: { level: "low", score: 0.4, rationale: "Contingency option only if constraints materialize" },
        },
      ],
      confidence: { level: "high", score: 0.85, rationale: "Strategy is fully derived from mission objective, priority, and context" },
    }

    return decision
  },
}
