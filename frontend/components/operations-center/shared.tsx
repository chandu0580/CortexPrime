"use client"

import { motion } from "framer-motion"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Users,
  ShieldCheck,
  Brain,
  CircuitBoard,
  Plug,
  Key,
  Terminal,
  FileKey,
  RefreshCw,
  ClipboardList,
  Search,
  Bell,
  ChevronLeft,
  ChevronRight,
  Activity,
  ChevronUp,
  ChevronDown,
  Copy,
  Check,
  X,
  AlertTriangle,
  Info,
  Trash2,
  ChevronLeft as ChevronLeftIcon,
  ChevronRight as ChevronRightIcon,
} from "lucide-react"
import { useState, useMemo, useCallback, useEffect, useRef, type ReactNode } from "react"

import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

// ==========================================
// TYPES
// ==========================================

type StatusTone = "active" | "inactive" | "healthy" | "degraded" | "error" | "warning" | "pending" | "connected" | "running"

interface NavItem {
  icon: React.ComponentType<{ className?: string }>
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

interface ModalProps {
  title: string
  children: ReactNode
  onClose: () => void
  footer?: ReactNode
}

interface ConfirmDialogProps {
  title: string
  message: string
  confirmLabel?: string
  cancelLabel?: string
  onConfirm: () => void
  onCancel: () => void
  variant?: "danger" | "warning" | "info"
}

interface FormFieldProps {
  label: string
  children: ReactNode
  error?: string
  className?: string
}

interface TabsProps {
  tabs: { id: string; label: string }[]
  activeTab: string
  onChange: (id: string) => void
}

interface EmptyStateProps {
  icon?: React.ComponentType<React.SVGProps<SVGSVGElement> & { className?: string }>
  title: string
  description?: string
  action?: ReactNode
}

interface SectionHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
}

interface MetricRowProps {
  label: string
  value: string | number
  trend?: "up" | "down" | "neutral"
  trendValue?: string
}

interface CodeBlockProps {
  code: string
  language?: string
}

// ==========================================
// NAVIGATION
// ==========================================

const NAV: NavItem[] = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/operations" },
  { icon: Users, label: "Users", href: "/operations/users" },
  { icon: ShieldCheck, label: "Roles & Permissions", href: "/operations/roles" },
  { icon: Brain, label: "AI Models", href: "/operations/models" },
  { icon: CircuitBoard, label: "Workers", href: "/operations/workers" },
  { icon: Plug, label: "Connectors", href: "/operations/connectors" },
  { icon: Key, label: "Secrets", href: "/operations/secrets" },
  { icon: Terminal, label: "Runtime", href: "/operations/runtime" },
  { icon: FileKey, label: "Licensing", href: "/operations/licensing" },
  { icon: RefreshCw, label: "Platform Updates", href: "/operations/updates" },
  { icon: ClipboardList, label: "Audit", href: "/operations/audit" },
]

// ==========================================
// OPERATIONS SIDEBAR
// ==========================================

export function OperationsSidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
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
            <Activity className="w-4 h-4 text-white" />
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#38B88A] flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-bold text-[#111827] leading-tight">Enterprise</span>
              <span className="text-sm font-bold text-[#111827] leading-tight">Operations Center</span>
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
                  layoutId="opsSidebarIndicator"
                  className="ml-auto w-1.5 h-1.5 rounded-full bg-[#38B88A]"
                  transition={{ type: "spring" as const, stiffness: 380, damping: 30 }}
                />
              )}
            </Link>
          )
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-[#E8EDF3] p-3 space-y-3">
        {!collapsed && (
          <div className="flex items-center gap-2 px-3 py-2">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#38B88A] opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-[#38B88A]" />
            </span>
            <span className="text-xs font-medium text-[#38B88A]">All Systems Normal</span>
          </div>
        )}
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
// OPERATIONS TOP BAR
// ==========================================

export function OperationsTopBar({ sidebarWidth = 260 }: { sidebarWidth?: number }) {
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
          placeholder="Search operations..."
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
        <button className="flex items-center gap-2.5 px-2 py-1.5 rounded-xl hover:bg-[#F4F7FA] transition-all duration-150">
          <div className="w-8 h-8 rounded-full bg-[#38B88A] flex items-center justify-center text-white text-xs font-bold">
            AD
          </div>
          <div className="hidden sm:block text-left">
            <p className="text-sm font-medium text-[#111827] leading-tight">Admin User</p>
            <p className="text-xs text-[#6B7280] leading-tight">admin@cortexprime.io</p>
          </div>
        </button>
      </div>
    </header>
  )
}

// ==========================================
// STATUS BADGE
// ==========================================

const STATUS_COLORS: Record<StatusTone, { dot: string; bg: string; text: string }> = {
  active:    { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  inactive:  { dot: "#9CA3AF", bg: "bg-[#F3F4F6]", text: "text-[#6B7280]" },
  healthy:   { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  degraded:  { dot: "#F59E0B", bg: "bg-[#FEF3C7]", text: "text-[#B45309]" },
  error:     { dot: "#EF4444", bg: "bg-[#FEE2E2]", text: "text-[#B91C1C]" },
  warning:   { dot: "#F59E0B", bg: "bg-[#FEF3C7]", text: "text-[#B45309]" },
  pending:   { dot: "#6B7280", bg: "bg-[#F3F4F6]", text: "text-[#6B7280]" },
  connected: { dot: "#38B88A", bg: "bg-[#E8F5EE]", text: "text-[#2F9F77]" },
  running:   { dot: "#3B82F6", bg: "bg-[#DBEAFE]", text: "text-[#1D4ED8]" },
}

export function StatusBadge({ tone, label }: { tone: StatusTone; label: string }) {
  const colors = STATUS_COLORS[tone]
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium", colors.bg, colors.text)}>
      <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: colors.dot }} />
      {label}
    </span>
  )
}

// ==========================================
// KPI CARD
// ==========================================

export function KpiCard({
  label,
  value,
  trend,
  sparkline,
  icon: Icon,
  color = "#38B88A",
}: {
  label: string
  value: string | number
  trend?: { value: string; direction: "up" | "down" }
  sparkline?: number[]
  icon?: React.ComponentType<React.SVGProps<SVGSVGElement> & { className?: string }>
  color?: string
}) {
  return (
    <div className="border border-[#E8EDF3] bg-white rounded-[18px] p-5 shadow-sm hover:shadow-md transition-shadow duration-200">
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-medium text-[#6B7280] uppercase tracking-wider">{label}</span>
        {Icon && <Icon className="w-4 h-4" style={{ color }} />}
      </div>
      <div className="flex items-end justify-between">
        <div>
          <div className="text-2xl font-bold text-[#111827]" style={{ color }}>{value}</div>
          {trend && (
            <div className={cn("flex items-center gap-0.5 text-xs font-medium mt-1", trend.direction === "up" ? "text-[#38B88A]" : "text-[#EF4444]")}>
              {trend.direction === "up" ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              {trend.value}
            </div>
          )}
        </div>
        {sparkline && sparkline.length > 0 && (
          <div className="flex items-end gap-0.5 h-10">
            {sparkline.map((point, i) => (
              <div
                key={i}
                className="w-2 rounded-sm transition-all duration-200"
                style={{
                  height: `${point}%`,
                  backgroundColor: color,
                  opacity: 0.3 + (i / sparkline.length) * 0.7,
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// ==========================================
// DATA TABLE
// ==========================================

export function DataTable<T extends { [key: string]: any }>({
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
            <ChevronLeftIcon className="w-4 h-4" />
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
            <ChevronRightIcon className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}

// ==========================================
// MODAL
// ==========================================

export function Modal({ title, children, onClose, footer }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)

  const handleBackdrop = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === overlayRef.current) onClose()
    },
    [onClose],
  )

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose() }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [onClose])

  return (
    <motion.div
      ref={overlayRef}
      onClick={handleBackdrop}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      <motion.div
        className="bg-white rounded-[18px] shadow-xl w-full max-w-lg max-h-[90vh] flex flex-col"
        initial={{ opacity: 0, scale: 0.95, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 10 }}
        transition={{ duration: 0.2 }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#E8EDF3]">
          <h2 className="text-lg font-bold text-[#111827]">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] transition-colors duration-150"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="px-6 py-4 overflow-y-auto flex-1">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-[#E8EDF3] flex items-center justify-end gap-3">
            {footer}
          </div>
        )}
      </motion.div>
    </motion.div>
  )
}

// ==========================================
// CONFIRM DIALOG
// ==========================================

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  variant = "danger",
}: ConfirmDialogProps) {
  const confirmColors = {
    danger:  "bg-[#EF4444] hover:bg-[#DC2626] text-white",
    warning: "bg-[#F59E0B] hover:bg-[#D97706] text-white",
    info:    "bg-[#38B88A] hover:bg-[#2F9F77] text-white",
  }

  const iconMap = {
    danger:  <AlertTriangle className="w-5 h-5 text-[#EF4444]" />,
    warning: <AlertTriangle className="w-5 h-5 text-[#F59E0B]" />,
    info:    <Info className="w-5 h-5 text-[#38B88A]" />,
  }

  const bgMap = {
    danger:  "bg-[#FEE2E2]",
    warning: "bg-[#FEF3C7]",
    info:    "bg-[#E8F5EE]",
  }

  return (
    <Modal title={title} onClose={onCancel}>
      <div className="flex items-start gap-4">
        <div className={cn("p-2 rounded-xl shrink-0", bgMap[variant])}>
          {iconMap[variant]}
        </div>
        <div>
          <p className="text-sm text-[#6B7280]">{message}</p>
        </div>
      </div>
      <div className="flex items-center justify-end gap-3 mt-6">
        <button
          onClick={onCancel}
          className="px-4 py-2 rounded-[18px] text-sm font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150"
        >
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          className={cn("px-4 py-2 rounded-[18px] text-sm font-medium transition-colors duration-150", confirmColors[variant])}
        >
          {confirmLabel}
        </button>
      </div>
    </Modal>
  )
}

// ==========================================
// FORM FIELD
// ==========================================

export function FormField({ label, children, error, className }: FormFieldProps) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label className="text-sm font-medium text-[#111827]">{label}</label>
      {children}
      {error && <span className="text-xs text-[#EF4444]">{error}</span>}
    </div>
  )
}

// ==========================================
// TABS
// ==========================================

export function Tabs({ tabs, activeTab, onChange }: TabsProps) {
  return (
    <div className="flex border-b border-[#E8EDF3]">
      {tabs.map((tab) => {
        const isActive = tab.id === activeTab
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={cn(
              "relative px-4 py-3 text-sm font-medium transition-colors duration-150",
              isActive ? "text-[#38B88A]" : "text-[#6B7280] hover:text-[#111827]",
            )}
          >
            {tab.label}
            {isActive && (
              <motion.div
                layoutId="tabsIndicator"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#38B88A]"
                transition={{ type: "spring" as const, stiffness: 380, damping: 30 }}
              />
            )}
          </button>
        )
      })}
    </div>
  )
}

// ==========================================
// EMPTY STATE
// ==========================================

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
      {Icon && (
        <div className="p-3 rounded-full bg-[#F4F7FA] mb-4">
          <Icon className="w-8 h-8 text-[#9CA3AF]" />
        </div>
      )}
      <p className="text-base font-semibold text-[#111827]">{title}</p>
      {description && <p className="text-sm text-[#6B7280] mt-1 max-w-sm">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ==========================================
// SECTION HEADER
// ==========================================

export function SectionHeader({ title, subtitle, actions }: SectionHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 className="text-lg font-bold text-[#111827]">{title}</h2>
        {subtitle && <p className="text-sm text-[#6B7280] mt-0.5">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  )
}

// ==========================================
// METRIC ROW
// ==========================================

export function MetricRow({ label, value, trend, trendValue }: MetricRowProps) {
  const TrendIcon = trend === "up" ? ChevronUp : trend === "down" ? ChevronDown : null
  const trendColor = trend === "up" ? "text-[#38B88A]" : trend === "down" ? "text-[#EF4444]" : "text-[#6B7280]"

  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-sm text-[#6B7280]">{label}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-[#111827]">{value}</span>
        {(trend || trendValue) && (
          <span className={cn("flex items-center gap-0.5 text-xs font-medium", trendColor)}>
            {TrendIcon && <TrendIcon className="w-3 h-3" />}
            {trendValue}
          </span>
        )}
      </div>
    </div>
  )
}

// ==========================================
// CODE BLOCK
// ==========================================

export function CodeBlock({ code, language }: CodeBlockProps) {
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }, [code])

  return (
    <div className="rounded-[18px] overflow-hidden border border-[#E8EDF3]">
      {language && (
        <div className="flex items-center justify-between px-4 py-2 bg-[#1F2937] border-b border-[#374151]">
          <span className="text-xs text-[#9CA3AF] font-mono">{language}</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1.5 text-xs text-[#9CA3AF] hover:text-white transition-colors duration-150"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-[#38B88A]" />
                <span className="text-[#38B88A]">Copied</span>
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      )}
      <pre className="bg-[#111827] text-[#E5E7EB] p-4 overflow-x-auto text-sm font-mono leading-relaxed">
        <code>{code}</code>
      </pre>
    </div>
  )
}