import type { ExecutionCapabilityDefinition, ExecutionStage } from "./types"
import type { CapabilityDefinition, CapabilityStage, CapabilityStageType } from "@/capability-framework/types"
import { generateId } from "@/worker-framework/shared"

const DEFAULT_STAGES: ExecutionStage[] = [
  "decomposition",
  "planning",
  "distribution",
  "dependency_check",
  "validation",
  "execution",
  "monitoring",
  "completion",
]

export class MissionExecutionCapability {
  private readonly definition: ExecutionCapabilityDefinition

  constructor(existingDefinition?: ExecutionCapabilityDefinition) {
    this.definition = existingDefinition ?? {
      id: `mission-execution-capability-${Date.now()}`,
      name: "Mission Execution Capability",
      description: "Deterministic mission execution planning, distribution, and lifecycle management",
      capabilities: [
        "execution.decomposition",
        "execution.planning",
        "execution.distribution",
        "execution.validation",
        "execution.lifecycle",
        "execution.metrics",
      ],
      stages: DEFAULT_STAGES,
      strategies: ["balanced", "sequential", "parallel", "round_robin", "capacity_first"],
      policies: ["single", "multi", "dedicated", "shared"],
      version: "1.0.0",
    }
  }

  getDefinition(): ExecutionCapabilityDefinition {
    return structuredClone(this.definition)
  }

  toCapabilityDefinition(): CapabilityDefinition {
    const stageTypeMap: Record<ExecutionStage, CapabilityStageType> = {
      decomposition: "setup",
      planning: "setup",
      distribution: "setup",
      dependency_check: "validate",
      validation: "validate",
      execution: "execute",
      monitoring: "execute",
      completion: "output",
    }

    const stages: CapabilityStage[] = this.definition.stages.map((s, i) => ({
      id: `exec-stage-${s}`,
      name: s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: `Mission execution stage: ${s}`,
      type: stageTypeMap[s],
      order: i + 1,
      timeoutMs: 60000,
      maxRetries: 3,
      inputKeys: [s],
      outputKeys: [`${s}_result`],
      required: true,
      tags: ["execution", s],
    }))

    return {
      id: generateId("exec-capability"),
      descriptor: {
        id: generateId("exec-capability-descriptor"),
        name: this.definition.name,
        type: "mission-execution",
        version: this.definition.version,
        description: this.definition.description,
        category: "execution",
        tags: ["mission", "execution"],
        icon: "execution",
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
        settings: {
          strategies: this.definition.strategies,
          policies: this.definition.policies,
        },
        defaults: {},
        overrides: {},
        environment: {},
        features: {},
        timeouts: {},
        limits: {},
      },
      dependencies: [],
      metadata: {
        displayName: this.definition.name,
        description: this.definition.description,
        category: "execution",
        tags: ["mission", "execution"],
        provider: "CortexPrime",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: [],
      },
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
  }
}
