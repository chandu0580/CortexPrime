"use client"

import { motion } from "framer-motion"
import { Activity, GitBranch, UserCheck, MessageCircle, Box, HardDrive, BarChart3, Eye } from "lucide-react"

const connectorIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  github: GitBranch, jira: UserCheck, slack: MessageCircle,
  docker: Box, kubernetes: HardDrive,
  prometheus: BarChart3, grafana: Eye,
}

const defaultConnectors = ["github", "jira", "slack", "docker", "kubernetes", "prometheus", "grafana"]

export function ConnectorCard({
  connector,
  isDefault = false,
  name,
}: {
  connector?: Record<string, unknown>
  isDefault?: boolean
  name?: string
}) {
  const displayName = isDefault
    ? name!
    : ((connector?.name as string) || (connector?.connector_type as string))
  const type = isDefault
    ? name!
    : (connector?.connector_type as string)
  const status = isDefault
    ? "unavailable"
    : ((connector?.status as string) || "unknown")
  const capabilities = isDefault
    ? []
    : (connector?.capabilities as string[] | undefined) ?? []

  const Icon: React.ComponentType<{ className?: string }> =
    (connectorIcons[type.toLowerCase()] || Activity) as React.ComponentType<{ className?: string }>

  return (
    <motion.div
      whileHover={{ y: -2 }}
      className="surface-panel p-5"
    >
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${isDefault ? "bg-[var(--surface-raised)]" : "bg-[var(--accent-muted)]"}`}>
          <Icon className="w-5 h-5 text-[var(--accent)]" />
        </div>
        <div>
          <p className="type-body-sm text-[var(--text-primary)] font-semibold capitalize">{displayName}</p>
          <p className="type-caption text-[var(--text-muted)]">{type}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${
          status === "connected" || status === "active" ? "bg-[var(--success)]" : "bg-[var(--text-muted)]"
        }`} />
        <span className="type-label-sm text-[var(--text-muted)]">{status}</span>
      </div>
      {capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-3">
          {capabilities.slice(0, 3).map((cap: string) => (
            <span key={cap} className="px-2 py-0.5 rounded-md text-xs bg-[var(--surface-raised)] text-[var(--text-muted)]">
              {cap}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  )
}

export function ConnectorGrid({
  connectors,
}: {
  connectors: Record<string, unknown>[]
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {connectors.length === 0 ? (
        defaultConnectors.map((name) => (
          <ConnectorCard key={name} isDefault name={name} />
        ))
      ) : (
        connectors.map((conn) => (
          <ConnectorCard key={conn.connector_type as string} connector={conn} />
        ))
      )}
    </div>
  )
}
