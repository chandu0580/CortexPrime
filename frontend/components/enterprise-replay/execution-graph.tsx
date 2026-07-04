"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { Badge } from "./shared"
import { useState } from "react"
import { motion } from "framer-motion"

const NODE_COLORS: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  mission:        { bg: "#ECFBF4", text: "#2F9F77", border: "#D6F0E5", icon: "M" },
  worker:         { bg: "#EFF6FF", text: "#2563EB", border: "#DBEAFE", icon: "W" },
  connector:      { bg: "#FFFBEB", text: "#B45309", border: "#FDECC8", icon: "C" },
  memory:         { bg: "#F5F3FF", text: "#7C3AED", border: "#EDE9FE", icon: "Me" },
  knowledge_graph:{ bg: "#F0FDF4", text: "#16A34A", border: "#DCFCE7", icon: "KG" },
  approval:       { bg: "#FFF7ED", text: "#C2410C", border: "#FED7AA", icon: "A" },
  completion:     { bg: "#ECFBF4", text: "#2F9F77", border: "#D6F0E5", icon: "✓" },
}

export function ExecutionGraphPanel() {
  const executionGraph = useEnterpriseReplayStore((s) => s.executionGraph)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)

  if (!executionGraph) return <div className="text-center py-12 text-[0.82rem] text-[#6B7280]">No execution graph loaded</div>

  const { nodes, edges } = executionGraph

  return (
    <div className="space-y-5">
      {/* Graph visualization */}
      <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-6 min-h-[400px]">
        <h3 className="text-[0.95rem] font-bold text-[#111827] mb-6">Execution Flow</h3>
        <div className="flex items-center justify-center gap-0">
          {nodes.map((node, i) => {
            const colors = NODE_COLORS[node.type] ?? NODE_COLORS.mission
            const isSelected = selectedNode === node.id
            const EdgeConnector = i < nodes.length - 1 ? (
              <div className="flex items-center mx-2">
                <div className="h-0.5 w-8 bg-[#38B88A]" />
                <div className="text-[0.6rem] text-[#9CA3AF] font-medium mx-1">
                  {edges.find((e) => e.source === node.id && e.target === nodes[i + 1]?.id)?.label ?? ""}
                </div>
                <div className="h-0.5 w-8 bg-[#38B88A]" />
              </div>
            ) : null

            return (
              <div key={node.id} className="flex items-center">
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  onClick={() => setSelectedNode(isSelected ? null : node.id)}
                  className="flex flex-col items-center gap-2 p-3 rounded-[16px] border-2 transition-all cursor-pointer min-w-[100px]"
                  style={{
                    borderColor: isSelected ? colors.text : colors.border,
                    background: isSelected ? `${colors.bg}` : "#FFFFFF",
                    boxShadow: isSelected ? `0 4px 12px ${colors.border}` : "none",
                  }}>
                  <div className="flex h-10 w-10 items-center justify-center rounded-[10px] text-[0.7rem] font-bold"
                    style={{ background: colors.bg, color: colors.text }}>
                    {colors.icon}
                  </div>
                  <div className="text-center">
                    <p className="text-[0.72rem] font-bold text-[#111827]">{node.label}</p>
                    <p className="text-[0.6rem]" style={{ color: colors.text }}>{node.status}</p>
                  </div>
                </motion.button>
                {EdgeConnector}
              </div>
            )
          })}
        </div>
      </div>

      {/* Selected node details */}
      {selectedNode && (
        <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5">
          <h3 className="text-[0.95rem] font-bold text-[#111827] mb-3">Node Details: {nodes.find((n) => n.id === selectedNode)?.label}</h3>
          <pre className="text-[0.72rem] text-[#6B7280] bg-[#F8FAFC] p-3 rounded-[10px] overflow-x-auto">
            {JSON.stringify(nodes.find((n) => n.id === selectedNode), null, 2)}
          </pre>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4">
          <p className="text-[0.66rem] text-[#9CA3AF] font-medium">Total Nodes</p>
          <p className="text-[1.2rem] font-bold text-[#111827]">{String(executionGraph.summary?.total_nodes ?? nodes.length)}</p>
        </div>
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4">
          <p className="text-[0.66rem] text-[#9CA3AF] font-medium">Total Edges</p>
          <p className="text-[1.2rem] font-bold text-[#111827]">{String(executionGraph.summary?.total_edges ?? edges.length)}</p>
        </div>
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4">
          <p className="text-[0.66rem] text-[#9CA3AF] font-medium">Has Mission</p>
          <Badge tone={executionGraph.summary?.has_mission ? "completed" : "failed"} label={executionGraph.summary?.has_mission ? "Yes" : "No"} />
        </div>
        <div className="rounded-[12px] border border-[#E8EDF3] bg-white p-4">
          <p className="text-[0.66rem] text-[#9CA3AF] font-medium">Completed</p>
          <Badge tone={executionGraph.summary?.has_completion ? "completed" : "warning"} label={executionGraph.summary?.has_completion ? "Yes" : "In Progress"} />
        </div>
      </div>
    </div>
  )
}