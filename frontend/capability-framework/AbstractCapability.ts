import type { PlatformCapability } from "@/platform/contracts"
import type {
  CapabilityDefinition,
  CapabilityDescriptor,
  CapabilityStage,
  CapabilityConfiguration,
  CapabilityRequirement,
  CapabilityConstraint,
  CapabilityPolicy,
  CapabilityDependency,
  CapabilityMetadata,
  CapabilityValidationResult,
} from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"
import { CapabilityBuilder } from "./CapabilityBuilder"
import { CapabilityValidator } from "./CapabilityValidator"
import { CapabilityDependencyResolver, type ResolvedDependency } from "./CapabilityDependencyResolver"
import { CapabilityPolicyManager } from "./CapabilityPolicyManager"
import { CapabilityConfigurationManager } from "./CapabilityConfigurationManager"
import { CapabilityMetadataManager } from "./CapabilityMetadataManager"
import { CapabilityDiscovery } from "./CapabilityDiscovery"

export abstract class AbstractCapability {
  protected abstract createDefinition(): CapabilityDefinition

  async register(): Promise<void> {
    const definition = this.createDefinition()
    await CapabilityRegistry.register(definition)
  }

  async validate(): Promise<CapabilityValidationResult> {
    const definition = this.createDefinition()
    const existing = await CapabilityRegistry.get(definition.id)
    if (!existing) {
      await CapabilityRegistry.register(definition)
    }
    return CapabilityValidator.validate(definition.id)
  }

  abstract buildPipeline(): Promise<CapabilityStage[]>

  async discover(filter?: { category?: string; type?: string; tag?: string }): Promise<CapabilityDefinition[]> {
    return CapabilityDiscovery.discoverByType(filter?.type ?? "")
  }

  async resolveDependencies(): Promise<{
    resolved: ResolvedDependency[]
    order: string[]
    circular: string[][]
  }> {
    const definition = this.createDefinition()
    const existing = await CapabilityRegistry.get(definition.id)
    if (!existing) {
      await CapabilityRegistry.register(definition)
    }
    return CapabilityDependencyResolver.resolve(definition.id)
  }

  async loadConfiguration(): Promise<CapabilityConfiguration> {
    const definition = this.createDefinition()
    return structuredClone(definition.configuration)
  }

  async exportDefinition(): Promise<CapabilityDefinition> {
    return structuredClone(this.createDefinition())
  }

  protected addStage(stage: CapabilityStage): Promise<void> {
    const definition = this.createDefinition()
    return CapabilityBuilder.addStage(definition.id, stage)
  }

  protected addRequirement(requirement: CapabilityRequirement): Promise<void> {
    const definition = this.createDefinition()
    return CapabilityBuilder.addRequirement(definition.id, requirement)
  }

  protected addConstraint(constraint: CapabilityConstraint): Promise<void> {
    const definition = this.createDefinition()
    return CapabilityBuilder.addConstraint(definition.id, constraint)
  }

  protected addPolicy(policy: CapabilityPolicy): Promise<void> {
    const definition = this.createDefinition()
    return CapabilityBuilder.addPolicy(definition.id, policy)
  }

  protected getDescriptor(): CapabilityDescriptor {
    return this.createDefinition().descriptor
  }

  protected getMetadata(): CapabilityMetadata {
    return this.createDefinition().metadata
  }

  protected getPlatformCapabilities(): PlatformCapability[] {
    const definition = this.createDefinition()
    return definition.stages.map((stage) => ({
      id: stage.id,
      name: stage.name,
      type: definition.descriptor.type as PlatformCapability["type"],
      version: definition.descriptor.version,
      features: stage.tags,
      enabled: stage.required,
    }))
  }
}
