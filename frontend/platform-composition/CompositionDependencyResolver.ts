import type { CompositionDependency } from "./types"; import { DependencyType } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"
import { CompositionGraph } from "./CompositionGraph"

export const CompositionDependencyResolver = {
  async resolveDependencies(): Promise<{ resolved: CompositionDependency[]; missing: string[]; cycles: string[][] }> {
    const modules = await CompositionRegistry.listModules()
    const resolved: CompositionDependency[] = []
    const missing: string[] = []

    for (const m of modules) {
      for (const dep of m.dependencies) {
        const depModule = await CompositionRegistry.getModule(dep)
        if (!depModule) {
          if (!missing.includes(dep)) missing.push(dep)
        }
      }
      resolved.push({
        moduleId: m.moduleId,
        dependsOn: m.dependencies,
        type: DependencyType.HARD,
        resolved: m.dependencies.every((d) => modules.some((mod) => mod.moduleId === d)),
      })
    }

    const cycles = await CompositionGraph.detectCycles()
    return { resolved, missing, cycles }
  },

  async detectMissingDependencies(): Promise<string[]> {
    const { missing } = await this.resolveDependencies()
    return missing
  },

  async detectCycles(): Promise<string[][]> {
    return CompositionGraph.detectCycles()
  },

  async detectInvalidOrdering(): Promise<string[]> {
    const sorted = await CompositionGraph.topologicalSort()
    const modules = await CompositionRegistry.listModules()
    const invalid: string[] = []
    for (const m of modules) {
      const moduleIndex = sorted.indexOf(m.moduleId)
      if (moduleIndex < 0) {
        invalid.push(m.moduleId)
        continue
      }
      for (const dep of m.dependencies) {
        const depIndex = sorted.indexOf(dep)
        if (depIndex > moduleIndex) {
          invalid.push(`${m.moduleId} depends on ${dep} but appears after it in topological order`)
        }
      }
    }
    return invalid
  },

  async getLoadOrder(): Promise<string[]> {
    return CompositionGraph.topologicalSort()
  },
}
