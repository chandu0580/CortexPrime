import { type RuntimeModule, RuntimeCompositionState } from "./types"
import { RuntimeRegistry } from "./RuntimeRegistry"

export const RuntimeCompositionGraph = {
  async buildGraph(): Promise<{ nodes: RuntimeModule[]; adjacency: Map<string, string[]> }> {
    const modules = await RuntimeRegistry.listModules()
    const adjacency = new Map<string, string[]>()
    for (const m of modules) {
      adjacency.set(m.id, [...m.dependencies])
    }
    return { nodes: modules, adjacency }
  },

  async topologicalSort(): Promise<string[]> {
    const { nodes, adjacency } = await this.buildGraph()
    const inDegree = new Map<string, number>()
    for (const n of nodes) inDegree.set(n.id, 0)
    for (const [id, deps] of adjacency) {
      for (const dep of deps) {
        inDegree.set(id, (inDegree.get(id) ?? 0) + 1)
      }
    }

    const queue: string[] = []
    for (const [id, degree] of inDegree) if (degree === 0) queue.push(id)

    const sorted: string[] = []
    while (queue.length > 0) {
      const node = queue.shift()!
      sorted.push(node)
      for (const [id, deps] of adjacency) {
        if (deps.includes(node)) {
          const nd = (inDegree.get(id) ?? 1) - 1
          inDegree.set(id, nd)
          if (nd === 0) queue.push(id)
        }
      }
    }
    return sorted
  },

  async detectCycles(): Promise<string[][]> {
    const { nodes, adjacency } = await this.buildGraph()
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

    for (const n of nodes) if (!visited.has(n.id)) dfs(n.id, [])
    return cycles
  },

  async getExecutionOrder(): Promise<string[]> {
    return this.topologicalSort()
  },
}
