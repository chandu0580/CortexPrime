import type { CapabilityDependency, CapabilityDefinition, DependencyType } from "./types"
import { CapabilityRegistry } from "./CapabilityRegistry"

export interface ResolvedDependency {
  dependency: CapabilityDependency
  definition: CapabilityDefinition | null
  resolved: boolean
  missingFeatures: string[]
}

interface ResolutionGraph {
  resolved: ResolvedDependency[]
  order: string[]
  circular: string[][]
}

export const CapabilityDependencyResolver = {
  async resolve(capabilityId: string): Promise<ResolutionGraph> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }

    const resolved: ResolvedDependency[] = []
    const visited = new Set<string>()
    const visiting = new Set<string>()
    const circular: string[][] = []
    const order: string[] = []

    for (const dep of definition.dependencies) {
      const resolvedDep = await this.resolveSingle(dep)
      resolved.push(resolvedDep)

      if (resolvedDep.resolved && dep.type !== "optional") {
        await this.detectCircular(capabilityId, dep.capabilityId, visited, visiting, circular, [capabilityId])
      }
    }

    const hardDeps = resolved
      .filter((r) => r.dependency.type === "hard" && r.resolved)
      .map((r) => r.dependency.capabilityId)

    const softDeps = resolved
      .filter((r) => r.dependency.type === "soft" && r.resolved)
      .map((r) => r.dependency.capabilityId)

    order.push(...hardDeps, ...softDeps)

    return { resolved, order, circular }
  },

  async resolveSingle(dependency: CapabilityDependency): Promise<ResolvedDependency> {
    const definition = await CapabilityRegistry.get(dependency.capabilityId)
    if (!definition) {
      return {
        dependency,
        definition: null,
        resolved: false,
        missingFeatures: dependency.requiredFeatures,
      }
    }

    if (definition.descriptor.status !== "active") {
      return {
        dependency,
        definition,
        resolved: dependency.optional,
        missingFeatures: dependency.requiredFeatures,
      }
    }

    const missingFeatures = dependency.requiredFeatures.filter(
      (f) => !definition.descriptor.tags.includes(f),
    )

    return {
      dependency,
      definition,
      resolved: missingFeatures.length === 0,
      missingFeatures,
    }
  },

  async resolveAll(ids: string[]): Promise<Map<string, ResolutionGraph>> {
    const results = new Map<string, ResolutionGraph>()
    for (const id of ids) {
      results.set(id, await this.resolve(id))
    }
    return results
  },

  async getDependencyChain(capabilityId: string): Promise<string[]> {
    const graph = await this.resolve(capabilityId)
    const chain: string[] = [capabilityId]
    for (const depId of graph.order) {
      chain.push(depId)
      const subGraph = await this.resolve(depId)
      chain.push(...subGraph.order)
    }
    return chain
  },

  async findHardDependencies(capabilityId: string): Promise<CapabilityDependency[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return definition.dependencies.filter((d) => d.type === "hard")
  },

  async findSoftDependencies(capabilityId: string): Promise<CapabilityDependency[]> {
    const definition = await CapabilityRegistry.get(capabilityId)
    if (!definition) {
      throw new Error(`Capability ${capabilityId} is not registered`)
    }
    return definition.dependencies.filter((d) => d.type === "soft")
  },

  async detectCircular(
    current: string,
    target: string,
    visited: Set<string>,
    visiting: Set<string>,
    circular: string[][],
    path: string[],
  ): Promise<void> {
    if (visiting.has(target)) {
      const cycleStart = path.indexOf(target)
      if (cycleStart !== -1) {
        circular.push([...path.slice(cycleStart), target])
      }
      return
    }

    if (visited.has(target)) return

    visiting.add(target)
    path.push(target)

    const targetDef = await CapabilityRegistry.get(target)

    if (targetDef) {
      for (const dep of targetDef.dependencies.filter((d) => d.type === "hard")) {
        await this.detectCircular(target, dep.capabilityId, visited, visiting, circular, path)
      }
    }

    visiting.delete(target)
    visited.add(target)
    path.pop()
  },
}
