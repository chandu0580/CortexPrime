"use client"

import { useMemo, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Server, Cloud, HardDrive, Wifi, Activity, AlertTriangle, CheckCircle2, XCircle } from "lucide-react"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"
import type { InfraCluster, InfraNode, InfraPod } from "@/types/infrastructure"

interface TopologyViewProps {
  clusters?: InfraCluster[]
  nodes?: InfraNode[]
  pods?: InfraPod[]
  loading?: boolean
}

type NodeType = "cluster" | "node" | "pod"

const typeConfig: Record<NodeType, { icon: typeof Server; color: string; bg: string }> = {
  cluster: { icon: Cloud, color: "text-[var(--success)]", bg: "bg-[var(--success-muted)]" },
  node: { icon: Server, color: "text-[#3B82F6]", bg: "bg-[#EFF6FF]" },
  pod: { icon: HardDrive, color: "text-[#8B5CF6]", bg: "bg-[#F5F3FF]" },
}

const statusColor: Record<string, string> = {
  healthy: "text-[var(--success)]",
  ready: "text-[var(--success)]",
  running: "text-[var(--success)]",
  True: "text-[var(--success)]",
  degraded: "text-[var(--warning)]",
  pending: "text-[var(--warning)]",
  warning: "text-[var(--warning)]",
  failed: "text-[var(--danger)]",
  error: "text-[var(--danger)]",
  False: "text-[var(--danger)]",
}

const statusBg: Record<string, string> = {
  healthy: "bg-[var(--success-muted)]",
  ready: "bg-[var(--success-muted)]",
  running: "bg-[var(--success-muted)]",
  degraded: "bg-[var(--warning-muted)]",
  pending: "bg-[var(--warning-muted)]",
  failed: "bg-[var(--danger-muted)]",
  error: "bg-[var(--danger-muted)]",
}

function TopologyNode({ type, label, status, metrics, onSelect }: {
  type: NodeType
  label: string
  status: string
  metrics?: Record<string, number>
  onSelect?: () => void
}) {
  const Icon = typeConfig[type].icon
  const statusCls = statusColor[status] ?? "text-[var(--text-muted)]"
  const statusBgCls = statusBg[status] ?? "bg-[var(--surface-raised)]"

  return (
    <motion.button
      onClick={onSelect}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className={cn(
        "flex flex-col items-center gap-2 rounded-[16px] border p-4 transition-all min-w-[140px]",
        "border-[var(--border)] bg-[var(--surface)] hover:shadow-md hover:border-[var(--success)]/30"
      )}
    >
      <div className={cn("flex h-10 w-10 items-center justify-center rounded-[12px]", typeConfig[type].bg, typeConfig[type].color)}>
        <Icon className="h-5 w-5" />
      </div>
      <span className="text-[0.75rem] font-bold text-[var(--text-primary)] text-center leading-tight">{label}</span>
      <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.62rem] font-semibold", statusBgCls, statusCls)}>
        <span className={cn("h-1.5 w-1.5 rounded-full", statusCls.replace("text-", "bg-"))} />
        {status}
      </span>
      {metrics && Object.keys(metrics).length > 0 && (
        <div className="mt-1 flex gap-2 text-[0.6rem] text-[var(--text-muted)] font-medium">
          {Object.entries(metrics).slice(0, 2).map(([k, v]) => (
            <span key={k}>{k}: {(v * 100).toFixed(0)}%</span>
          ))}
        </div>
      )}
    </motion.button>
  )
}

function ConnectionLine({ from, to, label, status }: { from: { x: number; y: number }; to: { x: number; y: number }; label?: string; status?: string }) {
  const midX = (from.x + to.x) / 2
  const midY = (from.y + to.y) / 2
  const color = status === "healthy" || status === "ready" || status === "running"
    ? "var(--success)" : status === "degraded" || status === "pending" || status === "warning"
    ? "var(--warning)" : status === "failed" || status === "error"
    ? "var(--danger)" : "var(--border)"

  return (
    <g>
      <line x1={from.x} y1={from.y} x2={to.x} y2={to.y} stroke={color} strokeWidth="1.5" strokeDasharray={status === "pending" ? "4 3" : "none"} />
      {label && (
        <text x={midX} y={midY - 4} textAnchor="middle" fill="var(--text-muted)" fontSize="8" fontWeight="600">{label}</text>
      )}
    </g>
  )
}

export default function TopologyView({ clusters = [], nodes = [], pods = [], loading }: TopologyViewProps) {
  const [selectedType, setSelectedType] = useState<NodeType | "all">("all")

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16" role="status" aria-label="Loading topology data">
        <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 2, ease: "linear" }}>
          <Activity className="h-8 w-8 text-[var(--success)]" />
        </motion.div>
        <span className="sr-only">Loading topology data...</span>
      </div>
    )
  }

  const hasData = clusters.length > 0 || nodes.length > 0 || pods.length > 0

  if (!hasData) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Server className="h-12 w-12 text-[var(--text-muted)] mb-4" />
        <p className="text-[0.9rem] font-semibold text-[var(--text-secondary)]">No infrastructure data</p>
        <p className="text-[0.75rem] text-[var(--text-muted)] mt-1">Connect your clusters to see topology</p>
      </div>
    )
  }

  const filters: { key: NodeType | "all"; label: string; count: number }[] = [
    { key: "all", label: "All", count: clusters.length + nodes.length + pods.length },
    { key: "cluster", label: "Clusters", count: clusters.length },
    { key: "node", label: "Nodes", count: nodes.length },
    { key: "pod", label: "Pods", count: pods.length },
  ]

  const filteredClusters = selectedType === "all" || selectedType === "cluster" ? clusters : []
  const filteredNodes = selectedType === "all" || selectedType === "node" ? nodes : []
  const filteredPods = selectedType === "all" || selectedType === "pod" ? pods : []

  const totalHealthy = [...clusters, ...nodes, ...pods].filter(
    (e) => ["healthy", "ready", "running", "True"].includes((e as any).status ?? (e as any).phase)
  ).length
  const totalWarning = [...clusters, ...nodes, ...pods].filter(
    (e) => ["degraded", "pending", "warning", "False"].includes((e as any).status ?? (e as any).phase)
  ).length
  const totalError = [...clusters, ...nodes, ...pods].filter(
    (e) => ["failed", "error", "CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"].includes((e as any).status ?? (e as any).phase)
  ).length

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-4" role="group" aria-label="Filter by infrastructure type">
        {filters.map((f) => (
          <button
            key={f.key}
            onClick={() => setSelectedType(f.key)}
            aria-pressed={selectedType === f.key}
            className={cn(
              "rounded-[10px] px-3.5 py-1.5 text-[0.75rem] font-semibold transition-all",
              selectedType === f.key
                ? "bg-[var(--success)] text-white shadow-sm"
                : "bg-[var(--surface-raised)] text-[var(--text-secondary)] hover:bg-[var(--success-muted)] hover:text-[var(--success)]"
            )}
          >
            {f.label} ({f.count})
          </button>
        ))}
        <div className="ml-auto flex items-center gap-3 text-[0.7rem] font-semibold">
          <span className="flex items-center gap-1 text-[var(--success)]"><CheckCircle2 className="h-3 w-3" />{totalHealthy}</span>
          <span className="flex items-center gap-1 text-[var(--warning)]"><AlertTriangle className="h-3 w-3" />{totalWarning}</span>
          <span className="flex items-center gap-1 text-[var(--danger)]"><XCircle className="h-3 w-3" />{totalError}</span>
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={selectedType}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.2 }}
          className="space-y-6"
          aria-live="polite"
          aria-atomic="false"
        >
          {filteredClusters.length > 0 && (
            <div>
              <h4 className="text-[0.75rem] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3 flex items-center gap-2">
                <Cloud className="h-3.5 w-3.5 text-[var(--success)]" /> Clusters ({filteredClusters.length})
              </h4>
              <div className="flex flex-wrap gap-3">
                {filteredClusters.map((c) => (
                  <TopologyNode key={c.cluster_id} type="cluster" label={c.name} status={c.status}
                    metrics={{ cpu: 0.65, mem: 0.72 }} />
                ))}
              </div>
            </div>
          )}
          {filteredNodes.length > 0 && (
            <div>
              <h4 className="text-[0.75rem] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3 flex items-center gap-2">
                <Server className="h-3.5 w-3.5 text-[#3B82F6]" /> Nodes ({filteredNodes.length})
              </h4>
              <div className="flex flex-wrap gap-3">
                {filteredNodes.map((n) => (
                  <TopologyNode key={n.node_id} type="node" label={n.name} status={n.status}
                    metrics={{ cpu: n.cpu_usage, mem: n.memory_usage }} />
                ))}
              </div>
            </div>
          )}
          {filteredPods.length > 0 && (
            <div>
              <h4 className="text-[0.75rem] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-3 flex items-center gap-2">
                <HardDrive className="h-3.5 w-3.5 text-[#8B5CF6]" /> Pods ({filteredPods.length})
              </h4>
              <div className="flex flex-wrap gap-3">
                {filteredPods.map((p) => (
                  <TopologyNode key={p.pod_id} type="pod" label={p.name} status={p.phase ?? p.status} />
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
