import type { ExecutionDependency } from "./types"
import { generateId } from "@/worker-framework/shared"

const dependencies = new Map<string, ExecutionDependency>()

export const ExecutionDependencyManager = {
  async registerDependency(sessionId: string, sourceTaskId: string, targetTaskId: string, type: ExecutionDependency["type"] = "hard"): Promise<ExecutionDependency> {
    const dep: ExecutionDependency = {
      id: generateId("exec-dep"),
      sessionId,
      sourceTaskId,
      targetTaskId,
      type,
      resolved: false,
      createdAt: new Date().toISOString(),
      resolvedAt: null,
    }
    dependencies.set(dep.id, dep)
    return dep
  },

  async getDependency(dependencyId: string): Promise<ExecutionDependency | null> {
    return dependencies.get(dependencyId) ?? null
  },

  async getDependenciesBySession(sessionId: string): Promise<ExecutionDependency[]> {
    return Array.from(dependencies.values()).filter((d) => d.sessionId === sessionId)
  },

  async getDependenciesForTask(taskId: string): Promise<ExecutionDependency[]> {
    return Array.from(dependencies.values()).filter((d) => d.targetTaskId === taskId || d.sourceTaskId === taskId)
  },

  async validateDependencies(sessionId: string): Promise<{ valid: boolean; unresolved: ExecutionDependency[] }> {
    const deps = await this.getDependenciesBySession(sessionId)
    const unresolved = deps.filter((d) => !d.resolved)
    return { valid: unresolved.length === 0, unresolved }
  },

  async resolveDependency(dependencyId: string): Promise<ExecutionDependency> {
    const dep = dependencies.get(dependencyId)
    if (!dep) throw new Error(`Dependency ${dependencyId} not found`)
    dep.resolved = true
    dep.resolvedAt = new Date().toISOString()
    return dep
  },

  async resolveAllForSession(sessionId: string): Promise<void> {
    const deps = await this.getDependenciesBySession(sessionId)
    for (const dep of deps) {
      dep.resolved = true
      dep.resolvedAt = new Date().toISOString()
    }
  },

  async detectCycles(sessionId: string): Promise<string[][]> {
    const deps = await this.getDependenciesBySession(sessionId)
    const graph = new Map<string, string[]>()

    for (const dep of deps) {
      if (!graph.has(dep.sourceTaskId)) graph.set(dep.sourceTaskId, [])
      graph.get(dep.sourceTaskId)!.push(dep.targetTaskId)
      if (!graph.has(dep.targetTaskId)) graph.set(dep.targetTaskId, [])
    }

    const cycles: string[][] = []
    const visited = new Set<string>()
    const recStack = new Set<string>()
    const pathStack: string[] = []

    function dfs(node: string): void {
      visited.add(node)
      recStack.add(node)
      pathStack.push(node)

      const neighbors = graph.get(node) ?? []
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          dfs(neighbor)
        } else if (recStack.has(neighbor)) {
          const cycleStart = pathStack.indexOf(neighbor)
          if (cycleStart >= 0) {
            cycles.push(pathStack.slice(cycleStart))
          }
        }
      }

      pathStack.pop()
      recStack.delete(node)
    }

    for (const node of graph.keys()) {
      if (!visited.has(node)) dfs(node)
    }

    return cycles
  },

  async countBySession(sessionId: string): Promise<number> {
    return Array.from(dependencies.values()).filter((d) => d.sessionId === sessionId).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, d] of dependencies.entries()) {
      if (d.sessionId === sessionId) dependencies.delete(id)
    }
  },
}
