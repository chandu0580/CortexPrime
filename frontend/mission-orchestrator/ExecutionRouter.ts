import type { EnterpriseDecisionResult } from "@/enterprise-decision/types"
import type { MissionExecutionGraph } from "./types"

export const ExecutionRouter = {
  async routeExecution(result: EnterpriseDecisionResult, graph: MissionExecutionGraph): Promise<string[]> {
    const routingSequence: string[] = []
    const approved = result.outcomes.filter((o) => o.state === "approved")
    const needsReview = result.outcomes.filter((o) => o.state === "needs_review")
    const escalated = result.outcomes.filter((o) => o.state === "escalated")
    const deferred = result.outcomes.filter((o) => o.state === "deferred")

    if (approved.length > 0) {
      routingSequence.push("approved_execution")
    }

    if (needsReview.length > 0) {
      routingSequence.push("review_required")
    }

    if (escalated.length > 0) {
      routingSequence.push("escalation_active")
    }

    if (deferred.length > 0) {
      routingSequence.push("deferred_items")
    }

    if (graph.entryNodeIds.length > 0) {
      routingSequence.push(`entry:${graph.entryNodeIds.join(",")}`)
    }

    if (graph.exitNodeIds.length > 0) {
      routingSequence.push(`exit:${graph.exitNodeIds.join(",")}`)
    }

    return routingSequence
  },
}
