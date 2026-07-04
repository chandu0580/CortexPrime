"use client"

import { ReactNode } from "react"
import { cn } from "@/utils/cn"

export function GlassCard({ children, className, onClick }: { children: ReactNode; className?: string; onClick?: () => void }) {
  return (
    <div className={cn("border border-white/5 rounded-xl p-4 bg-white/[0.02] backdrop-blur-sm", className)} onClick={onClick}>
      {children}
    </div>
  )
}

export function SectionHeader({ icon: Icon, title, subtitle, action }: {
  icon?: React.ComponentType<{ className?: string }>
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon className="w-4 h-4 text-white/40" />}
        <div>
          <h2 className="text-sm font-medium text-white/60">{title}</h2>
          {subtitle && <p className="text-xs text-white/30 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      {action && <div className="flex items-center gap-2">{action}</div>}
    </div>
  )
}

export function KpiCard({ label, value, icon: Icon, color = "text-emerald-400", trend }: {
  label: string
  value: string | number
  icon?: React.ComponentType<{ className?: string }>
  color?: string
  trend?: string
}) {
  return (
    <div className="border border-white/5 rounded-xl p-4 bg-white/[0.02]">
      <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
        {Icon && <Icon className={`w-3.5 h-3.5 ${color}`} />}
        {label}
      </div>
      <div className={`text-2xl font-semibold ${color}`}>{value}</div>
      {trend && <div className={`text-xs mt-1 ${trend.startsWith("+") ? "text-emerald-400" : "text-red-400"}`}>{trend}</div>}
    </div>
  )
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const colors: Record<string, string> = {
    healthy: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    active: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    connected: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
    pending: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    running: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    degraded: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    failed: "text-red-400 bg-red-500/10 border-red-500/20",
    blocked: "text-red-400 bg-red-500/10 border-red-500/20",
    completed: "text-blue-400 bg-blue-500/10 border-blue-500/20",
    idle: "text-white/30 bg-white/5 border-white/10",
    disconnected: "text-red-400 bg-red-500/10 border-red-500/20",
    checking: "text-white/30 bg-white/5 border-white/10",
  }
  const c = colors[status] || "text-white/40 bg-white/5 border-white/10"
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium uppercase ${c}`}>
      {label || status}
    </span>
  )
}

export function PulseDot({ color = "bg-emerald-400" }: { color?: string }) {
  return (
    <span className="relative flex h-2 w-2">
      <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${color}`} />
      <span className={`relative inline-flex rounded-full h-2 w-2 ${color}`} />
    </span>
  )
}

export function EmptyState({ icon: Icon, title, description }: {
  icon?: React.ComponentType<{ className?: string }>
  title: string
  description?: string
}) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {Icon && <Icon className="w-10 h-10 text-white/10 mb-3" />}
      <p className="text-sm text-white/30">{title}</p>
      {description && <p className="text-xs text-white/20 mt-1">{description}</p>}
    </div>
  )
}

export function LiveIndicator() {
  return (
    <div className="flex items-center gap-1.5">
      <PulseDot />
      <span className="text-[10px] text-emerald-400 font-medium uppercase tracking-wider">Live</span>
    </div>
  )
}