import type { EnterpriseDecision } from "@/enterprise-reasoning/types"
import type { DecisionPolicy, PolicyResult } from "./types"
import { generateId } from "./shared"

const policyDefinitions: { name: string; category: string; evaluate: (d: EnterpriseDecision) => PolicyResult; details: (d: EnterpriseDecision) => string }[] = [
  {
    name: "Confidence Threshold",
    category: "Quality",
    evaluate: (d) => d.confidence.score >= 0.7 ? "passed" : d.confidence.score >= 0.5 ? "needs_review" : "failed",
    details: (d) => `Decision confidence is ${(d.confidence.score * 100).toFixed(0)}%. Threshold: 70% pass, 50-69% review, below 50% fail.`,
  },
  {
    name: "Risk Impact Assessment",
    category: "Risk",
    evaluate: (d) => {
      if (d.category !== "risk") return "passed"
      return d.evidence.some((e) => e.content.includes("critical") || e.content.includes("high")) ? "needs_review" : "passed"
    },
    details: (d) => d.category === "risk" ? "Risk-level decisions require additional scrutiny" : "Not a risk decision — automatically passed",
  },
  {
    name: "Evidence Sufficiency",
    category: "Quality",
    evaluate: (d) => d.evidence.length >= 2 ? "passed" : d.evidence.length >= 1 ? "needs_review" : "failed",
    details: (d) => `${d.evidence.length} evidence items provided. Minimum: 2 for pass, 1 for review.`,
  },
  {
    name: "Alternative Consideration",
    category: "Completeness",
    evaluate: (d) => d.alternatives.length >= 1 ? "passed" : "needs_review",
    details: (d) => `${d.alternatives.length} alternatives evaluated. At least 1 recommended.`,
  },
  {
    name: "Assumption Documentation",
    category: "Completeness",
    evaluate: (d) => d.assumptions.length >= 2 ? "passed" : d.assumptions.length >= 1 ? "needs_review" : "failed",
    details: (d) => `${d.assumptions.length} assumptions documented. Minimum: 2 for pass, 1 for review.`,
  },
]

export const PolicyEvaluationEngine = {
  async evaluate(decision: EnterpriseDecision): Promise<DecisionPolicy[]> {
    return policyDefinitions.map((def) => ({
      id: generateId("policy"),
      name: def.name,
      category: def.category,
      evaluation: def.evaluate(decision),
      details: def.details(decision),
    }))
  },
}
