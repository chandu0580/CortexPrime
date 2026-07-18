"use client"

import { motion } from "framer-motion"
import type { LucideIcon } from "lucide-react"

export default function StatsCard({
  icon: Icon, label, value, color,
}: {
  icon: LucideIcon; label: string; value: number; color: "accent" | "info" | "success" | "danger"
}) {
  const colors: Record<string, string> = {
    accent: "var(--accent-primary)", info: "var(--info)", success: "var(--success)", danger: "var(--danger)",
  }
  return (
    <motion.div
      whileHover={{ y: -2 }}
      className="surface-panel p-5 flex items-center gap-4"
    >
      <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: `${colors[color]}20` }}>
        <Icon className="w-5 h-5" style={{ color: colors[color] }} />
      </div>
      <div>
        <p className="type-label-sm text-[var(--text-muted)]">{label}</p>
        <motion.p
          key={value}
          initial={{ scale: 1.4, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="type-metric text-[var(--text-primary)]"
        >
          {value}
        </motion.p>
      </div>
    </motion.div>
  )
}
