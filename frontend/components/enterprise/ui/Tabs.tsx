"use client"

import { motion } from "framer-motion"
import type { ReactNode } from "react"
import { cn } from "@/utils/cn"

export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: { id: string; label: string; icon?: ReactNode }[]
  active: string
  onChange: (id: string) => void
  className?: string
}) {
  return (
    <div className={cn("flex gap-1 rounded-xl bg-[var(--surface-raised)] p-1", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onChange(tab.id)}
          className={cn(
            "relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
            active === tab.id
              ? "text-[var(--text-primary)]"
              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]",
          )}
        >
          {active === tab.id && (
            <motion.div
              layoutId="tab-indicator"
              className="absolute inset-0 rounded-lg bg-[var(--surface-panel)] shadow-sm"
              transition={{ type: "spring", stiffness: 500, damping: 35 }}
            />
          )}
          <span className="relative z-10 flex items-center gap-2">
            {tab.icon}
            {tab.label}
          </span>
        </button>
      ))}
    </div>
  )
}
