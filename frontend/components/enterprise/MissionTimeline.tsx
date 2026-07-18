"use client"

import { motion } from "framer-motion"
import type { StageResult } from "@/types/enterprise"

const stateColors: Record<string, string> = {
  mission_received: "var(--text-muted)", mission_analyzed: "var(--info)",
  mission_planned: "var(--accent-primary)", knowledge_retrieved: "var(--success)",
  learning_retrieved: "var(--success)", governance_evaluated: "var(--warning)",
  execution_planned: "var(--accent-secondary)", execution_started: "var(--info)",
  execution_completed: "var(--success)", verification: "var(--accent-primary)",
  knowledge_updated: "var(--success)", learning_updated: "var(--success)",
  mission_archived: "var(--text-muted)",
}

export function MissionTimeline({
  stages,
}: {
  stages: [string, StageResult | undefined][]
}) {
  if (!stages.length) return null

  return (
    <div className="space-y-2">
      {stages.map(([state, result], i) => (
        <motion.div
          key={state}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.03 }}
          className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-[var(--surface-raised)]"
        >
          <div className="flex flex-col items-center">
            <div className="w-2.5 h-2.5 rounded-full" style={{ background: stateColors[state] || "var(--text-muted)" }} />
            {i < stages.length - 1 && <div className="w-px h-6 bg-[var(--border)]" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="type-body-sm text-[var(--text-primary)] capitalize">{state.replace(/_/g, " ")}</p>
            {result?.error && <p className="type-caption text-[var(--danger)]">{result.error}</p>}
          </div>
          <div className="text-right">
            <span className={`type-label-sm ${result?.success ? "text-[var(--success)]" : "text-[var(--danger)]"}`}>
              {result?.success ? "PASS" : "FAIL"}
            </span>
            {result?.runtime && <p className="type-caption text-[var(--text-muted)]">{result.runtime}</p>}
          </div>
        </motion.div>
      ))}
    </div>
  )
}
