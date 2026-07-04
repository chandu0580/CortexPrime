import type { MissionExecutionGraph } from "./types"
import type { CapabilityAssignment } from "./types"
import { generateId } from "./shared"

const capabilityPool: { name: string; priority: number; prerequisites: string[]; matchCategories: string[] }[] = [
  { name: "Strategic Planning", priority: 1, prerequisites: [], matchCategories: ["strategy", "recommendation"] },
  { name: "Risk Management", priority: 2, prerequisites: ["Strategic Planning"], matchCategories: ["risk"] },
  { name: "Resource Coordination", priority: 3, prerequisites: ["Strategic Planning"], matchCategories: ["dependency", "capability"] },
  { name: "Quality Assurance", priority: 4, prerequisites: ["Resource Coordination"], matchCategories: ["recommendation"] },
  { name: "Technical Execution", priority: 5, prerequisites: ["Resource Coordination"], matchCategories: ["capability"] },
  { name: "Stakeholder Communication", priority: 6, prerequisites: [], matchCategories: ["strategy", "recommendation"] },
]

export const CapabilityAssignmentEngine = {
  async assignCapabilities(graph: MissionExecutionGraph): Promise<CapabilityAssignment[]> {
    const assignments: CapabilityAssignment[] = []

    for (const node of graph.nodes) {
      const matched = capabilityPool.filter((cap) => cap.matchCategories.includes(node.sourceCategory))

      if (matched.length > 0) {
        const primary = matched[0]
        assignments.push({
          id: generateId("assign"),
          nodeId: node.id,
          capabilityName: primary.name,
          priority: primary.priority,
          prerequisites: primary.prerequisites,
        })
      } else {
        assignments.push({
          id: generateId("assign"),
          nodeId: node.id,
          capabilityName: "General Execution",
          priority: 99,
          prerequisites: [],
        })
      }
    }

    return assignments
  },
}
