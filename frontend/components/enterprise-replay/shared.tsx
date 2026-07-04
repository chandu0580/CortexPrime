"use client"

import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { cn } from "@/utils/cn"
import {
  Activity, Archive, BarChart3, Bot, Brain,
  Clock, Database, FileText, Filter, Globe,
  ListRestart, Mic, Monitor, Play, Pause,
  Puzzle, Search, Settings, ShieldCheck,
  Target, Workflow, Zap, ChevronLeft, ChevronRight, Bell, ChevronDown,
  Sparkles, CheckCircle2, PlayCircle, ListTodo,
} from "lucide-react"
import Link from "next/link"
import { useMemo, useState } from "react"

export const ENTERPRISE_REPLAY_NAV = [
  { href: "/enterprise-replay", icon: ListRestart, label: "Overview" },
  { href: "/enterprise-replay/mission", icon: Target, label: "Mission Replay" },
  { href: "/enterprise-replay/workers", icon: Bot, label: "Worker Replay" },
  { href: "/enterprise-replay/timeline", icon: Clock, label: "Timeline Explorer" },
  { href: "/enterprise-replay/execution-graph", icon: Workflow, label: "Execution Graph" },
  { href: "/enterprise-replay/decisions", icon: Brain, label: "Decision Explorer" },
  { href: "/enterprise-replay/connectors", icon: Puzzle, label: "Connector Activity" },
  { href: "/enterprise-replay/memory", icon: Database, label: "Memory Replay" },
  { href: "/enterprise-replay/knowledge-graph", icon: Activity, label: "Knowledge Graph" },
  { href: "/enterprise-replay/costs", icon: BarChart3, label: "Cost Replay" },
  { href: "/enterprise-replay/events", icon: ListTodo, label: "Event Explorer" },
]

export function EnterpriseReplaySidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#E8EDF3] bg-white transition-all duration-300",
      collapsed ? "w-[60px]" : "w-[172px]"
    )}>
      <div className={cn("flex items-center gap-2 px-4 py-[18px]", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-4 w-4 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round"/>
            <path d="M24 13 31 17v14l-7 4-7-4V17Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[0.82rem] font-bold leading-tight text-[#111827]">Replay</p>
            <p className="text-[0.62rem] font-medium text-[#9CA3AF]">Enterprise Center</p>
          </div>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-[2px]">
        {ENTERPRISE_REPLAY_NAV.map(({ href, icon: Icon, label }) => (
          <Link key={label} href={href} className={cn(
            "flex items-center gap-2.5 rounded-[12px] px-2.5 py-2 text-[0.82rem] font-semibold transition-all",
            collapsed && "justify-center px-0",
          )}>
            <Icon className="h-[16px] w-[16px] shrink-0 text-[#6B7280]" />
            {!collapsed && <span className="text-[#6B7280] hover:text-[#111827]">{label}</span>}
          </Link>
        ))}
      </nav>
      <div className="px-2 pb-4">
        <button onClick={onCollapse} className={cn(
          "flex w-full items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
          collapsed && "justify-center"
        )}>
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}

export function EnterpriseReplayTopBar({ sidebarWidth }: { sidebarWidth: number }) {
  const avatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, [])

  return (
    <header className="fixed top-0 right-0 z-30 flex items-center gap-3 border-b border-[#E8EDF3] bg-white/96 px-5 py-2.5 backdrop-blur transition-all duration-300"
      style={{ left: sidebarWidth }}>
      <button className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]">
        <Filter className="h-4 w-4" />
      </button>
      <label className="relative flex h-9 w-[200px] items-center">
        <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input type="search" placeholder="Search execution ID..." className="h-full w-full rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-12 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]" />
      </label>
      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#374151] hover:bg-[#F5F7FA]">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white ring-2 ring-white">3</span>
        </button>
        <div className="flex cursor-pointer items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white p-1 pr-2.5 hover:bg-[#F5F7FA]">
          <img src={avatar} alt="Avatar" width={28} height={28} className="rounded-[8px]" />
          <div className="hidden leading-tight sm:block">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Enterprise Admin</p>
            <p className="text-[0.62rem] text-[#9CA3AF]">Replay Center</p>
          </div>
          <ChevronDown className="hidden h-3 w-3 text-[#9CA3AF] sm:block" />
        </div>
      </div>
    </header>
  )
}

type Tone = "completed" | "running" | "failed" | "warning" | "info" | "queued"

const toneStyles: Record<Tone, string> = {
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  running:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  failed:    "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  warning:   "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  info:      "bg-[#EFF6FF] text-[#2563EB] ring-[#DBEAFE]",
  queued:    "bg-[#FFF7ED] text-[#C2410C] ring-[#FED7AA]",
}

const toneDot: Record<Tone, string> = {
  completed: "bg-[#38B88A]", running: "bg-[#38B88A]", failed: "bg-[#EF4444]",
  warning: "bg-[#F59E0B]", info: "bg-[#3B82F6]", queued: "bg-[#F97316]",
}

const toneText: Record<Tone, string> = {
  completed: "Completed", running: "Running", failed: "Failed",
  warning: "Warning", info: "Info", queued: "Queued",
}

export function Badge({ tone, label }: { tone: Tone; label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.72rem] font-semibold ring-1", toneStyles[tone])}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone])} />
      {label ?? toneText[tone]}
    </span>
  )
}

export function Sparkline({ data, color = "#38B88A" }: { data: number[]; color?: string }) {
  if (!data.length) return null
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1
  const W = 100, H = 36
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 6) - 3}`)
  const linePath = `M ${pts.join(" L ")}`
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`
  const uid = useMemo(() => Math.random().toString(36).slice(2, 7), [])

  return (
    <div className="h-9 w-full mt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.15} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${uid})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  )
}

const SPEEDS = [0.25, 0.5, 1, 2, 4] as const

export function EnterprisePlaybackControls() {
  const isPlaying = useEnterpriseReplayStore((s) => s.isPlaying)
  const play = useEnterpriseReplayStore((s) => s.play)
  const pause = useEnterpriseReplayStore((s) => s.pause)
  const next = useEnterpriseReplayStore((s) => s.next)
  const previous = useEnterpriseReplayStore((s) => s.previous)
  const seekTo = useEnterpriseReplayStore((s) => s.seekTo)
  const speed = useEnterpriseReplayStore((s) => s.playbackSpeed)
  const setSpeed = useEnterpriseReplayStore((s) => s.setPlaybackSpeed)
  const currentSequence = useEnterpriseReplayStore((s) => s.currentSequence)
  const timeline = useEnterpriseReplayStore((s) => s.timeline)

  const totalSequences = timeline?.events.length ?? 0
  const progress = totalSequences > 1 ? currentSequence / (totalSequences - 1) : 0

  return (
    <div className="flex items-center gap-4 rounded-[18px] border border-[#E8EDF3] bg-white px-5 py-3 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      <div className="flex items-center gap-2">
        <button onClick={previous} disabled={currentSequence === 0}
          className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA] disabled:opacity-40">
          <ChevronLeft className="h-4 w-4" />
        </button>
        <button onClick={isPlaying ? pause : play}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-[#38B88A] text-white hover:bg-[#2F9F77] shadow-[0_2px_8px_rgba(56,184,138,0.3)]">
          {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </button>
        <button onClick={next} disabled={currentSequence >= totalSequences - 1}
          className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA] disabled:opacity-40">
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 flex items-center gap-3">
        <span className="text-[0.7rem] font-mono text-[#6B7280] min-w-[48px]">
          {totalSequences > 0 ? `${currentSequence + 1}` : "—"} / {totalSequences || "—"}
        </span>
        <div className="flex-1 h-1.5 rounded-full bg-[#E8EDF3] cursor-pointer relative"
          onClick={(e) => {
            if (!totalSequences) return
            const rect = (e.currentTarget).getBoundingClientRect()
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
            seekTo(Math.round(pct * (totalSequences - 1)))
          }}>
          <div className="h-full rounded-full bg-[#38B88A] transition-all duration-100"
            style={{ width: `${progress * 100}%` }} />
        </div>
      </div>
      <div className="flex items-center gap-1">
        {SPEEDS.map((s) => (
          <button key={s} onClick={() => setSpeed(s)}
            className={cn(
              "px-2 py-1 rounded-[6px] text-[0.7rem] font-semibold border transition-colors",
              speed === s ? "border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77]" : "border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]"
            )}>
            {s}×
          </button>
        ))}
      </div>
    </div>
  )
}

export function ExportButton({ executionId }: { executionId?: string | null }) {
  const [open, setOpen] = useState(false)
  if (!executionId) return null

  const formats = [
    { value: "json", label: "Export as JSON" },
    { value: "markdown", label: "Export as Markdown" },
    { value: "timeline", label: "Export Timeline" },
    { value: "replay-package", label: "Export Replay Package" },
  ] as const

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white shadow-[0_3px_10px_rgba(56,184,138,0.25)] hover:bg-[#2F9F77]">
        <FileText className="h-3.5 w-3.5" /> Export
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 w-48 rounded-[12px] border border-[#E8EDF3] bg-white shadow-lg">
          {formats.map((f) => (
            <a key={f.value}
              href={`${window.location.origin}/api/enterprise-replay/export/${executionId}?format=${f.value}`}
              className="block px-4 py-2.5 text-[0.8rem] font-medium text-[#374151] hover:bg-[#F5F7FA] first:rounded-t-[12px] last:rounded-b-[12px]"
              onClick={() => setOpen(false)}>
              {f.label}
            </a>
          ))}
        </div>
      )}
    </div>
  )
}

export function ExecutionIdInput({ onLoad }: { onLoad: (id: string) => void }) {
  const [value, setValue] = useState("")
  return (
    <div className="flex items-center gap-2">
      <input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Enter execution ID..."
        className="h-9 rounded-[10px] border border-[#E8EDF3] bg-white px-3 text-[0.8rem] text-[#111827] outline-none focus:border-[#B7E5D3] w-[300px]"
        onKeyDown={(e) => { if (e.key === "Enter" && value.trim()) onLoad(value.trim()) }}
      />
      <button onClick={() => { if (value.trim()) onLoad(value.trim()) }}
        className="flex items-center gap-1.5 rounded-[10px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white hover:bg-[#2F9F77]">
        <PlayCircle className="h-4 w-4" /> Load
      </button>
    </div>
  )
}

export function KpiCard({ label, value, trend, data, tone = "info", icon: Icon }: {
  label: string; value: string; trend?: string; data?: number[]; tone?: Tone; icon: React.ComponentType<{ className?: string }>
}) {
  const isError = tone === "failed"
  const chartColor = isError ? "#EF4444" : "#38B88A"
  const iconBg = isError ? "bg-[#FEF2F2] text-[#EF4444] border-[#FBD5D5]" : "bg-[#ECFBF4] text-[#38B88A] border-[#D6F0E5]"

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[0.71rem] font-semibold text-[#9CA3AF]">{label}</p>
        <div className={cn("flex h-7 w-7 items-center justify-center rounded-[9px] border", iconBg)}>
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[1.4rem] font-bold tracking-tight text-[#111827]">{value}</span>
        {trend && <span className={cn("text-[0.7rem] font-bold", isError ? "text-[#EF4444]" : "text-[#38B88A]")}>{trend}</span>}
      </div>
      {data && <Sparkline data={data} color={chartColor} />}
    </div>
  )
}
