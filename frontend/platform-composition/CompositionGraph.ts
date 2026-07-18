import type { CompositionNode, CompositionEdge } from "./types"
import { CompositionRegistry } from "./CompositionRegistry"

export const CompositionGraph = {
  async buildGraph(): Promise<{ nodes: CompositionNode[]; edges: CompositionEdge[] }> {
    const modules = await CompositionRegistry.listModules()
    const allEdges = await CompositionRegistry.listEdges()
    const nodes: CompositionNode[] = modules.map((m) => ({
      id: m.moduleId,
      moduleId: m.moduleId,
      moduleName: m.moduleName,
      moduleVersion: m.moduleVersion,
      category: m.category,
      dependencies: m.dependencies,
      initialized: false,
      active: false,
      startedAt: null,
    }))
    return { nodes, edges: allEdges }
  },

  async topologicalSort(): Promise<string[]> {
    const modules = await CompositionRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    const inDegree = new Map<string, number>()

    for (const m of modules) {
      adjacency.set(m.moduleId, [])
      inDegree.set(m.moduleId, 0)
    }
    for (const m of modules) {
      for (const dep of m.dependencies) {
        adjacency.get(dep)?.push(m.moduleId)
        inDegree.set(m.moduleId, (inDegree.get(m.moduleId) ?? 0) + 1)
      }
    }

    const queue: string[] = []
    for (const [id, degree] of inDegree) {
      if (degree === 0) queue.push(id)
    }

    const sorted: string[] = []
    while (queue.length > 0) {
      const node = queue.shift()!
      sorted.push(node)
      for (const neighbor of adjacency.get(node) ?? []) {
        const newDegree = (inDegree.get(neighbor) ?? 1) - 1
        inDegree.set(neighbor, newDegree)
        if (newDegree === 0) queue.push(neighbor)
      }
    }
    return sorted
  },

  async findDependencyPath(moduleId: string): Promise<string[]> {
    const modules = await CompositionRegistry.listModules()
    // eslint-disable-next-line @next/next/no-assign-module-variable
    const module = modules.find((m) => m.moduleId === moduleId)
    if (!module) return []
    const path: string[] = []
    const visited = new Set<string>()

    const dfs = (id: string): boolean => {
      if (visited.has(id)) return false
      visited.add(id)
      const m = modules.find((mod) => mod.moduleId === id)
      if (!m) return false
      for (const dep of m.dependencies) {
        if (!dfs(dep)) return false
      }
      path.push(id)
      return true
    }

    dfs(moduleId)
    return path
  },

  async detectCycles(): Promise<string[][]> {
    const modules = await CompositionRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    for (const m of modules) {
      adjacency.set(m.moduleId, [...m.dependencies])
    }

    const cycles: string[][] = []
    const visited = new Set<string>()
    const recStack = new Set<string>()

    const dfs = (node: string, path: string[]): void => {
      if (recStack.has(node)) {
        const cycleStart = path.indexOf(node)
        if (cycleStart >= 0) cycles.push(path.slice(cycleStart))
        return
      }
      if (visited.has(node)) return
      visited.add(node)
      recStack.add(node)
      path.push(node)
      for (const neighbor of adjacency.get(node) ?? []) {
        dfs(neighbor, [...path])
      }
      recStack.delete(node)
    }

    for (const m of modules) {
      if (!visited.has(m.moduleId)) dfs(m.moduleId, [])
    }
    return cycles
  },
}