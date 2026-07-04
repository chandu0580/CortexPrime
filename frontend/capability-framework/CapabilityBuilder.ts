import type { CapabilityDefinition, CapabilityStage, CapabilityStageType } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export const CapabilityBuilder = {
  async addStage(capabilityId: string, stage: CapabilityStage): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    if (definition.stages.some((s) => s.id === stage.id)) {
      throw new Error(`Stage ${stage.id} already exists in capability ${capabilityId}`)
    }

    definition.stages.push(stage)
    definition.stages.sort((a, b) => a.order - b.order)
    definition.updatedAt = new Date().toISOString()
  },

  async removeStage(capabilityId: string, stageId: string): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    const index = definition.stages.findIndex((s) => s.id === stageId)
    if (index === -1) {
      throw new Error(`Stage ${stageId} not found in capability ${capabilityId}`)
    }

    definition.stages.splice(index, 1)
    definition.updatedAt = new Date().toISOString()
  },

  async getStages(capabilityId: string): Promise<CapabilityStage[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return [...definition.stages].sort((a, b) => a.order - b.order)
  },

  async getStagesByType(capabilityId: string, type: CapabilityStageType): Promise<CapabilityStage[]> {
    const stages = await this.getStages(capabilityId)
    return stages.filter((s) => s.type === type)
  },

  async buildExecutionPlan(capabilityId: string): Promise<CapabilityStage[]> {
    const stages = await this.getStages(capabilityId)
    const required = stages.filter((s) => s.required)
    const optional = stages.filter((s) => !s.required)

    return [...required, ...optional].sort((a, b) => a.order - b.order)
  },

  async addRequirement(capabilityId: string, requirement: CapabilityDefinition["requirements"][0]): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    if (definition.requirements.some((r) => r.id === requirement.id)) {
      throw new Error(`Requirement ${requirement.id} already exists in capability ${capabilityId}`)
    }

    definition.requirements.push(requirement)
    definition.updatedAt = new Date().toISOString()
  },

  async addConstraint(capabilityId: string, constraint: CapabilityDefinition["constraints"][0]): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    if (definition.constraints.some((c) => c.id === constraint.id)) {
      throw new Error(`Constraint ${constraint.id} already exists in capability ${capabilityId}`)
    }

    definition.constraints.push(constraint)
    definition.updatedAt = new Date().toISOString()
  },

  async addPolicy(capabilityId: string, policy: CapabilityDefinition["policies"][0]): Promise<void> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    if (definition.policies.some((p) => p.id === policy.id)) {
      throw new Error(`Policy ${policy.id} already exists in capability ${capabilityId}`)
    }

    definition.policies.push(policy)
    definition.policies.sort((a, b) => b.priority - a.priority)
    definition.updatedAt = new Date().toISOString()
  },

  async createFromTemplate(template: Partial<CapabilityDefinition>): Promise<CapabilityDefinition> {
    const now = new Date().toISOString()
    return {
      id: template.id ?? `cap-${Date.now()}`,
      descriptor: {
        id: template.descriptor?.id ?? `cap-${Date.now()}`,
        name: template.descriptor?.name ?? "",
        type: template.descriptor?.type ?? "custom",
        version: template.descriptor?.version ?? "1.0.0",
        description: template.descriptor?.description ?? "",
        category: template.descriptor?.category ?? "uncategorized",
        tags: template.descriptor?.tags ?? [],
        icon: template.descriptor?.icon ?? "",
        provider: template.descriptor?.provider ?? "",
        status: template.descriptor?.status ?? "active",
        createdAt: now,
        updatedAt: now,
      },
      stages: template.stages ?? [],
      requirements: template.requirements ?? [],
      constraints: template.constraints ?? [],
      policies: template.policies ?? [],
      configuration: template.configuration ?? {
        settings: {},
        defaults: {},
        overrides: {},
        environment: {},
        features: {},
        timeouts: {},
        limits: {},
      },
      dependencies: template.dependencies ?? [],
      metadata: template.metadata ?? {
        displayName: "",
        description: "",
        category: "uncategorized",
        tags: [],
        provider: "",
        homepage: "",
        documentation: "",
        license: "",
        maintainers: [],
        changelog: [],
      },
      createdAt: now,
      updatedAt: now,
    }
  },
}
