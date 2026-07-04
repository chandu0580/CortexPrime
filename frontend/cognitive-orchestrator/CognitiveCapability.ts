import type { CognitiveCapabilityDefinition, CognitiveStage, CoordinationStrategy, RoutingPolicy } from "./types"
import type { CapabilityDefinition, CapabilityStage, CapabilityStageType } from "@/capability-framework/types"
import { generateId } from "@/worker-framework/shared"

const DEFAULT_STAGES: CognitiveStage[] = [
  "intake",
  "context_build",
  "memory_retrieval",
  "knowledge_resolution",
  "worker_coordination",
  "world_state_update",
  "validation",
  "completion",
]

const DEFAULT_STRATEGIES: CoordinationStrategy[] = [
  "sequential",
  "parallel",
  "conditional",
  "broadcast",
]

const DEFAULT_POLICIES: RoutingPolicy[] = [
  "auto",
  "skip_on_success",
  "retry_on_failure",
  "terminate_on_failure",
]

export class CognitiveCapability {
  private readonly definition: CognitiveCapabilityDefinition

  constructor(existingDefinition?: CognitiveCapabilityDefinition) {
    this.definition = existingDefinition ?? {
      id: `cognitive-orchestrator-capability-${Date.now()}`,
      name: "Cognitive Orchestrator Capability",
      description: "Deterministic cognitive orchestration across memory, knowledge graph, world state, and workers",
      capabilities: [
        "cognition.pipeline",
        "cognition.routing",
        "cognition.context",
        "cognition.coordination",
        "cognition.validation",
        "cognition.state",
      ],
      stages: DEFAULT_STAGES,
      strategies: DEFAULT_STRATEGIES,
      policies: DEFAULT_POLICIES,
      version: "1.0.0",
    }
  }

  getDefinition(): CognitiveCapabilityDefinition {
    return structuredClone(this.definition)
  }

  toCapabilityDefinition(): CapabilityDefinition {
    const stageTypeMap: Record<CognitiveStage, CapabilityStageType> = {
      intake: "setup",
      context_build: "setup",
      memory_retrieval: "execute",
      knowledge_resolution: "execute",
      worker_coordination: "execute",
      world_state_update: "execute",
      validation: "validate",
      completion: "output",
    }

    const stages: CapabilityStage[] = this.definition.stages.map((s, i) => ({
      id: `cog-stage-${s}`,
      name: s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
      description: `Cognitive orchestration stage: ${s}`,
      type: stageTypeMap[s],
      order: i + 1,
      timeoutMs: 30000,
      maxRetries: 3,
      inputKeys: [s],
      outputKeys: [`${s}_result`],
      required: true,
      tags: ["cognition", s],
    }))

    return {
      id: generateId("cog-capability"),
      descriptor: {
        id: generateId("cog-capability-descriptor"),
        name: this.definition.name,
        type: "cognitive-orchestrator",
        version: this.definition.version,
        description: this.definition.description,
        category: "orchestration",
        tags: ["cognition", "orchestration"],
        icon: "cognitive",
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
        category: "orchestration",
        tags: ["cognition", "orchestration"],
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
