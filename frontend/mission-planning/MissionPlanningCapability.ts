import type { PlanningCapabilityDefinition } from "./types"
import type { CapabilityDefinition, CapabilityStage, CapabilityStageType } from "@/capability-framework/types"
import { generateId } from "@/worker-framework/shared"

export class MissionPlanningCapability {
  private readonly definition: PlanningCapabilityDefinition

  constructor(existingDefinition?: PlanningCapabilityDefinition) {
    this.definition = existingDefinition ?? {
      id: `mission-planning-capability-${Date.now()}`,
      name: "Mission Planning Capability",
      description: "Deterministic mission planning, sequencing, scheduling, prioritization, and portfolio optimization",
      capabilities: [
        "planning.decomposition",
        "planning.priority",
        "planning.resources",
        "planning.timeline",
        "planning.portfolio",
        "planning.optimization",
      ],
      strategies: ["waterfall", "iterative", "parallel", "incremental", "opportunistic"],
      policies: ["strict_priority", "balanced", "resource_first", "deadline_first", "portfolio_aware"],
      version: "1.0.0",
    }
  }

  getDefinition(): PlanningCapabilityDefinition {
    return structuredClone(this.definition)
  }

  toCapabilityDefinition(): CapabilityDefinition {
    const stages: CapabilityStage[] = [
      { id: "plan-stage-decomposition", name: "Decomposition", description: "Decompose mission into phases and tasks", type: "setup" as CapabilityStageType, order: 1, timeoutMs: 30000, maxRetries: 3, inputKeys: ["mission"], outputKeys: ["phases"], required: true, tags: ["planning", "decomposition"] },
      { id: "plan-stage-prioritization", name: "Prioritization", description: "Calculate and assign priorities", type: "execute" as CapabilityStageType, order: 2, timeoutMs: 15000, maxRetries: 2, inputKeys: ["phases"], outputKeys: ["priorities"], required: true, tags: ["planning", "priority"] },
      { id: "plan-stage-resource", name: "Resource Planning", description: "Estimate and reserve resources", type: "execute" as CapabilityStageType, order: 3, timeoutMs: 30000, maxRetries: 3, inputKeys: ["priorities"], outputKeys: ["resources"], required: true, tags: ["planning", "resource"] },
      { id: "plan-stage-timeline", name: "Timeline Planning", description: "Generate execution timeline", type: "execute" as CapabilityStageType, order: 4, timeoutMs: 30000, maxRetries: 3, inputKeys: ["resources"], outputKeys: ["timeline"], required: true, tags: ["planning", "timeline"] },
      { id: "plan-stage-portfolio", name: "Portfolio Optimization", description: "Optimize across portfolio", type: "execute" as CapabilityStageType, order: 5, timeoutMs: 30000, maxRetries: 2, inputKeys: ["timeline"], outputKeys: ["portfolio"], required: false, tags: ["planning", "portfolio"] },
      { id: "plan-stage-validation", name: "Validation", description: "Validate plan completeness", type: "validate" as CapabilityStageType, order: 6, timeoutMs: 15000, maxRetries: 2, inputKeys: ["plan"], outputKeys: ["validation"], required: true, tags: ["planning", "validation"] },
    ]

    return {
      id: generateId("plan-capability"),
      descriptor: {
        id: generateId("plan-capability-descriptor"),
        name: this.definition.name,
        type: "mission-planning",
        version: this.definition.version,
        description: this.definition.description,
        category: "planning",
        tags: ["mission", "planning"],
        icon: "planning",
        provider: "CortexPrime",
        status: "active",
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      },
      stages,
      requirements: [],
      constraints: [],
      policies: [],
      configuration: {
        settings: { strategies: this.definition.strategies, policies: this.definition.policies },
        defaults: {}, overrides: {}, environment: {}, features: {}, timeouts: {}, limits: {},
      },
      dependencies: [],
      metadata: {
        displayName: this.definition.name,
        description: this.definition.description,
        category: "planning",
        tags: ["mission", "planning"],
        provider: "CortexPrime",
        homepage: "", documentation: "", license: "", maintainers: [], changelog: [],
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  }
}
