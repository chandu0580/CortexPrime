import type { MissionExecutionGraph } from "./types"
import type { ExecutionCheckpoint, ValidationType } from "./types"
import { generateId } from "./shared"

function determineValidationType(nodeType: string): ValidationType {
  if (nodeType === "checkpoint") return "automatic"
  if (nodeType === "milestone") return "manual"
  return "hybrid"
}

export const CheckpointPlanner = {
  async planCheckpoints(graph: MissionExecutionGraph): Promise<ExecutionCheckpoint[]> {
    const checkpoints: ExecutionCheckpoint[] = []

    for (const edge of graph.edges) {
      if (edge.type === "dependency") {
        checkpoints.push({
          id: generateId("checkpoint"),
          name: "Dependency Validation",
          description: "Validate that all prerequisites are satisfied before proceeding",
          nodeId: edge.targetId,
          criteria: [
            "All upstream nodes have completed successfully",
            "Required outputs are available and validated",
            "No blocking issues detected in upstream execution",
          ],
          validationType: "automatic",
        })
      }
    }

    for (const node of graph.nodes) {
      if (node.type === "milestone" || node.type === "phase") {
        checkpoints.push({
          id: generateId("checkpoint"),
          name: `${node.label} Gate Review`,
          description: `Formal review gate for ${node.label}`,
          nodeId: node.id,
          criteria: [
            `All ${node.label.toLowerCase()} objectives have been met`,
            "Required artifacts are complete and reviewed",
            "Stakeholder sign-off obtained",
            "No critical issues outstanding",
          ],
          validationType: determineValidationType(node.type),
        })
      }
    }

    for (let i = 0; i < graph.exitNodeIds.length; i++) {
      checkpoints.push({
        id: generateId("checkpoint"),
        name: `Exit Checkpoint ${i + 1}`,
        description: "Final validation before mission completion",
        nodeId: graph.exitNodeIds[i],
        criteria: [
          "All execution nodes have completed successfully",
          "All checkpoints have passed validation",
          "Mission objectives have been achieved",
          "Documentation is complete",
        ],
        validationType: "manual",
      })
    }

    return checkpoints
  },
}
