import type { AssemblyHealth } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"
import { DependencyAssembler } from "./DependencyAssembler"

export const PlatformHealth = {
  async check(): Promise<AssemblyHealth> {
    const modules = await PlatformRegistry.listModules()
    const deps = await DependencyAssembler.assemble()
    const cycles = await DependencyAssembler.detectCycles()

    const loadedModules = modules.filter((m) => m.loaded).length
    const activeModules = modules.filter((m) => m.initialized).length
    const dependencyReady = deps.every((d) => d.resolved) && cycles.length === 0
    const moduleReady = modules.every((m) => m.loaded)
    const platformReady = dependencyReady && moduleReady

    return {
      platformReady,
      moduleReady,
      dependencyReady,
      assemblyReady: platformReady,
      recoveryReady: !platformReady,
      totalModules: modules.length,
      loadedModules,
      activeModules,
      lastError: cycles.length > 0 ? `circular dependencies found` : null,
    }
  },
}