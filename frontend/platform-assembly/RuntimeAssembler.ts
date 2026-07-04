import { type AssemblyContext, type AssemblyStatus, type PlatformModuleRecord, AssemblyState } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"
import { ModuleLoader } from "./ModuleLoader"
import { DependencyAssembler } from "./DependencyAssembler"
import { generateId } from "./shared"

let context: AssemblyContext | null = null

export const RuntimeAssembler = {
  async assemble(): Promise<AssemblyContext> {
    const modules = await PlatformRegistry.listModules()
    context = {
      id: generateId("assembly"),
      modules,
      state: AssemblyState.ASSEMBLING,
      status: "unknown" as AssemblyStatus,
      assembledAt: null,
      startedAt: new Date().toISOString(),
    }
    return context
  },

  async getRuntimeTree(): Promise<{ foundation: string[]; kernel: string[]; runtime: string[]; workers: string[]; mission: string[]; enterprise: string[]; connectors: string[] }> {
    const modules = await PlatformRegistry.listModules()
    return {
      foundation: modules.filter((m) => m.category === "foundation").map((m) => m.id),
      kernel: modules.filter((m) => m.category === "kernel").map((m) => m.id),
      runtime: modules.filter((m) => m.category === "runtime").map((m) => m.id),
      workers: modules.filter((m) => m.category === "worker").map((m) => m.id),
      mission: modules.filter((m) => m.category === "mission").map((m) => m.id),
      enterprise: modules.filter((m) => m.category === "enterprise" || m.category === "cognitive" || m.category === "integration").map((m) => m.id),
      connectors: modules.filter((m) => m.category === "connector").map((m) => m.id),
    }
  },

  async getContext(): Promise<AssemblyContext | null> {
    return context
  },

  async updateState(state: AssemblyState, status: AssemblyStatus): Promise<void> {
    if (context) {
      context = { ...context, state, status, assembledAt: state === AssemblyState.ASSEMBLED ? new Date().toISOString() : context.assembledAt }
    }
  },
}