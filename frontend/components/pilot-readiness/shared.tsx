"use client"

import { motion, type Variants } from "framer-motion"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  Rocket,
  Monitor,
  Loader,
  BookOpen,
  Wrench,
  Settings,
  CheckCircle,
  Presentation,
  Bell,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Check,
  Minus,
  X,
  ArrowLeft,
  ArrowRight,
  type LucideIcon,
} from "lucide-react"
import { useState, useMemo, useEffect, type ReactNode } from "react"

import { cn } from "@/utils/cn"

// ==========================================
// TYPES
// ==========================================

type StatusTone = "connected" | "error" | "pending" | "active" | "inactive" | "healthy" | "degraded" | "running"

type ChecklistStatus = "pending" | "in_progress" | "completed" | "failed"

interface NavItem {
  icon: LucideIcon
  label: string
  href: string
}

interface Column<T> {
  label: string
  key: string
  render?: (row: T) => ReactNode
  sortable?: boolean
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  onRowClick?: (row: T) => void
  selectedId?: string | number
  idKey?: string
}

interface WizardContainerProps {
  steps?: string[]
  currentStep?: number
  onBack?: () => void
  onNext?: () => void
  onFinish?: () => void
  children: ReactNode
}

interface ChecklistItemProps {
  title: string
  description?: string
  status: ChecklistStatus
  action?: ReactNode
}

interface SetupCardProps {
  icon: LucideIcon
  title: string
  description?: string
  status?: string
  statusTone?: StatusTone
  action?: ReactNode
}

interface StatusBadgeProps {
  tone: StatusTone
  label: string
}

interface StepIndicatorProps {
  steps: string[]
  currentStep: number
}

// ==========================================
// NAVIGATION
// ==========================================

const NAV: NavItem[] = [
  { icon: Monitor, label: "Demo Environment", href: "/pilot-readiness" },
  { icon: Loader, label: "Demo Loader", href: "/pilot-readiness/demo-loader" },
  { icon: BookOpen, label: "Product Tour", href: "/pilot-readiness/product-tour" },
  { icon: Wrench, label: "Installation Wizard", href: "/pilot-readiness/installation" },
  { icon: Settings, label: "Configuration Wizard", href: "/pilot-readiness/configuration" },
  { icon: CheckCircle, label: "Deployment Validation", href: "/pilot-readiness/deployment-validation" },
  { icon: Presentation, label: "Presentation Mode", href: "/pilot-readiness/presentation" },
]

// ==========================================
// PILOT SIDEBAR
// ==========================================

export function PilotSidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  const pathname = usePathname()
  const sidebarWidth = collapsed ? 72 : 260

  return (
    <aside
      className={cn(
        "h-screen bg-white border-r border-[#E8EDF3] flex flex-col transition-all duration-300 fixed left-0 top-0 z-40",
      )}
      style={{ width: sidebarWidth }}
    >
      {/* Branding */}
      <div className={cn("flex items-center border-b border-[#E8EDF3] px-5 h-16 shrink-0", collapsed && "justify-center px-0")}>
        {collapsed ? (
          <div className="w-8 h-8 rounded-lg bg-[#38B88A] flex items-center justify-center">
            <Rocket className="w-4 h-4 text-white" />
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#38B88A] flex items-center justify-center">
              <Rocket className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-[#111827] leading-tight">Pilot</span>
              <span className="text-sm font-bold text-[#111827] leading-tight">Readiness</span>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5 scrollbar-thin">
        {NAV.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/")

          return (
            <Link
              key={item.label}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
                isActive
                  ? "bg-[#E8F5EE] text-[#2F9F77]"
                  : "text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827]",
                collapsed && "justify-center px-0",
              )}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={cn("w-5 h-5 shrink-0", isActive ? "text-[#38B88A]" : "text-[#9CA3AF]")} />
              {!collapsed && <span className="truncate">{item.label}</span>}
              {isActive && !collapsed && (
                <motion.div
                  layoutId="pilotSidebarIndicator"
                  className="ml-auto w-1.5 h-1.5 rounded-full bg-[#38B88A]"
                  transition={{ type: "spring" as const, stiffness: 380, damping: 30 }}
                />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[#E8EDF3] p-3">
        <button
          onClick={onCollapse}
          className={cn(
            "flex items-center justify-center w-full py-2 rounded-xl text-xs font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] transition-colors duration-150",
            collapsed && "py-2.5",
          )}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <><ChevronLeft className="w-4 h-4 mr-1.5" /> Collapse</>}
        </button>
      </div>
    </aside>
  )
}

// ==========================================
// PILOT TOP BAR
// ==========================================

export function PilotTopBar({ sidebarWidth = 260 }: { sidebarWidth?: number }) {
  return (
    <header
      className="h-16 bg-white border-b border-[#E8EDF3] fixed top-0 right-0 z-30 flex items-center justify-between px-6"
      style={{ left: sidebarWidth }}
    >
      {/* Search */}
      <div className="relative flex-1 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
        <input
          type="text"
          placeholder="Search pilot readiness..."
          className="w-full h-10 pl-10 pr-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] transition-all duration-150"
        />
      </div>

      {/* Right */}
      <div className="flex items-center gap-4">
        <button className="relative p-2 rounded-xl text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] transition-all duration-150">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#38B88A]" />
        </button>
        <div className="w-px h-8 bg-[#E8EDF3]" />
        <Link
          href="/operations"
          className="text-xs font-medium text-[#6B7280] hover:text-[#111827] transition-colors duration-150 px-2 py-1.5 rounded-xl hover:bg-[#F4F7FA]"
        >
          Operations Center
        </Link>
        <Link
          href="/developers"
          className="text-xs font-medium text-[#6B7280] hover:text-[#111827] transition-colors duration-150 px-2 py-1.5 rounded-xl hover:bg-[#F4F7FA]"
        >
          Developer Portal
        </Link>
      </div>
    </header>
  )
}

// ==========================================
// WIZARD CONTAINER
// ==========================================

export function WizardContainer({ steps = [], currentStep = 0, onBack, onNext, onFinish, children }: WizardContainerProps) {
  const isLast = currentStep === steps.length - 1

  return (
    <div className="flex flex-col h-full bg-[#F4F7FA]">
      {/* Steps Indicator */}
      <div className="bg-white border-b border-[#E8EDF3] px-8 py-6">
        <StepIndicator steps={steps} currentStep={currentStep} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {children}
      </div>

      {/* Footer */}
      <div className="bg-white border-t border-[#E8EDF3] px-8 py-4 flex items-center justify-between">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              className="flex items-center gap-2 px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
            >
              <ArrowLeft className="w-4 h-4" />
              Back
            </button>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-[#6B7280]">
            Step {currentStep + 1} of {steps.length}
          </span>
          {isLast ? (
            <button
              onClick={onFinish}
              className="px-6 py-2 rounded-[18px] text-sm font-medium text-white bg-[#38B88A] hover:bg-[#2F9F77] transition-colors duration-150"
            >
              Finish
            </button>
          ) : (
            <button
              onClick={onNext}
              className="flex items-center gap-2 px-6 py-2 rounded-[18px] text-sm font-medium text-white bg-[#38B88A] hover:bg-[#2F9F77] transition-colors duration-150"
            >
              Next
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ==========================================
// CHECKLIST ITEM
// ==========================================

const STATUS_ICONS: Record<ChecklistStatus, { icon: LucideIcon; className: string }> = {
  completed:   { icon: Check, className: "text-[#38B88A]" },
  failed:      { icon: X, className: "text-[#EF4444]" },
  in_progress: { icon: Loader, className: "text-[#F59E0B]" },
  pending:     { icon: Minus, className: "w-5 h-5 rounded-full border-2 border-[#D1D5DB]" },
}

export function ChecklistItem({ title, description, status, action }: ChecklistItemProps) {
  const StatusIcon = STATUS_ICONS[status]?.icon

  return (
    <div className="flex items-start gap-3 p-4 bg-white border border-[#E8EDF3] rounded-[18px] transition-shadow duration-150 hover:shadow-sm">
      {/* Status Icon */}
      <div className="shrink-0 mt-0.5">
        {status === "pending" ? (
          <div className="w-5 h-5 rounded-full border-2 border-[#D1D5DB]" />
        ) : (
          <StatusIcon className={cn("w-5 h-5", STATUS_ICONS[status]?.className)} />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span className={cn(
            "text-sm font-medium",
            status === "completed" ? "text-[#38B88A]" : "text-[#111827]",
          )}>
            {title}
          </span>
          {status === "in_progress" && (
            <span className="shrink-0 text-xs font-medium text-[#F59E0B]">In Progress</span>
          )}
          {status === "failed" && (
            <span className="shrink-0 text-xs font-medium text-[#EF4444]">Failed</span>
          )}
        </div>
        {description && (
          <p className="text-xs text-[#6B7280] mt-1">{description}</p>
        )}
      </div>

      {/* Action */}
      {action && <div className="shrink-0">{action}</div>}
    </div>
  )
}

// ==========================================
// SETUP CARD
// ==========================================

export function SetupCard({ icon: Icon, title, description, status, statusTone = "pending", action }: SetupCardProps) {
  return (
    <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex items-start gap-4">
        <div className="p-2.5 rounded-xl bg-[#F4F7FA] shrink-0">
          <Icon className="w-5 h-5 text-[#6B7280]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-sm font-semibold text-[#111827]">{title}</h3>
            {status && statusTone && (
              <StatusBadge tone={statusTone} label={status} />
            )}
          </div>
          {description && (
            <p className="text-xs text-[#6B7280] leading-relaxed">{description}</p>
          )}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </div>
    </div>
  )
}

// ==========================================
// DATA TABLE
// ==========================================

export function DataTable<T extends Record<string, any>>({
  columns,
  data,
  onRowClick,
  selectedId,
  idKey = "id",
}: DataTableProps<T>) {
  const [search, setSearch] = useState("")
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc")
  const [page, setPage] = useState(1)
  const perPage = 10

  const filtered = useMemo(() => {
    if (!search.trim()) return data
    const q = search.toLowerCase()
    return data.filter((row) =>
      columns.some((col) => {
        const val = row[col.key]
        return val != null && String(val).toLowerCase().includes(q)
      }),
    )
  }, [data, search, columns])

  const sorted = useMemo(() => {
    if (!sortKey) return filtered
    return [...filtered].sort((a, b) => {
      const aVal = a[sortKey]
      const bVal = b[sortKey]
      if (aVal == null) return 1
      if (bVal == null) return -1
      const cmp = typeof aVal === "number" ? aVal - bVal : String(aVal).localeCompare(String(bVal))
      return sortDir === "asc" ? cmp : -cmp
    })
  }, [filtered, sortKey, sortDir])

  const totalPages = Math.max(1, Math.ceil(sorted.length / perPage))
  const paginated = sorted.slice((page - 1) * perPage, page * perPage)

  useEffect(() => {
    if (page > totalPages) setPage(totalPages)
  }, [totalPages, page])

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"))
    } else {
      setSortKey(key)
      setSortDir("asc")
    }
  }

  return (
    <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
      {/* Search */}
      <div className="p-4 border-b border-[#E8EDF3]">
        <div className="relative max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            className="w-full h-10 pl-10 pr-4 rounded-[18px] bg-[#F4F7FA] border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A] transition-all duration-150"
          />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    "px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider",
                    col.sortable !== false && "cursor-pointer select-none hover:text-[#111827]",
                  )}
                  onClick={() => col.sortable !== false && handleSort(col.key)}
                >
                  <span className="flex items-center gap-1">
                    {col.label}
                    {sortKey === col.key && (
                      <span className="text-[#38B88A]">{sortDir === "asc" ? "\u2191" : "\u2193"}</span>
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-[#6B7280]">
                  No results found.
                </td>
              </tr>
            ) : (
              paginated.map((row) => {
                const id = row[idKey]
                const isSelected = selectedId != null && id != null && String(id) === String(selectedId)
                return (
                  <tr
                    key={id ?? Math.random()}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      "border-b border-[#E8EDF3] transition-colors duration-100",
                      onRowClick && "cursor-pointer",
                      isSelected ? "bg-[#E8F5EE]" : "hover:bg-[#F4F7FA]",
                    )}
                  >
                    {columns.map((col) => (
                      <td key={col.key} className="px-4 py-3 text-[#111827] whitespace-nowrap">
                        {col.render ? col.render(row) : (row[col.key] ?? "-")}
                      </td>
                    ))}
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-[#E8EDF3] bg-[#F4F7FA]">
        <span className="text-xs text-[#6B7280]">
          Showing {(page - 1) * perPage + 1}-{Math.min(page * perPage, sorted.length)} of {sorted.length}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            className="p-1.5 rounded-lg text-[#6B7280] hover:bg-white hover:text-[#111827] disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
            const start = Math.max(1, Math.min(page - 2, totalPages - 4))
            const p = start + i
            if (p > totalPages) return null
            return (
              <button
                key={p}
                onClick={() => setPage(p)}
                className={cn(
                  "w-8 h-8 rounded-lg text-xs font-medium transition-colors duration-150",
                  p === page
                    ? "bg-[#38B88A] text-white"
                    : "text-[#6B7280] hover:bg-white hover:text-[#111827]",
                )}
              >
                {p}
              </button>
            )
          })}
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            className="p-1.5 rounded-lg text-[#6B7280] hover:bg-white hover:text-[#111827] disabled:opacity-30 disabled:cursor-not-allowed transition-colors duration-150"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// STATUS BADGE
// ==========================================

const STATUS_COLORS: Record<StatusTone, { dot: string; bg: string; text: string }> = {
  connected: { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  error:     { dot: "#EF4444", bg: "bg-[#FEE2E2]", text: "text-[#B91C1C]" },
  pending:   { dot: "#6B7280", bg: "bg-[#F3F4F6]", text: "text-[#6B7280]" },
  active:    { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  inactive:  { dot: "#9CA3AF", bg: "bg-[#F3F4F6]", text: "text-[#6B7280]" },
  healthy:   { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  degraded:  { dot: "#F59E0B", bg: "bg-[#FEF3C7]", text: "text-[#B45309]" },
  running:   { dot: "#3B82F6", bg: "bg-[#DBEAFE]", text: "text-[#1D4ED8]" },
}

export function StatusBadge({ tone, label }: StatusBadgeProps) {
  const colors = STATUS_COLORS[tone]
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium", colors.bg, colors.text)}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.dot }} />
      {label}
    </span>
  )
}

// ==========================================
// STEP INDICATOR
// ==========================================

export function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
  return (
    <div className="flex items-center">
      {steps.map((label, i) => {
        const isActive = i === currentStep
        const isCompleted = i < currentStep

        return (
          <div key={label} className="flex items-center">
            {/* Circle + Label */}
            <div className="flex flex-col items-center">
              <div
                className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-200",
                  isCompleted && "bg-[#38B88A] text-white",
                  isActive && "bg-[#38B88A] text-white ring-4 ring-[#38B88A]/20",
                  !isCompleted && !isActive && "bg-[#F4F7FA] border-2 border-[#E8EDF3] text-[#6B7280]",
                )}
              >
                {isCompleted ? <Check className="w-4 h-4" /> : i + 1}
              </div>
              <span
                className={cn(
                  "text-xs mt-1.5 whitespace-nowrap font-medium",
                  isCompleted || isActive ? "text-[#111827]" : "text-[#6B7280]",
                )}
              >
                {label}
              </span>
            </div>

            {/* Connector Line */}
            {i < steps.length - 1 && (
              <div className={cn(
                "w-16 h-0.5 mx-3 mb-5 transition-colors duration-200",
                isCompleted ? "bg-[#38B88A]" : "bg-[#E8EDF3]",
              )} />
            )}
          </div>
        )
      })}
    </div>
  )
}
