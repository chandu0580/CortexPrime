"use client"

import { motion } from "framer-motion"
import { Cpu, Server, Database, Globe, Activity, Wifi, WifiOff, type LucideIcon } from "lucide-react"

type TopologyNode = {
  id: string
  label: string
  type: string
  icon: LucideIcon
  status: "active" | "inactive"
}

type TopologyConnection = {
  from: string
  to: string
  label: string
}

export function TopologyGraph({
  nodes,
  connections,
}: {
  nodes: TopologyNode[]
  connections: TopologyConnection[]
}) {
  return (
    <div className="surface-panel p-8">
      <div className="flex items-center justify-center relative min-h-[400px]">
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity: 0.15 }}>
          {connections.map((conn) => {
            const fromNode = nodes.find((n) => n.id === conn.from)
            const toNode = nodes.find((n) => n.id === conn.to)
            if (!fromNode || !toNode) return null
            const fromIdx = nodes.indexOf(fromNode)
            const toIdx = nodes.indexOf(toNode)
            const angle1 = (fromIdx / nodes.length) * Math.PI * 2 - Math.PI / 2
            const angle2 = (toIdx / nodes.length) * Math.PI * 2 - Math.PI / 2
            const cx = 400, cy = 200, r = 150
            const x1 = cx + r * Math.cos(angle1)
            const y1 = cy + r * Math.sin(angle1)
            const x2 = cx + r * Math.cos(angle2)
            const y2 = cy + r * Math.sin(angle2)
            return <line key={`${conn.from}-${conn.to}`} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--accent-border)" strokeWidth="1.5" />
          })}
        </svg>

        <div className="relative grid grid-cols-3 gap-6 z-10">
          {nodes.map((node, i) => (
            <motion.div
              key={node.id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.1 }}
              whileHover={{ scale: 1.05 }}
              className={`surface-panel p-5 text-center ${
                node.status === "active" ? "accent-border" : ""
              }`}
            >
              <div className="w-12 h-12 rounded-xl bg-[var(--accent-muted)] flex items-center justify-center mx-auto mb-3">
                <node.icon className="w-6 h-6 text-[var(--accent)]" />
              </div>
              <p className="type-body-sm text-[var(--text-primary)] font-semibold">{node.label}</p>
              <div className="flex items-center justify-center gap-1.5 mt-2">
                {node.status === "active" ? (
                  <>
                    <Wifi className="w-3 h-3 text-[var(--success)]" />
                    <span className="type-caption text-[var(--success)]">Active</span>
                  </>
                ) : (
                  <>
                    <WifiOff className="w-3 h-3 text-[var(--text-muted)]" />
                    <span className="type-caption text-[var(--text-muted)]">Standby</span>
                  </>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  )
}

export function DefaultTopologyNodes(runtimeStatus: { runtimes?: Record<string, boolean> }): TopologyNode[] {
  return [
    { id: "cortex", label: "CortexPrime Core", type: "core", icon: Cpu, status: "active" },
    { id: "orchestrator", label: "Mission Orchestrator", type: "runtime", icon: Activity, status: runtimeStatus?.runtimes?.cognitive_memory ? "active" : "inactive" },
    { id: "memory", label: "Cognitive Memory", type: "runtime", icon: Database, status: runtimeStatus?.runtimes?.cognitive_memory ? "active" : "inactive" },
    { id: "knowledge", label: "Knowledge Base", type: "runtime", icon: Database, status: runtimeStatus?.runtimes?.knowledge ? "active" : "inactive" },
    { id: "governance", label: "Governance Engine", type: "runtime", icon: Globe, status: runtimeStatus?.runtimes?.governance ? "active" : "inactive" },
    { id: "execution", label: "Execution Runtime", type: "runtime", icon: Server, status: runtimeStatus?.runtimes?.execution ? "active" : "inactive" },
  ]
}

export const defaultConnections: TopologyConnection[] = [
  { from: "cortex", to: "orchestrator", label: "orchestrates" },
  { from: "orchestrator", to: "memory", label: "reads/writes" },
  { from: "orchestrator", to: "knowledge", label: "indexes" },
  { from: "orchestrator", to: "governance", label: "evaluates" },
  { from: "orchestrator", to: "execution", label: "executes" },
]
