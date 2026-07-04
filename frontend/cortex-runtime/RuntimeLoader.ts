import type { RuntimeModuleRecord } from "./types"
import { RuntimeManifest } from "./RuntimeManifest"

export const RuntimeLoader = {
  async loadModules(): Promise<{ loaded: RuntimeModuleRecord[]; missing: string[] }> {
    const modules = await RuntimeManifest.listModules()
    const loaded: RuntimeModuleRecord[] = []
    const missing: string[] = []

    for (const mod of modules) {
      try {
        loaded.push(mod)
      } catch {
        missing.push(mod.id)
      }
    }
    return { loaded, missing }
  },

  async resolveDependencies(moduleId: string): Promise<string[]> {
    const mod = await RuntimeManifest.getModule(moduleId)
    if (!mod) return []
    return mod.dependencies
  },

  async determineStartupOrder(): Promise<string[]> {
    const modules = await RuntimeManifest.listModules()
    const required = modules.filter((m) => m.required)
    const adjacency = new Map<string, string[]>()
    const inDegree = new Map<string, number>()

    for (const m of required) {
      adjacency.set(m.id, [])
      inDegree.set(m.id, 0)
    }
    for (const m of required) {
      for (const dep of m.dependencies) {
        adjacency.get(dep)?.push(m.id)
        inDegree.set(m.id, (inDegree.get(m.id) ?? 0) + 1)
      }
    }

    const queue: string[] = []
    for (const [id, degree] of inDegree) if (degree === 0) queue.push(id)

    const sorted: string[] = []
    while (queue.length > 0) {
      const node = queue.shift()!
      sorted.push(node)
      for (const neighbor of adjacency.get(node) ?? []) {
        const nd = (inDegree.get(neighbor) ?? 1) - 1
        inDegree.set(neighbor, nd)
        if (nd === 0) queue.push(neighbor)
      }
    }
    return sorted
  },

  async detectMissingModules(): Promise<string[]> {
    const modules = await RuntimeManifest.listModules()
    const allDepIds = new Set(modules.flatMap((m) => m.dependencies))
    const allModuleIds = new Set(modules.map((m) => m.id))
    const missing: string[] = []
    for (const depId of allDepIds) {
      if (!allModuleIds.has(depId)) missing.push(depId)
    }
    return missing
  },
}