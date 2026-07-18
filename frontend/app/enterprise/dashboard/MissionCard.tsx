"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import type { OrchestratorMission } from "@/types/enterprise"
import { Badge } from "@/components/enterprise/ui"

const statusVariants: Record<string, "success" | "warning" | "info" | "danger" | "default"> = {
  running: "success", pending: "warning",
  paused: "info", failed: "danger",
  completed: "success", cancelled: "default",
}

export default function MissionCard({ mission }: { mission: OrchestratorMission }) {
  return (
    <Link href={`/enterprise/missions/${mission.mission_id}`}>
      <motion.div
        whileHover={{ x: 4 }}
        className="flex items-center justify-between p-3 rounded-xl hover:bg-[var(--surface-raised)] transition-colors cursor-pointer"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="min-w-0">
            <p className="type-body-sm text-[var(--text-primary)] truncate">{mission.goal}</p>
            <p className="type-caption text-[var(--text-muted)]">
              {mission.current_state.replace(/_/g, " ")}
            </p>
          </div>
        </div>
        <Badge variant={statusVariants[mission.status] || "default"}>
          {mission.status}
        </Badge>
      </motion.div>
    </Link>
  )
}
