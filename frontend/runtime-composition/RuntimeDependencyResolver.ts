import { RuntimeCompositionStrategy } from "./types"
import type { RuntimeDependency, RuntimeExecutionOrder } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"
import { RuntimeCompositionGraph } from "./RuntimeCompositionGraph"
import { generateId } from "./shared"

export const RuntimeDependencyResolver = {
  async resolveDependencies(): Promise<{ resolved: RuntimeDependency[]; missing: string[]; cycles: string[][] }> {
    const modules = await RuntimeRegistry.listModules()
    const resolved: RuntimeDependency[] = []
    const missing: string[] = []

    for (const mod of modules) {
      for (const dep of mod.dependencies) {
        if (!modules.some((m) => m.id === dep) && !missing.includes(dep)) missing.push(dep)
      }
      resolved.push({
        moduleId: mod.id,
        dependsOn: mod.dependencies,
        resolved: mod.dependencies.every((d) => modules.some((m) => m.id === d)),
      })
    }

    const cycles = await RuntimeCompositionGraph.detectCycles()
    return { resolved, missing, cycles }
  },

  async detectMissingModules(): Promise<string[]> {
    const { missing } = await this.resolveDependencies()
    return missing
  },

  async generateExecutionOrder(strategy: RuntimeCompositionStrategy = RuntimeCompositionStrategy.TOPOLOGICAL): Promise<RuntimeExecutionOrder> {
    const moduleIds = await RuntimeCompositionGraph.getExecutionOrder()
    const { missing } = await this.resolveDependencies()
    return {
      id: generateId("exec"),
      moduleIds,
      strategy,
      valid: missing.length === 0 && moduleIds.length > 0,
    }
  },

  async validateDependencyGraph(): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = []
    const { missing, cycles } = await this.resolveDependencies()
    if (missing.length > 0) errors.push(`missing runtime modules: ${missing.join(", ")}`)
    if (cycles.length > 0) errors.push(`circular dependencies: ${JSON.stringify(cycles)}`)
    return { valid: errors.length === 0, errors }
  },
}
