import { BootstrapState } from "./types"
import { type BootstrapModule, BootstrapStageType } from "./types"
import { generateId } from "./shared"

const modules = new Map<string, BootstrapModule>()

export const BootstrapRegistry = {
  async registerModule(
    name: string,
    version: string,
    stage: BootstrapStageType,
    dependencies: string[] = [],
  ): Promise<BootstrapModule> {
    const id = generateId("bmod")
    // eslint-disable-next-line @next/next/no-assign-module-variable
    const module: BootstrapModule = {
      id, name, version, stage, dependencies,
      status: BootstrapState.PENDING,
      startedAt: null, completedAt: null,
    }
    modules.set(id, module)
    return module
  },

  async getModule(moduleId: string): Promise<BootstrapModule | null> {
    return modules.get(moduleId) ?? null
  },

  async listModules(): Promise<BootstrapModule[]> {
    return Array.from(modules.values())
  },

  async listModulesByStage(stage: BootstrapStageType): Promise<BootstrapModule[]> {
    return Array.from(modules.values()).filter((m) => m.stage === stage)
  },

  async updateModuleStatus(moduleId: string, status: BootstrapState): Promise<BootstrapModule | null> {
    // eslint-disable-next-line @next/next/no-assign-module-variable
    const module = modules.get(moduleId)
    if (!module) return null
    const now = new Date().toISOString()
    const updated: BootstrapModule = {
      ...module,
      status,
      startedAt: status === BootstrapState.INITIALIZING ? now : module.startedAt,
      completedAt: status === BootstrapState.ACTIVE ? now : module.completedAt,
    }
    modules.set(moduleId, updated)
    return updated
  },

  async clear(): Promise<void> {
    modules.clear()
  },
}
