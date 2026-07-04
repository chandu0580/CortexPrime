import type { PlatformModuleRecord } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"

export const ModuleLoader = {
  async loadModule(moduleId: string): Promise<boolean> {
    try {
      const mod = await PlatformRegistry.getModule(moduleId)
      if (!mod) return false
      const pkg = mod.package
      const importPath = `@/${pkg}`
      try {
        const _module = await import(/* @vite-ignore */ importPath)
        if (_module) {
          await PlatformRegistry.updateModule(moduleId, { loaded: true })
          return true
        }
      } catch {
        return false
      }
      return false
    } catch {
      return false
    }
  },

  async loadAll(): Promise<{ loaded: string[]; failed: string[] }> {
    const modules = await PlatformRegistry.listModules()
    const loaded: string[] = []
    const failed: string[] = []

    for (const mod of modules) {
      const ok = await this.loadModule(mod.id)
      if (ok) loaded.push(mod.id)
      else failed.push(mod.id)
    }
    return { loaded, failed }
  },

  async resolveLoadOrder(): Promise<string[]> {
    const modules = await PlatformRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    const inDegree = new Map<string, number>()

    for (const m of modules) { adjacency.set(m.id, []); inDegree.set(m.id, 0) }
    for (const m of modules) {
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
}