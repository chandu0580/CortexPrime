import type { BootstrapDependency } from "./types"
import { BootstrapRegistry } from "./BootstrapRegistry"

export const BootstrapDependencyResolver = {
  async resolveDependencies(): Promise<{ resolved: BootstrapDependency[]; missing: string[]; cycles: string[][] }> {
    const modules = await BootstrapRegistry.listModules()
    const resolved: BootstrapDependency[] = []
    const missing: string[] = []

    for (const mod of modules) {
      for (const dep of mod.dependencies) {
        const depModule = await BootstrapRegistry.getModule(dep)
        if (!depModule && !missing.includes(dep)) missing.push(dep)
      }
      resolved.push({
        moduleId: mod.id,
        dependsOn: mod.dependencies,
        resolved: mod.dependencies.every((d) => modules.some((m) => m.id === d)),
      })
    }

    const cycles = await this.detectCycles()
    return { resolved, missing, cycles }
  },

  async detectCycles(): Promise<string[][]> {
    const modules = await BootstrapRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    for (const m of modules) adjacency.set(m.id, [...m.dependencies])

    const cycles: string[][] = []
    const visited = new Set<string>()
    const recStack = new Set<string>()

    const dfs = (node: string, path: string[]): void => {
      if (recStack.has(node)) {
        const start = path.indexOf(node)
        if (start >= 0) cycles.push(path.slice(start))
        return
      }
      if (visited.has(node)) return
      visited.add(node)
      recStack.add(node)
      path.push(node)
      for (const neighbor of adjacency.get(node) ?? []) dfs(neighbor, [...path])
      recStack.delete(node)
    }

    for (const m of modules) if (!visited.has(m.id)) dfs(m.id, [])
    return cycles
  },

  async detectMissingModules(): Promise<string[]> {
    const { missing } = await this.resolveDependencies()
    return missing
  },

  async generateStartupOrder(): Promise<string[]> {
    const modules = await BootstrapRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    const inDegree = new Map<string, number>()

    for (const m of modules) {
      adjacency.set(m.id, [])
      inDegree.set(m.id, 0)
    }
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