import type { MissionAnalysis } from "@/types/intelligence"
import type { MissionRisk, ImpactLevel } from "./types"

function generateId(): string {
  return `risk-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

function inferLikelihood(priority: string, baseScore: number): number {
  const multiplier = priority === "critical" ? 1.3
    : priority === "high" ? 1.15
    : priority === "medium" ? 1.0
    : 0.85
  return Math.min(Math.round(baseScore * multiplier * 10) / 10, 1)
}

function inferImpact(priority: string): ImpactLevel {
  switch (priority) {
    case "critical": return "critical"
    case "high": return "high"
    case "medium": return "medium"
    case "low": return "low"
    default: return "medium"
  }
}

export const MissionRiskEngine = {
  async evaluateRisks(analysis: MissionAnalysis): Promise<MissionRisk[]> {
    const priority = analysis.context.priority
    const impact = inferImpact(priority)

    const risks: MissionRisk[] = [
      {
        id: `risk-scope-${generateId()}`,
        category: "Scope",
        description: "Scope creep without clearly defined boundaries",
        likelihood: inferLikelihood(priority, 0.7),
        impact,
        mitigation: "Establish strict change control process and define scope boundaries upfront",
        owner: "Business Owner",
      },
      {
        id: `risk-resource-${generateId()}`,
        category: "Resource",
        description: "Resource contention with existing commitments",
        likelihood: inferLikelihood(priority, 0.6),
        impact,
        mitigation: "Conduct resource capacity planning and secure commitments before execution",
        owner: "Technical Lead",
      },
      {
        id: `risk-align-${generateId()}`,
        category: "Stakeholder",
        description: "Stakeholder misalignment on success criteria",
        likelihood: inferLikelihood(priority, 0.5),
        impact,
        mitigation: "Document and validate success criteria with all stakeholders in Initiation phase",
        owner: "Project Manager",
      },
      {
        id: `risk-tech-${generateId()}`,
        category: "Technical",
        description: `Technical complexity in domain: ${analysis.context.businessDomain}`,
        likelihood: inferLikelihood(priority, 0.55),
        impact: "high",
        mitigation: "Engage domain experts early and prototype critical components",
        owner: "Technical Lead",
      },
      {
        id: `risk-sched-${generateId()}`,
        category: "Schedule",
        description: `Schedule risk due to estimated duration: ${analysis.assessment.estimatedDuration}`,
        likelihood: inferLikelihood(priority, 0.6),
        impact,
        mitigation: "Build buffer into timeline and track milestones weekly",
        owner: "Project Manager",
      },
    ]

    return risks
  },
}
