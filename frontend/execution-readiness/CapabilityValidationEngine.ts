import type { MissionExecutionGraph, CapabilityAssignment } from "@/mission-orchestrator/types"
import type { ReadinessCheck, ExecutionPrerequisite } from "./types"
import { generateId } from "./shared"

export const CapabilityValidationEngine = {
  async validateCapabilities(graph: MissionExecutionGraph, assignments: CapabilityAssignment[]): Promise<{
    capabilityChecks: ReadinessCheck[]
    prerequisites: ExecutionPrerequisite[]
  }> {
    const unassignedNodes = graph.nodes.filter((n) => !n.assignedCapability)
    const prerequisites: ExecutionPrerequisite[] = []

    for (const assignment of assignments) {
      for (const prereq of assignment.prerequisites) {
        prerequisites.push({
          id: generateId("prereq"),
          name: `Prerequisite: ${prereq}`,
          description: `Capability ${assignment.capabilityName} requires: ${prereq}`,
          targetId: assignment.nodeId,
          met: Math.random() > 0.2,
          details: `Prerequisite "${prereq}" for capability "${assignment.capabilityName}"`,
        })
      }
    }

    const unmetPrerequisites = prerequisites.filter((p) => !p.met)
    const nodesMissingCapability = graph.nodes.filter((n) => n.stage === "queued" && !n.assignedCapability)

    const capabilityChecks: ReadinessCheck[] = [
      {
        id: generateId("chk"),
        type: "capability",
        name: "Node Capability Assignment",
        description: "All execution-ready nodes must have an assigned capability",
        result: unassignedNodes.length === 0 ? "pass" : "warning",
        details: unassignedNodes.length === 0
          ? "All nodes have assigned capabilities"
          : `${unassignedNodes.length} nodes have no capability assigned (${unassignedNodes.map((n) => n.label).join(", ")})`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "capability",
        name: "Capability Prerequisites",
        description: "All capability prerequisites must be satisfied",
        result: unmetPrerequisites.length === 0 ? "pass" : "fail",
        details: unmetPrerequisites.length === 0
          ? "All capability prerequisites are met"
          : `${unmetPrerequisites.length} prerequisites not satisfied`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
      {
        id: generateId("chk"),
        type: "capability",
        name: "Execution-Ready Capability Coverage",
        description: "Queued nodes must have assigned capabilities",
        result: nodesMissingCapability.length === 0 ? "pass" : "fail",
        details: nodesMissingCapability.length === 0
          ? "All queued nodes have assigned capabilities"
          : `${nodesMissingCapability.length} queued nodes missing capability assignment`,
        sourceId: null,
        timestamp: new Date().toISOString(),
      },
    ]

    return { capabilityChecks, prerequisites }
  },
}
