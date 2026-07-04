import type { EnterpriseDecisionResult, DecisionOutcome } from "@/enterprise-decision/types"
import type { MissionExecutionGraph, MissionExecutionNode, MissionExecutionEdge, NodeType, EdgeType, ExecutionStage } from "./types"
import { generateId } from "./shared"

const categoryNodeType: Record<string, NodeType> = {
  strategy: "phase",
  capability: "task",
  risk: "checkpoint",
  dependency: "milestone",
  recommendation: "phase",
}

function determineStage(outcome: DecisionOutcome): ExecutionStage {
  if (outcome.state === "approved") return "queued"
  if (outcome.state === "pending_approval") return "initialized"
  if (outcome.state === "needs_review") return "initialized"
  if (outcome.state === "escalated") return "initialized"
  if (outcome.state === "deferred") return "queued"
  if (outcome.state === "rejected") return "failed"
  return "initialized"
}

export const ExecutionGraphBuilder = {
  async buildExecutionGraph(result: EnterpriseDecisionResult): Promise<MissionExecutionGraph> {
    const nodes: MissionExecutionNode[] = []
    const edges: MissionExecutionEdge[] = []

    for (const outcome of result.outcomes) {
      const nodeType = categoryNodeType[outcome.sourceCategory] ?? "task"

      const node: MissionExecutionNode = {
        id: outcome.id,
        sourceDecisionId: outcome.sourceDecisionId,
        sourceCategory: outcome.sourceCategory,
        type: nodeType,
        label: outcome.sourceCategory.charAt(0).toUpperCase() + outcome.sourceCategory.slice(1),
        description: outcome.summary,
        stage: determineStage(outcome),
        assignedCapability: null,
        estimatedDuration: outcome.route.priority === "critical" ? "1-2 weeks"
          : outcome.route.priority === "high" ? "2-3 weeks"
          : "3-4 weeks",
        metadata: {
          state: outcome.state,
          route: outcome.route.target,
          priority: outcome.route.priority,
        },
      }

      nodes.push(node)
    }

    const approvedNodes = nodes.filter((n) => n.stage === "queued")
    const reviewNodes = nodes.filter((n) => n.stage === "initialized")

    for (let i = 1; i < approvedNodes.length; i++) {
      edges.push({
        id: generateId("edge"),
        sourceId: approvedNodes[i - 1].id,
        targetId: approvedNodes[i].id,
        type: "sequence",
      })
    }

    if (approvedNodes.length > 0 && reviewNodes.length > 0) {
      edges.push({
        id: generateId("edge"),
        sourceId: approvedNodes[approvedNodes.length - 1].id,
        targetId: reviewNodes[0].id,
        type: "dependency",
      })
    }

    let currentPhaseId: string | null = null
    for (const node of nodes) {
      if (node.type === "phase") {
        currentPhaseId = node.id
      } else if (currentPhaseId) {
        edges.push({
          id: generateId("edge"),
          sourceId: currentPhaseId,
          targetId: node.id,
          type: "containment" as EdgeType,
        })
      }
    }

    const entryNodeIds = nodes.filter((n) => !edges.some((e) => e.targetId === n.id)).map((n) => n.id)
    const exitNodeIds = nodes.filter((n) => !edges.some((e) => e.sourceId === n.id)).map((n) => n.id)

    return {
      id: generateId("graph"),
      nodes,
      edges,
      entryNodeIds: entryNodeIds.length > 0 ? entryNodeIds : nodes.length > 0 ? [nodes[0].id] : [],
      exitNodeIds: exitNodeIds.length > 0 ? exitNodeIds : nodes.length > 0 ? [nodes[nodes.length - 1].id] : [],
    }
  },
}
