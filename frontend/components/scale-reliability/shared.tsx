"use client"

import { useState, useMemo, type ReactNode } from "react"
import {
  LayoutDashboard,
  Gauge,
  Zap,
  BarChart3,
  Siren,
  ShieldCheck,
  Scaling,
  Cpu,
  FileText,
  ChevronLeft,
  ChevronRight,
  Search,
  Bell,
  ExternalLink,
  ArrowUp,
  ArrowDown,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  AlertTriangle,
} from "lucide-react"
import { cn } from "@/utils/cn"
import { useUxStore } from "@/store/uxStore"

// ──────────────────────────────────────
// TYPES
// ──────────────────────────────────────

type StatusTone = "healthy" | "degraded" | "critical" | "warning" | "info" | "pending"

// ──────────────────────────────────────
// TONE MAP (status string → tone)
// ──────────────────────────────────────

const TONE_MAP: Record<string, StatusTone> = {
  healthy: "healthy", degraded: "degraded", critical: "critical",
  warning: "warning", info: "info", pending: "pending",
  connected: "healthy", error: "critical", active: "healthy",
  inactive: "degraded", failed: "critical", success: "healthy",
  running: "info", completed: "healthy", passed: "healthy",
}

const toneStyles: Record<StatusTone, string> = {
  healthy:  "bg-[#ECFBF4] text-[#2F9F77]",
  degraded: "bg-[#FFFBEB] text-[#B45309]",
  critical: "bg-[#FEF2F2] text-[#B91C1C]",
  warning:  "bg-[#FFF7ED] text-[#C2410C]",
  info:     "bg-[#EFF6FF] text-[#2563EB]",
  pending:  "bg-[#F3F4F6] text-[#6B7280]",
}

const toneDots: Record<StatusTone, string> = {
  healthy:  "bg-[#38B88A]", degraded: "bg-[#F59E0B]", critical: "bg-[#EF4444]",
  warning:  "bg-[#F97316]", info:     "bg-[#3B82F6]", pending:  "bg-[#D1D5DB]",
}

// ──────────────────────────────────────
// NAV DATA
// ──────────────────────────────────────

interface NavItem {
  label: string
  href: string
  icon: React.ComponentType<{ size?: number; className?: string }>
}

const NAV_ITEMS: NavItem[] = [
  { label: "Performance Dashboard",  href: "/scale-reliability/performance",  icon: LayoutDashboard },
  { label: "Load Testing",           href: "/scale-reliability/load-testing",  icon: Zap },
  { label: "Stress Testing",         href: "/scale-reliability/stress-testing", icon: BarChart3 },
  { label: "Capacity Planning",      href: "/scale-reliability/capacity",     icon: Cpu },
  { label: "Failure Injection",      href: "/scale-reliability/failure",      icon: Siren },
  { label: "Reliability Dashboard",  href: "/scale-reliability/reliability",  icon: ShieldCheck },
  { label: "Scaling Simulator",      href: "/scale-reliability/scaling",      icon: Scaling },
  { label: "Resource Optimization",  href: "/scale-reliability/optimization", icon: Gauge },
  { label: "Executive Capacity Report", href: "/scale-reliability/report",    icon: FileText },
]

// ──────────────────────────────────────
// 1. ScaleReliabilitySidebar
// ──────────────────────────────────────

export function ScaleReliabilitySidebar({ collapsed: propCollapsed, onCollapse }: { collapsed?: boolean; onCollapse?: () => void }) {
  const [collapsed, setCollapsed] = useState(propCollapsed ?? false)
  const [pathname, setPathname] = useState("")

  useMemo(() => {
    if (typeof window !== "undefined") {
      setPathname(window.location.pathname)
    }
  }, [])

  return (
    <aside
      className={cn(
        "h-screen bg-white border-r border-[#E8EDF3] flex flex-col transition-all duration-300 shrink-0",
        collapsed ? "w-[60px]" : "w-[220px]"
      )}
    >
      <div className={cn("flex items-center gap-2 px-4 h-14 border-b border-[#E8EDF3]", collapsed && "justify-center px-0")}>
        <Gauge size={22} className="text-[#38B88A] shrink-0" />
        {!collapsed && (
          <span className="text-sm font-bold text-gray-800 whitespace-nowrap">
            Scale & Reliability
          </span>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href
          const Icon = item.icon
          return (
            <a
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                collapsed && "justify-center px-2",
                active
                  ? "bg-[#38B88A]/10 text-[#38B88A]"
                  : "text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              )}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </a>
          )
        })}
      </nav>

      <div className="border-t border-[#E8EDF3] p-2">
        <button
          onClick={() => setCollapsed((c) => !c)}
          className="flex items-center justify-center w-full rounded-xl py-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
    </aside>
  )
}

// ──────────────────────────────────────
// 2. ScaleReliabilityTopBar
// ──────────────────────────────────────

export function ScaleReliabilityTopBar({ sidebarWidth = 260 }: { sidebarWidth?: number }) {
  const unreadCount = useUxStore((s) => s.unreadCount)
  const setNotificationCenterOpen = useUxStore((s) => s.setNotificationCenterOpen)
  const notificationCenterOpen = useUxStore((s) => s.notificationCenterOpen)

  return (
    <header className="sticky top-0 z-30 h-14 bg-white/90 backdrop-blur-md border-b border-[#E8EDF3] flex items-center justify-between px-6">
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <Search size={16} className="text-gray-400 shrink-0" />
        <input
          type="text"
          placeholder="Search metrics, tests, reports..."
          className="flex-1 bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
        />
      </div>

      <div className="flex items-center gap-3">
        <a
          href="/operations-center"
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ExternalLink size={14} />
          Operations Center
        </a>
        <a
          href="/replay-center"
          className="flex items-center gap-1.5 text-xs font-medium text-gray-500 hover:text-gray-800 transition-colors"
        >
          <ExternalLink size={14} />
          Replay Center
        </a>

        <button
          onClick={() => setNotificationCenterOpen(!notificationCenterOpen)}
          className="relative p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
        >
          <Bell size={18} className="text-gray-500" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center w-4 h-4 rounded-full bg-[#EF4444] text-[9px] font-bold text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
      </div>
    </header>
  )
}

// ──────────────────────────────────────
// 3. StatusBadge
// ──────────────────────────────────────

export function StatusBadge(props: { tone?: StatusTone; label: string; status?: string }) {
  const tone = props.tone ?? TONE_MAP[props.status ?? ""] ?? "pending"
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.7rem] font-semibold", toneStyles[tone])}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDots[tone])} />
      {props.label}
    </span>
  )
}

// ──────────────────────────────────────
// 4. KpiCard
// ──────────────────────────────────────

export function KpiCard(props: {
  label?: string
  title?: string
  value: string | number
  trend?: { value: string; direction: "up" | "down" }
  change?: string
  subtitle?: string
  icon?: ReactNode
  color?: string
}) {
  const displayLabel = props.label ?? props.title ?? "Metric"
  const displayTrend = props.trend ?? (props.change ? { value: props.change, direction: "up" as const } : undefined)
  return (
    <div className="bg-white rounded-[18px] border border-[#E8EDF3] p-4 shadow-sm flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">{displayLabel}</span>
        {props.icon && (
          <span className="text-gray-400">{props.icon}</span>
        )}
      </div>
      <span className="text-2xl font-bold text-gray-900" style={props.color ? { color: props.color } : undefined}>
        {props.value}
      </span>
      {props.trend && (
        <div className="flex items-center gap-1">
          {props.trend.direction === "up" ? (
            <ArrowUp size={14} className="text-emerald-500" />
          ) : (
            <ArrowDown size={14} className="text-red-500" />
          )}
          <span className={cn("text-xs font-medium", props.trend.direction === "up" ? "text-emerald-600" : "text-red-500")}>
            {props.trend.value}
          </span>
        </div>
      )}
    </div>
  )
}

// ──────────────────────────────────────
// 5. ProgressBar
// ──────────────────────────────────────

export function ProgressBar(props: {
  label: string
  value: number
  color?: string
  size: "sm" | "md" | "lg"
  maxValue?: number
  max?: number
}) {
  const { label, value, color = "#38B88A", size, maxValue: _maxValue, max: _max } = props
  const maxValue = _maxValue ?? _max ?? 100
  const pct = Math.min(Math.max((value / maxValue) * 100, 0), 100)
  const heights = { sm: "h-1.5", md: "h-2.5", lg: "h-4" }
  const textSizes = { sm: "text-[10px]", md: "text-xs", lg: "text-sm" }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className={cn("font-medium text-gray-700", textSizes[size])}>{label}</span>
        <span className={cn("text-gray-500", textSizes[size])}>
          {value}{maxValue !== 100 ? ` / ${maxValue}` : ""}
        </span>
      </div>
      <div className={cn("w-full bg-[#F4F7FA] rounded-full overflow-hidden", heights[size])}>
        <div
          className={cn("rounded-full transition-all duration-700 ease-out", heights[size])}
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}

// ──────────────────────────────────────
// 6. GaugeChart
// ──────────────────────────────────────

interface GaugeChartProps {
  value: number
  label: string
  max?: number
  color?: string
  size?: "sm" | "md" | "lg"
}

export function GaugeChart({ value, label, max = 100, color = "#38B88A", size = "md" }: GaugeChartProps) {
  const pct = Math.min(Math.max(value / max, 0), 1)
  const dimensions = { sm: { w: 120, h: 70, sw: 8 }, md: { w: 180, h: 105, sw: 12 }, lg: { w: 240, h: 140, sw: 16 } }
  const { w, h, sw } = dimensions[size]
  const cx = w / 2
  const cy = h
  const r = Math.min(cx, cy) - sw / 2 - 4

  const arcPath = (startAngle: number, endAngle: number) => {
    const startRad = ((startAngle - 90) * Math.PI) / 180
    const endRad = ((endAngle - 90) * Math.PI) / 180
    const x1 = cx + r * Math.cos(startRad)
    const y1 = cy + r * Math.sin(startRad)
    const x2 = cx + r * Math.cos(endRad)
    const y2 = cy + r * Math.sin(endRad)
    const largeArc = endAngle - startAngle > 180 ? 1 : 0
    return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${r.toFixed(1)} ${r.toFixed(1)} 0 ${largeArc} 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`
  }

  const startAngle = 180
  const sweepAngle = 180
  const filledAngle = startAngle + sweepAngle * pct

  const bgPath = arcPath(startAngle, startAngle + sweepAngle)
  const fillPath = arcPath(startAngle, filledAngle)

  return (
    <div className="flex flex-col items-center">
      <svg width={w} height={h + 4} viewBox={`0 0 ${w} ${h + 4}`}>
        <path d={bgPath} fill="none" stroke="#F4F7FA" strokeWidth={sw} strokeLinecap="round" />
        <path d={fillPath} fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" />
        <text x={cx} y={h - r * 0.55} textAnchor="middle" className="text-lg font-bold fill-gray-900" fontSize={size === "lg" ? 22 : size === "md" ? 18 : 14}>
          {value}
        </text>
      </svg>
      <span className="text-xs font-medium text-gray-500 -mt-2">{label}</span>
    </div>
  )
}

// ──────────────────────────────────────
// 7. MetricRow
// ──────────────────────────────────────

export function MetricRow(props: {
  label: string
  value: string | number
  sparkline?: number[]
  trend?: { value: string; direction: "up" | "down" }
  color?: string
}) {
  const { label, value, sparkline, trend, color = "#38B88A" } = props
  const sw = 80
  const sh = 28

  const sparkPoints = useMemo(() => {
    if (!sparkline || sparkline.length < 2) return ""
    const min = Math.min(...sparkline)
    const max = Math.max(...sparkline)
    const range = max - min || 1
    return sparkline
      .map((v, i) => {
        const x = (i / (sparkline.length - 1)) * sw
        const y = sh - ((v - min) / range) * (sh - 4) - 2
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(" ")
  }, [sparkline])

  return (
    <div className="flex items-center justify-between py-2 px-1">
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="text-sm font-medium text-gray-700 truncate">{label}</span>
        {sparkline && sparkline.length >= 2 && (
          <svg width={sw} height={sh} viewBox={`0 0 ${sw} ${sh}`} className="shrink-0">
            <path d={sparkPoints} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-semibold text-gray-900">{value}</span>
        {trend && (
          <span className={cn("flex items-center gap-0.5 text-xs font-medium", trend.direction === "up" ? "text-emerald-600" : "text-red-500")}>
            {trend.direction === "up" ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
            {trend.value}
          </span>
        )}
      </div>
    </div>
  )
}

// ──────────────────────────────────────
// 8. SectionHeader
// ──────────────────────────────────────

export function SectionHeader(props: {
  title: string
  subtitle?: string
  actions?: ReactNode
  action?: ReactNode
}) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div className="min-w-0">
        <h3 className="text-base font-semibold text-gray-900">{props.title}</h3>
        {props.subtitle && (
          <p className="text-xs text-gray-500 mt-0.5">{props.subtitle}</p>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {props.actions}
        {props.action}
      </div>
    </div>
  )
}

// ──────────────────────────────────────
// 9. DataTable
// ──────────────────────────────────────

interface DataTableColumn {
  label: string
  key: string
  render?: (val: unknown, row: Record<string, unknown>) => ReactNode
}

interface DataTableProps {
  columns: DataTableColumn[]
  data?: Record<string, unknown>[]
  rows?: Record<string, unknown>[]
  onRowClick?: (row: Record<string, unknown>) => void
  selectedId?: string
  searchable?: boolean
  pageSize?: number
}

export function DataTable({
  columns,
  data,
  rows,
  onRowClick,
  selectedId,
  searchable,
  pageSize = 10,
}: DataTableProps) {
  const tableData = data ?? rows ?? []
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(0)
  const [pageSizeState, setPageSizeState] = useState(pageSize ?? 10)

  const filtered = useMemo(() => {
    if (!search) return tableData
    const q = search.toLowerCase()
    return tableData.filter((row) =>
      columns.some((col) => String(row[col.key] ?? "").toLowerCase().includes(q))
    )
  }, [tableData, search, columns])

  const sorted = useMemo(() => {
    if (!sortKey) return filtered
    return [...filtered].sort((a, b) => {
      const av = a[sortKey] ?? ""
      const bv = b[sortKey] ?? ""
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true })
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSizeState))
  const safePage = Math.min(page, totalPages - 1)
  const paged = sorted.slice(safePage * pageSizeState, (safePage + 1) * pageSizeState)

  const pageSizeOptions = [5, 10, 20, 50]

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortKey(key)
      setSortDir("asc")
    }
  }

  const SortIcon = ({ column }: { column: string }) => {
    if (sortKey !== column) return <ChevronsUpDown size={12} className="text-gray-300" />
    return sortDir === "asc" ? <ChevronUp size={12} className="text-[#38B88A]" /> : <ChevronDown size={12} className="text-[#38B88A]" />
  }

  return (
    <div className="space-y-2">
      {searchable && (
        <div className="flex items-center gap-2 px-3 py-2 bg-white border border-[#E8EDF3] rounded-xl">
          <Search size={14} className="text-gray-400 shrink-0" />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0) }}
            className="w-full bg-transparent text-sm text-gray-700 placeholder:text-gray-400 outline-none"
          />
          {search && (
            <button onClick={() => setSearch("")} className="text-gray-400 hover:text-gray-600 text-xs font-medium">
              Clear
            </button>
          )}
        </div>
      )}

      <div className="bg-white rounded-[18px] border border-[#E8EDF3] overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer select-none hover:text-gray-700 transition-colors"
                    onClick={() => handleSort(col.key)}
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      <SortIcon column={col.key} />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paged.length === 0 && search && (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-gray-400">
                    <div className="flex flex-col items-center gap-1">
                      <Search size={20} className="text-gray-300" />
                      <span>No results for &quot;{search}&quot;</span>
                      <button onClick={() => setSearch("")} className="text-[#38B88A] hover:underline text-xs font-medium">
                        Clear search
                      </button>
                    </div>
                  </td>
                </tr>
              )}
              {paged.length === 0 && !search && (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-8 text-center text-sm text-gray-400">
                    <div className="flex flex-col items-center gap-1">
                      <AlertTriangle size={20} className="text-gray-300" />
                      <span>No data available</span>
                    </div>
                  </td>
                </tr>
              )}
              {paged.length > 0 && paged.map((row, i) => {
  const rid = String(row.id ?? row.key ?? i)
  return <tr key={rid} onClick={() => onRowClick?.(row)} className={cn("border-b border-[#E8EDF3] last:border-b-0 transition-colors", onRowClick && "cursor-pointer hover:bg-gray-50", selectedId && selectedId === rid && "bg-[#38B88A]/5")}>
    {columns.map((col) => <td key={col.key} className="px-4 py-2.5 text-sm text-gray-700">{col.render ? col.render(row[col.key], row) : String(row[col.key] ?? "")}</td>)}
  </tr>
})}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-2.5 border-t border-[#E8EDF3] bg-white">
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">
                {sorted.length} result{sorted.length !== 1 ? "s" : ""}
              </span>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-400">Per page:</span>
                <select
                  value={pageSizeState}
                  onChange={(e) => { setPageSizeState(Number(e.target.value)); setPage(0) }}
                  className="text-xs font-medium text-gray-600 bg-transparent border border-[#E8EDF3] rounded-lg px-2 py-1 outline-none cursor-pointer hover:border-gray-300"
                >
                  {pageSizeOptions.map((opt) => (
                    <option key={opt} value={opt}>{opt}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={safePage === 0}
                className="px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Prev
              </button>
              {Array.from({ length: totalPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setPage(i)}
                  className={cn(
                    "w-7 h-7 rounded-lg text-xs font-medium transition-colors",
                    i === safePage
                      ? "bg-[#38B88A] text-white"
                      : "text-gray-500 hover:bg-gray-100"
                  )}
                >
                  {i + 1}
                </button>
              ))}
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={safePage === totalPages - 1}
                className="px-2 py-1 text-xs font-medium text-gray-500 hover:text-gray-800 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ──────────────────────────────────────
// 10. ResourceBar
// ──────────────────────────────────────

export function ResourceBar(props: {
  used: number
  total: number
  label: string
  color?: string
  unit?: string
}) {
  const { used, total, label, color = "#38B88A", unit = "" } = props
  const pct = total > 0 ? Math.min(Math.max((used / total) * 100, 0), 100) : 0
  const freePct = 100 - pct

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-gray-600">{label}</span>
        <span className="text-xs font-semibold text-gray-900">
          {used}{unit ? ` ${unit}` : ""} / {total}{unit ? ` ${unit}` : ""}
        </span>
      </div>
      <div className="flex h-2.5 rounded-full overflow-hidden bg-[#F4F7FA]">
        <div
          className="h-full rounded-l-full transition-all duration-500"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
        {freePct > 0 && (
          <div
            className="h-full rounded-r-full transition-all duration-500"
            style={{ width: `${freePct}%`, backgroundColor: color === "#38B88A" ? "#E8EDF3" : `${color}33` }}
          />
        )}
      </div>
    </div>
  )
}