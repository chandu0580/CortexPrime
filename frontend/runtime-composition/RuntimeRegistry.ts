import { RuntimeCompositionState } from "./types"
import type { RuntimeModule, RuntimeModuleType } from "./types"
import { generateId } from "./shared"

const modules = new Map<string, RuntimeModule>()

export const RuntimeRegistry = {
  async registerModule(
    name: string,
    version: string,
    type: RuntimeModuleType,
    dependencies: string[] = [],
  ): Promise<RuntimeModule> {
    const id = generateId("rtmod")
    // eslint-disable-next-line @next/next/no-assign-module-variable
    const module: RuntimeModule = {
      id, name, version, type, dependencies,
      state: RuntimeCompositionState.PENDING,
      startedAt: null, completedAt: null,
    }
    modules.set(id, module)
    return module
  },

  async getModule(moduleId: string): Promise<RuntimeModule | null> {
    return modules.get(moduleId) ?? null
  },

  async listModules(): Promise<RuntimeModule[]> {
    return Array.from(modules.values())
  },

  async listModulesByType(type: RuntimeModuleType): Promise<RuntimeModule[]> {
    return Array.from(modules.values()).filter((m) => m.type === type)
  },

  async updateModuleState(moduleId: string, state: RuntimeCompositionState): Promise<RuntimeModule | null> {
    const mod = modules.get(moduleId)
    if (!mod) return null
    const now = new Date().toISOString()
    const updated: RuntimeModule = {
      ...mod, state,
      startedAt: state === RuntimeCompositionState.INITIALIZING ? now : mod.startedAt,
      completedAt: state === RuntimeCompositionState.ACTIVE ? now : mod.completedAt,
    }
    modules.set(moduleId, updated)
    return updated
  },

  async clear(): Promise<void> {
    modules.clear()
  },
}
