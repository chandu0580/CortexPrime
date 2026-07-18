"use client"

import { ExecPanel } from "./ExecPanel"
import Link from "next/link"
import {
  Crosshair, Play, History, PlugZap, ShieldCheck, BarChart3,
  AlertCircle, GitBranch, Sparkles, ChevronRight,
} from "lucide-react"

const ACTIONS = [
  { icon: Crosshair, label: "Create Mission", href: "/executive-platform/mission-control", color: "text-emerald-400 bg-emerald-500/10" },
  { icon: Play, label: "Execute Workflow", href: "/workflows", color: "text-blue-400 bg-blue-500/10" },
  { icon: History, label: "Open Replay", href: "/replay", color: "text-violet-400 bg-violet-500/10" },
  { icon: PlugZap, label: "View Connectors", href: "/executive-platform/connectors", color: "text-cyan-400 bg-cyan-500/10" },
  { icon: ShieldCheck, label: "Open Governance", href: "/governance-center", color: "text-amber-400 bg-amber-500/10" },
  { icon: BarChart3, label: "Open Analytics", href: "/analytics", color: "text-rose-400 bg-rose-500/10" },
  { icon: AlertCircle, label: "Create Incident", href: "/operations-center", color: "text-rose-400 bg-rose-500/10" },
  { icon: GitBranch, label: "Create Repository", href: "/integrations", color: "text-emerald-400 bg-emerald-500/10" },
  { icon: Sparkles, label: "Launch Research", href: "/executive-platform/intelligence", color: "text-violet-400 bg-violet-500/10" },
]

export function QuickActionsPanel() {
  return (
    <ExecPanel
      title="Quick Actions"
      subtitle="Launch frequently used tools"
      accent="emerald"
    >
      <div className="grid grid-cols-3 gap-1.5">
        {ACTIONS.map((action) => (
          <Link
            key={action.label}
            href={action.href}
            className="flex flex-col items-center gap-1 p-2 rounded-lg hover:bg-white/5 transition-all group"
          >
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${action.color} group-hover:scale-110 transition-transform`}>
              <action.icon className="w-3.5 h-3.5" />
            </div>
            <span className="text-[9px] text-white/40 group-hover:text-white/60 text-center leading-tight transition-colors">
              {action.label}
            </span>
          </Link>
        ))}
      </div>
    </ExecPanel>
  )
}