import type { ApplicationModule, ApplicationDependency } from "./types"
import { ApplicationRegistry } from "./ApplicationRegistry"

export const ModuleComposer = {
  async compose(): Promise<ApplicationModule[]> {
    const modules = await ApplicationRegistry.listModules()
    for (const mod of modules) {
      await ApplicationRegistry.markRegistered(mod.id)
    }
    return modules
  },

  async resolveOrder(): Promise<string[]> {
    const modules = await ApplicationRegistry.listModules()
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

  async getDependencies(): Promise<ApplicationDependency[]> {
    const modules = await ApplicationRegistry.listModules()
    return modules.map((m) => ({
      moduleId: m.id,
      dependsOn: m.dependencies,
      resolved: m.dependencies.every((d) => modules.some((mod) => mod.id === d)),
    }))
  },
}