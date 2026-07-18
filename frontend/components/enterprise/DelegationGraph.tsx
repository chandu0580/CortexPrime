"use client"

import { motion } from "framer-motion"
import { Bot } from "lucide-react"
import type { ReactNode } from "react"

type AgentNode = {
  id: string
  label: string
  status: string
  capabilities: string[]
  icon?: ReactNode
}

export function DelegationGraph({
  agents,
  selectedAgent,
  onSelect,
}: {
  agents: AgentNode[]
  selectedAgent: string | null
  onSelect: (id: string | null) => void
}) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <motion.div
          key={agent.id}
          whileHover={{ y: -2 }}
          className={`surface-panel p-4 cursor-pointer transition-all ${
            selectedAgent === agent.id ? "accent-border" : ""
          }`}
          onClick={() => onSelect(selectedAgent === agent.id ? null : agent.id)}
        >
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-lg bg-[var(--accent-muted)] flex items-center justify-center">
              {agent.icon || <Bot className="w-4 h-4 text-[var(--accent)]" />}
            </div>
            <div>
              <p className="type-body-sm text-[var(--text-primary)] font-semibold">{agent.label}</p>
              <p className="type-caption text-[var(--text-muted)]">{agent.id}</p>
            </div>
            <span className={`ml-auto w-2 h-2 rounded-full ${
              agent.status === "idle" ? "bg-[var(--success)]" :
              agent.status === "running" ? "bg-[var(--info)] animate-blink" :
              agent.status === "failed" ? "bg-[var(--danger)]" : "bg-[var(--text-muted)]"
            }`} />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {agent.capabilities.slice(0, 4).map((cap) => (
              <span key={cap} className="px-2 py-0.5 rounded-md text-xs bg-[var(--surface-raised)] text-[var(--text-muted)]">
                {cap}
              </span>
            ))}
          </div>
        </motion.div>
      ))}
    </div>
  )
}

export function AgentHistoryList({
  history,
}: {
  history: Record<string, unknown>[]
}) {
  if (!history.length) {
    return <p className="type-body-sm text-[var(--text-muted)]">No task history</p>
  }

  return (
    <div className="space-y-2">
      {history.map((h, i) => (
        <div key={i} className="flex items-center justify-between p-2.5 rounded-xl bg-[var(--surface-raised)]">
          <div>
            <p className="type-body-sm text-[var(--text-primary)]">{String(h.task_id || h.agent_type || "")}</p>
            {(h.error as string) ? <p className="type-caption text-[var(--danger)]">{String(h.error)}</p> : null}
          </div>
          <span className={`type-label-sm ${(h.success as boolean) ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
            {(h.success as boolean) ? "SUCCESS" : "FAILED"}
          </span>
        </div>
      ))}
    </div>
  )
}
