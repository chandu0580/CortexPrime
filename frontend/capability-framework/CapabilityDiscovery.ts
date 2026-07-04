import type { CapabilityDefinition, CapabilityStatus } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export interface DiscoveryFilter {
  category?: string
  type?: string
  status?: CapabilityStatus
  tag?: string
  feature?: string
  query?: string
}

export interface DiscoveryResult {
  definition: CapabilityDefinition
  relevance: number
  matchedOn: string[]
}

export const CapabilityDiscovery = {
  async discover(filter: DiscoveryFilter): Promise<DiscoveryResult[]> {
    const all = await CapabilityRegistry.list()
    const results: DiscoveryResult[] = []

    for (const definition of all) {
      const matchedOn: string[] = []

      if (filter.category && definition.descriptor.category === filter.category) {
        matchedOn.push("category")
      }

      if (filter.type && definition.descriptor.type === filter.type) {
        matchedOn.push("type")
      }

      if (filter.status && definition.descriptor.status === filter.status) {
        matchedOn.push("status")
      }

      if (filter.tag && definition.descriptor.tags.includes(filter.tag)) {
        matchedOn.push("tag")
      }

      if (filter.feature) {
        const hasFeature = definition.stages.some((s) =>
          s.tags.includes(filter.feature!) || s.name.toLowerCase().includes(filter.feature!.toLowerCase()),
        )
        if (hasFeature) matchedOn.push("feature")
      }

      if (filter.query) {
        const q = filter.query.toLowerCase()
        const matchesName = definition.descriptor.name.toLowerCase().includes(q)
        const matchesDescription = definition.descriptor.description.toLowerCase().includes(q)
        const matchesMetadata = definition.metadata.displayName.toLowerCase().includes(q)
        if (matchesName || matchesDescription || matchesMetadata) {
          matchedOn.push("query")
        }
      }

      if (matchedOn.length > 0 || Object.keys(filter).length === 0) {
        const relevance = matchedOn.length / Math.max(Object.keys(filter).length, 1)
        results.push({ definition, relevance, matchedOn })
      }
    }

    return results.sort((a, b) => b.relevance - a.relevance)
  },

  async discoverByType(type: string): Promise<CapabilityDefinition[]> {
    const results = await this.discover({ type })
    return results.map((r) => r.definition)
  },

  async discoverByCategory(category: string): Promise<CapabilityDefinition[]> {
    const results = await this.discover({ category })
    return results.map((r) => r.definition)
  },

  async discoverByTag(tag: string): Promise<CapabilityDefinition[]> {
    const results = await this.discover({ tag })
    return results.map((r) => r.definition)
  },

  async search(query: string): Promise<CapabilityDefinition[]> {
    const results = await this.discover({ query })
    return results.map((r) => r.definition)
  },

  async getCapabilitySummary(capabilityId: string): Promise<Record<string, unknown> | null> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) return null

    return {
      id: definition.id,
      name: definition.descriptor.name,
      type: definition.descriptor.type,
      version: definition.descriptor.version,
      status: definition.descriptor.status,
      category: definition.descriptor.category,
      stageCount: definition.stages.length,
      requirementCount: definition.requirements.length,
      dependencyCount: definition.dependencies.length,
      policyCount: definition.policies.length,
      features: definition.configuration.features,
      maintainers: definition.metadata.maintainers,
      tags: definition.descriptor.tags,
    }
  },
}
