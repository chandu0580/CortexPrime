import type { MissionExecutionGraph } from "./types"
import type { ExecutionRecoveryPlan } from "./types"
import { generateId } from "./shared"

export const RecoveryPlanner = {
  async planRecovery(graph: MissionExecutionGraph): Promise<ExecutionRecoveryPlan[]> {
    const plans: ExecutionRecoveryPlan[] = []

    for (const node of graph.nodes) {
      const failedDeps = graph.edges.filter((e) => e.type === "dependency" && e.targetId === node.id)
      const predecessors = graph.edges.filter((e) => e.type === "sequence" && e.targetId === node.id)

      if (failedDeps.length > 0) {
        plans.push({
          id: generateId("recovery"),
          nodeId: node.id,
          failureScenario: `Dependency failure: ${failedDeps.map((d) => d.sourceId).join(", ")}`,
          recoveryActions: [
            "Identify root cause of dependency failure",
            "Evaluate alternative dependency paths",
            "Re-sequence affected nodes if necessary",
            "Notify capability owner for manual intervention",
          ],
          fallbackNodeId: null,
          estimatedRecoveryTime: "2-4 hours",
          autoRecoverable: false,
        })
      }

      if (node.type === "checkpoint") {
        plans.push({
          id: generateId("recovery"),
          nodeId: node.id,
          failureScenario: `Validation failure at ${node.label}`,
          recoveryActions: [
            "Review validation criteria and results",
            "Collect additional evidence if needed",
            "Engage reviewer for manual assessment",
            "Re-run validation after corrective actions",
          ],
          fallbackNodeId: predecessors.length > 0 ? predecessors[0].sourceId : null,
          estimatedRecoveryTime: "1-2 hours",
          autoRecoverable: false,
        })
      }

      if (node.type === "phase") {
        plans.push({
          id: generateId("recovery"),
          nodeId: node.id,
          failureScenario: `Phase execution failure at ${node.label}`,
          recoveryActions: [
            "Halt downstream execution immediately",
            "Assess impact scope and affected nodes",
            "Determine rollback or retry strategy",
            "Re-plan remaining phases if necessary",
            "Escalate to LifecycleCoordinator",
          ],
          fallbackNodeId: predecessors.length > 0 ? predecessors[0].sourceId : null,
          estimatedRecoveryTime: "4-8 hours",
          autoRecoverable: false,
        })
      }
    }

    return plans
  },
}
