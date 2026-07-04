import type { MissionPlan } from "./types"
import type { MissionGraph, MissionGraphNode, MissionGraphEdge } from "./types"

function generateEdgeId(): string {
  return `edge-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
}

export const MissionGraphBuilder = {
  async buildMissionGraph(plan: MissionPlan): Promise<MissionGraph> {
    const nodes: MissionGraphNode[] = []
    const edges: MissionGraphEdge[] = []

    for (const phase of plan.phases) {
      const phaseNode: MissionGraphNode = {
        id: phase.id,
        type: "phase",
        label: phase.name,
        metadata: {
          description: phase.description,
          order: String(phase.order),
          status: phase.status,
        },
      }
      nodes.push(phaseNode)

      for (const task of phase.tasks) {
        const taskNode: MissionGraphNode = {
          id: task.id,
          type: "task",
          label: task.name,
          metadata: {
            description: task.description,
            effort: task.estimatedEffort,
            status: task.status,
          },
        }
        nodes.push(taskNode)

        edges.push({
          id: generateEdgeId(),
          sourceId: phase.id,
          targetId: task.id,
          type: "containment",
        })
      }
    }

    for (const dep of plan.dependencies) {
      edges.push({
        id: generateEdgeId(),
        sourceId: dep.sourceId,
        targetId: dep.targetId,
        type: "dependency",
      })
    }

    for (let i = 1; i < plan.phases.length; i++) {
      edges.push({
        id: generateEdgeId(),
        sourceId: plan.phases[i - 1].id,
        targetId: plan.phases[i].id,
        type: "sequence",
      })
    }

    return { nodes, edges }
  },
}
