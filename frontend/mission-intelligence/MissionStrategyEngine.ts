import type { MissionAnalysis } from "@/types/intelligence"
import type { MissionStrategy, MissionPhase, MissionRecommendation } from "./types"

function generateId(): string {
  return `strat-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

function deriveApproach(domain: string, priority: string): string {
  if (priority === "critical") return "Expedited execution with executive oversight and dedicated resources"
  if (priority === "high") return "Structured phased delivery with regular stakeholder reviews"
  if (priority === "medium") return "Standard delivery lifecycle with milestone-based checkpoints"
  return "Exploratory approach with iterative validation and adaptive planning"
}

function buildPhases(analysis: MissionAnalysis): MissionPhase[] {
  const phases: MissionPhase[] = [
    {
      id: `phase-init-${generateId()}`,
      name: "Initiation",
      description: "Define objectives, secure resources, and establish governance",
      order: 1,
      status: "pending",
      tasks: [
        {
          id: `task-init-${generateId()}`,
          name: "Objective Validation",
          description: `Validate business objective: ${analysis.context.businessGoal}`,
          assignedCapability: null,
          estimatedEffort: "1 week",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-init-${generateId()}`,
          name: "Stakeholder Alignment",
          description: `Align stakeholders: ${analysis.context.stakeholders.join(", ")}`,
          assignedCapability: null,
          estimatedEffort: "1 week",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-init-${generateId()}`,
          name: "Resource Planning",
          description: "Identify and allocate required resources for execution",
          assignedCapability: null,
          estimatedEffort: "3 days",
          dependsOn: [],
          status: "pending",
        },
      ],
    },
    {
      id: `phase-plan-${generateId()}`,
      name: "Planning",
      description: "Detailed planning, risk assessment, and capability allocation",
      order: 2,
      status: "pending",
      tasks: [
        {
          id: `task-plan-${generateId()}`,
          name: "Detailed Plan Development",
          description: "Develop comprehensive execution plan with milestones",
          assignedCapability: null,
          estimatedEffort: "2 weeks",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-plan-${generateId()}`,
          name: "Risk Mitigation Strategy",
          description: "Develop mitigation strategies for identified risks",
          assignedCapability: null,
          estimatedEffort: "1 week",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-plan-${generateId()}`,
          name: "Capability Readiness",
          description: `Ensure capabilities ready: ${analysis.preview.suggestedCapabilities.join(", ")}`,
          assignedCapability: null,
          estimatedEffort: "1 week",
          dependsOn: [],
          status: "pending",
        },
      ],
    },
    {
      id: `phase-exec-${generateId()}`,
      name: "Execution",
      description: "Execute mission tasks, monitor progress, and adapt as needed",
      order: 3,
      status: "pending",
      tasks: [
        {
          id: `task-exec-${generateId()}`,
          name: "Core Execution",
          description: `Execute mission for domain: ${analysis.context.businessDomain}`,
          assignedCapability: null,
          estimatedEffort: analysis.assessment.estimatedDuration,
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-exec-${generateId()}`,
          name: "Progress Monitoring",
          description: "Track progress against defined key results and milestones",
          assignedCapability: null,
          estimatedEffort: "Ongoing",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-exec-${generateId()}`,
          name: "Constraint Management",
          description: `Manage constraints: ${analysis.context.constraints.join(", ")}`,
          assignedCapability: null,
          estimatedEffort: "Ongoing",
          dependsOn: [],
          status: "pending",
        },
      ],
    },
    {
      id: `phase-review-${generateId()}`,
      name: "Review & Close",
      description: "Validate outcomes, document learnings, and close mission",
      order: 4,
      status: "pending",
      tasks: [
        {
          id: `task-review-${generateId()}`,
          name: "Outcome Validation",
          description: `Validate outcomes against success criteria: ${analysis.context.successCriteria.join(", ")}`,
          assignedCapability: null,
          estimatedEffort: "1 week",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-review-${generateId()}`,
          name: "Knowledge Capture",
          description: "Document learnings, artifacts, and institutional knowledge",
          assignedCapability: null,
          estimatedEffort: "3 days",
          dependsOn: [],
          status: "pending",
        },
        {
          id: `task-review-${generateId()}`,
          name: "Mission Close",
          description: "Formal mission closure, stakeholder sign-off, and reporting",
          assignedCapability: null,
          estimatedEffort: "2 days",
          dependsOn: [],
          status: "pending",
        },
      ],
    },
  ]

  return phases
}

export const MissionStrategyEngine = {
  async buildStrategy(analysis: MissionAnalysis): Promise<MissionStrategy> {
    const phases = buildPhases(analysis)
    const priority = analysis.context.priority
    const domain = analysis.context.businessDomain

    const recommendations: MissionRecommendation[] = [
      {
        id: `rec-strat-${generateId()}`,
        category: "Governance",
        priority,
        description: "Establish clear decision authority and escalation paths",
        rationale: "Structured governance reduces decision latency and prevents bottlenecks",
        actionItems: [
          "Define decision authority matrix",
          "Establish escalation criteria",
          "Schedule recurring governance reviews",
        ],
      },
      {
        id: `rec-comm-${generateId()}`,
        category: "Communication",
        priority,
        description: "Maintain regular stakeholder communication cadence",
        rationale: "Transparent communication ensures alignment and early issue detection",
        actionItems: [
          "Set up weekly status updates",
          "Define stakeholder communication channels",
          "Create issue escalation protocol",
        ],
      },
      {
        id: `rec-qual-${generateId()}`,
        category: "Quality",
        priority,
        description: "Implement continuous validation against success criteria",
        rationale: "Early validation reduces rework and ensures alignment with objectives",
        actionItems: [
          "Define quality gates for each phase",
          "Implement automated validation where possible",
          "Schedule phase-end reviews",
        ],
      },
      ...analysis.assessment.recommendations.map((rec, i) => ({
        id: `rec-assess-${generateId()}`,
        category: "Assessment",
        priority,
        description: rec,
        rationale: `Derived from opportunity assessment`,
        actionItems: [
          `Review and incorporate: ${rec}`,
          "Assign owner for follow-through",
          "Track resolution in mission plan",
        ],
      })),
    ]

    const strategy: MissionStrategy = {
      id: `strategy-${generateId()}`,
      title: `Strategy: ${analysis.preview.title}`,
      objective: analysis.context.businessGoal,
      approach: deriveApproach(domain, priority),
      phases,
      timeline: analysis.assessment.estimatedDuration,
      priority,
      keyResults: analysis.context.successCriteria,
      recommendations,
    }

    return strategy
  },
}
