import type { RuntimeModuleRecord } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"

const initializedModules = new Set<string>()

export const RuntimeInitializer = {
  async initializeModule(moduleId: string): Promise<boolean> {
    const mod = await RuntimeManifest.getModule(moduleId)
    if (!mod) return false
    initializedModules.add(moduleId)
    return true
  },

  async activateModule(moduleId: string): Promise<boolean> {
    return initializedModules.has(moduleId)
  },

  async initializeAll(order: string[]): Promise<{ initialized: string[]; failed: string[] }> {
    const initialized: string[] = []
    const failed: string[] = []

    for (const moduleId of order) {
      const ok = await this.initializeModule(moduleId)
      if (ok) initialized.push(moduleId)
      else failed.push(moduleId)
    }
    return { initialized, failed }
  },

  async activateAll(order: string[]): Promise<{ activated: string[]; failed: string[] }> {
    const activated: string[] = []
    const failed: string[] = []

    for (const moduleId of order) {
      if (initializedModules.has(moduleId)) activated.push(moduleId)
      else failed.push(moduleId)
    }
    return { activated, failed }
  },

  async rollback(failedModuleId: string, order: string[]): Promise<string[]> {
    const rollbackOrder = [...order].reverse()
    const rolledBack: string[] = []
    const failedIndex = rollbackOrder.indexOf(failedModuleId)
    const toRollback = failedIndex >= 0 ? rollbackOrder.slice(failedIndex) : rollbackOrder

    for (const moduleId of toRollback) {
      initializedModules.delete(moduleId)
      rolledBack.push(moduleId)
    }
    return rolledBack
  },

  async getProgress(): Promise<{ initialized: number; total: number }> {
    const modules = await RuntimeManifest.listModules()
    return { initialized: initializedModules.size, total: modules.length }
  },
}