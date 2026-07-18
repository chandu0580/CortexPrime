"use client"

import { motion } from "framer-motion"
import { useMissions } from "@/hooks/queries/useMissions"
import { History, Play } from "lucide-react"
import { Badge } from "@/components/enterprise/ui"
import Link from "next/link"

export default function ReplayCenter() {
  const { data } = useMissions()
  const missions = data?.missions ?? []

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Replay Center</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Review mission execution history</p>
      </div>

      <div className="surface-panel p-5">
        <div className="space-y-2">
          {missions.length === 0 ? (
            <p className="type-body text-[var(--text-muted)] text-center py-8">No completed missions to replay</p>
          ) : (
            missions.filter((m) => m.status === "completed" || m.status === "failed").map((m, i) => (
              <motion.div
                key={m.mission_id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
              >
                <Link href={`/enterprise/replay/${m.mission_id}`}>
                  <div className="flex items-center gap-3 p-3 rounded-xl hover:bg-[var(--surface-raised)] transition-colors">
                    <div className="w-8 h-8 rounded-lg bg-[var(--accent-muted)] flex items-center justify-center">
                      <Play className="w-4 h-4 text-[var(--accent)]" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="type-body-sm text-[var(--text-primary)] truncate">{m.goal}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant={m.status === "failed" ? "danger" : "success"}>{m.status}</Badge>
                        <span className="type-caption text-[var(--text-muted)]">{m.current_state.replace(/_/g, " ")}</span>
                      </div>
                    </div>
                    <History className="w-4 h-4 text-[var(--text-muted)] shrink-0" />
                  </div>
                </Link>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
