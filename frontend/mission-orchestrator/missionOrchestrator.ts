import type { EnterpriseDecisionResult } from "@/enterprise-decision/types"
import type { OrchestrationReport } from "./types"
import { ExecutionGraphBuilder } from "./ExecutionGraphBuilder"
import { CapabilityAssignmentEngine } from "./CapabilityAssignmentEngine"
import { CheckpointPlanner } from "./CheckpointPlanner"
import { LifecycleCoordinator } from "./LifecycleCoordinator"
import { ExecutionRouter } from "./ExecutionRouter"
import { RecoveryPlanner } from "./RecoveryPlanner"

export const missionOrchestrator = {
  async createExecutionPlan(result: EnterpriseDecisionResult): Promise<OrchestrationReport> {
    const graph = await ExecutionGraphBuilder.buildExecutionGraph(result)
    const assignments = await CapabilityAssignmentEngine.assignCapabilities(graph)
    const checkpoints = await CheckpointPlanner.planCheckpoints(graph)
    const lifecycle = await LifecycleCoordinator.coordinateLifecycle()
    const recoveryPlans = await RecoveryPlanner.planRecovery(graph)
    const routingSequence = await ExecutionRouter.routeExecution(result, graph)

    const approvedCount = graph.nodes.filter((n) => n.stage === "queued").length
    const initializedCount = graph.nodes.filter((n) => n.stage === "initialized").length

    return {
      graph,
      checkpoints,
      assignments,
      lifecycle,
      recoveryPlans,
      summary: `Execution plan created. ${graph.nodes.length} nodes, ${graph.edges.length} edges, ${checkpoints.length} checkpoints, ${assignments.length} capability assignments, ${recoveryPlans.length} recovery plans. ${approvedCount} ready for execution, ${initializedCount} awaiting prerequisites. Routing: ${routingSequence.join(", ")}.`,
      timestamp: new Date().toISOString(),
    }
  },
}
