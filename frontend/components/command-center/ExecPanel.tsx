"use client"

import { ReactNode } from "react"
import { cn } from "@/utils/cn"

interface ExecPanelProps {
  title: string
  subtitle?: string
  children: ReactNode
  className?: string
  headerRight?: ReactNode
  accent?: "emerald" | "blue" | "violet" | "amber" | "rose" | "cyan"
  loading?: boolean
  compact?: boolean
}

const ACCENT_GRADIENTS = {
  emerald: "from-emerald-500/10 via-emerald-500/5 to-transparent",
  blue: "from-blue-500/10 via-blue-500/5 to-transparent",
  violet: "from-violet-500/10 via-violet-500/5 to-transparent",
  amber: "from-amber-500/10 via-amber-500/5 to-transparent",
  rose: "from-rose-500/10 via-rose-500/5 to-transparent",
  cyan: "from-cyan-500/10 via-cyan-500/5 to-transparent",
}

const ACCENT_BORDERS = {
  emerald: "border-emerald-500/20",
  blue: "border-blue-500/20",
  violet: "border-violet-500/20",
  amber: "border-amber-500/20",
  rose: "border-rose-500/20",
  cyan: "border-cyan-500/20",
}

const ACCENT_HEADS = {
  emerald: "bg-emerald-500/10",
  blue: "bg-blue-500/10",
  violet: "bg-violet-500/10",
  amber: "bg-amber-500/10",
  rose: "bg-rose-500/10",
  cyan: "bg-cyan-500/10",
}

export function ExecPanel({
  title,
  subtitle,
  children,
  className = "",
  headerRight,
  accent = "emerald",
  loading = false,
  compact = false,
}: ExecPanelProps) {
  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-xl border ${ACCENT_BORDERS[accent]} bg-white/[0.02] backdrop-blur-sm ${className}`}
    >
      <div className={`pointer-events-none absolute inset-0 bg-gradient-to-b ${ACCENT_GRADIENTS[accent]}`} />
      {loading && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-white/[0.01] z-10">
          <div className="flex gap-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className="h-1.5 w-1.5 rounded-full bg-emerald-400/50"
                style={{ animation: `pulse 0.8s ease-in-out ${i * 0.15}s infinite` }}
              />
            ))}
          </div>
        </div>
      )}
      <div
        className={`flex items-center justify-between shrink-0 border-b border-white/5 ${ACCENT_HEADS[accent]} ${compact ? "px-3 py-2" : "px-4 py-3"}`}
      >
        <div className="flex items-center gap-2 min-w-0">
          <h3 className={`text-xs font-semibold text-white/50 uppercase tracking-wider truncate ${compact ? "" : ""}`}>
            {title}
          </h3>
          {subtitle && (
            <span className="text-[10px] text-white/20 hidden sm:inline">{subtitle}</span>
          )}
        </div>
        {headerRight && <div className="flex items-center gap-2 shrink-0">{headerRight}</div>}
      </div>
      <div className={`flex-1 overflow-hidden ${compact ? "p-3" : "p-4"}`}>
        {children}
      </div>
    </div>
  )
}

export function ExecKpi({ label, value, color = "text-emerald-400", trend }: {
  label: string
  value: string | number
  color?: string
  trend?: string
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[10px] text-white/40 uppercase tracking-wider">{label}</span>
      <div className="flex items-baseline gap-1.5">
        <span className={`text-lg font-bold ${color}`}>{value}</span>
        {trend && (
          <span className={`text-[10px] ${trend.startsWith("+") ? "text-emerald-400" : trend.startsWith("-") ? "text-rose-400" : "text-white/30"}`}>
            {trend}
          </span>
        )}
      </div>
    </div>
  )
}

export function EmptyPanel({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="h-8 w-8 rounded-full bg-white/5 flex items-center justify-center mb-2">
        <span className="text-white/20 text-xs">—</span>
      </div>
      <p className="text-xs text-white/30">{title}</p>
      {description && <p className="text-[10px] text-white/20 mt-0.5">{description}</p>}
    </div>
  )
}

export function PulseDot({ size = "md" }: { size?: "sm" | "md" }) {
  const s = size === "sm" ? 4 : 6
  return (
    <span className="relative flex shrink-0" style={{ width: s, height: s }}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-emerald-400" />
      <span className="relative inline-flex rounded-full h-full w-full bg-emerald-400" />
    </span>
  )
}