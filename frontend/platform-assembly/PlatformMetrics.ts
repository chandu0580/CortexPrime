import type { AssemblyMetrics } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"
import { DependencyAssembler } from "./DependencyAssembler"

let assemblyStartTime = 0

export const PlatformMetrics = {
  async collect(): Promise<AssemblyMetrics> {
    const modules = await PlatformRegistry.listModules()
    const deps = await DependencyAssembler.assemble()
    const loadedModules = modules.filter((m) => m.loaded).length
    const dependencyCount = deps.reduce((sum, d) => sum + d.dependsOn.length, 0)
    const assemblyDurationMs = assemblyStartTime > 0 ? Date.now() - assemblyStartTime : 0
    const coverage = modules.length > 0 ? Math.round((loadedModules / modules.length) * 100) : 0

    return {
      registeredModules: modules.length,
      loadedModules,
      assemblyDurationMs,
      dependencyCount,
      coverage,
      startupReady: loadedModules === modules.length,
    }
  },

  async recordAssemblyStart(): Promise<void> {
    assemblyStartTime = Date.now()
  },
}