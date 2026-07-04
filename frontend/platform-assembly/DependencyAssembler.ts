import type { AssemblyDependency } from "./types"
import { PlatformRegistry } from "./PlatformRegistry"

export const DependencyAssembler = {
  async assemble(): Promise<AssemblyDependency[]> {
    const modules = await PlatformRegistry.listModules()
    return modules.map((m) => ({
      moduleId: m.id,
      dependsOn: m.dependencies,
      resolved: m.dependencies.every((d) => modules.some((mod) => mod.id === d)),
    }))
  },

  async detectCycles(): Promise<string[][]> {
    const modules = await PlatformRegistry.listModules()
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

  async validateAll(): Promise<{ valid: boolean; errors: string[]; warnings: string[] }> {
    const errors: string[] = []
    const warnings: string[] = []
    const deps = await this.assemble()
    const cycles = await this.detectCycles()

    const unresolved = deps.filter((d) => !d.resolved)
    if (unresolved.length > 0) errors.push(`unresolved dependencies: ${unresolved.map((d) => d.moduleId).join(", ")}`)
    if (cycles.length > 0) errors.push(`circular dependencies: ${JSON.stringify(cycles)}`)

    return { valid: errors.length === 0, errors, warnings }
  },
}