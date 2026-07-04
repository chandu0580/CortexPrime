import type { MissionExecutionGraph, MissionExecutionEdge } from "@/mission-orchestrator/types"
import type { ExecutionDependency, ReadinessCheck } from "./types"
import { generateId } from "./shared"

export const DependencyValidationEngine = {
  async validateDependencies(graph: MissionExecutionGraph): Promise<{
    dependencyChecks: ReadinessCheck[]
    dependencies: ExecutionDependency[]
  }> {
    const dependencyEdges = graph.edges.filter((e) => e.type === "dependency")
    const dependencies: ExecutionDependency[] = []

    for (const edge of dependencyEdges) {
      const sourceNode = graph.nodes.find((n) => n.id === edge.sourceId)
      const targetNode = graph.nodes.find((n) => n.id === edge.targetId)

      dependencies.push({
        id: generateId("dep"),
        sourceNodeId: edge.sourceId,
        targetNodeId: edge.targetId,
        dependencyType: "hard",
        satisfied: sourceNode?.stage === "completed" || sourceNode?.stage === "queued",
        details: sourceNode && targetNode
          ? `"${sourceNode.label}" → "${targetNode.label}": ${sourceNode.stage === "completed" ? "complete" : sourceNode.stage === "queued" ? "ready" : "not ready"}`
          : "Unknown dependency",
      })
    }

    const unresolvedHardDeps = dependencies.filter((d) => d.dependencyType === "hard" && !d.satisfied)

    const dependencyChecks: ReadinessCheck[] = [
      {
        id: generateId("chk"),
        type: "dependency",
        name: "Hard Dependency Resolution",
        description: "All hard dependencies must be satisfied before execution",
        result: unresolvedHardDeps.length === 0 ? "pass" : "fail",
        details: unresolvedHardDeps.length === 0
          ? "All hard dependencies are satisfied"
          : `${unresolvedHardDeps.length} unresolved hard dependencies detected`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "dependency",
        name: "Cyclic Dependency Detection",
        description: "Execution graph must not contain cyclic dependencies",
        result: detectCycle(graph) ? "fail" : "pass",
        details: detectCycle(graph) ? "Cyclic dependency detected in execution graph" : "No cyclic dependencies found",
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
    ]

    return { dependencyChecks, dependencies }
  },
}

function detectCycle(graph: MissionExecutionGraph): boolean {
  const adjacency = new Map<string, string[]>()
  for (const edge of graph.edges) {
    if (!adjacency.has(edge.sourceId)) adjacency.set(edge.sourceId, [])
    adjacency.get(edge.sourceId)!.push(edge.targetId)
  }

  const visited = new Set<string>()
  const recursionStack = new Set<string>()

  function dfs(nodeId: string): boolean {
    if (recursionStack.has(nodeId)) return true
    if (visited.has(nodeId)) return false

    visited.add(nodeId)
    recursionStack.add(nodeId)

    const neighbors = adjacency.get(nodeId) ?? []
    for (const neighbor of neighbors) {
      if (dfs(neighbor)) return true
    }

    recursionStack.delete(nodeId)
    return false
  }

  for (const node of graph.nodes) {
    if (dfs(node.id)) return true
  }

  return false
}
