"use client"

import { useState, useMemo } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  ClipboardList,
  Filter,
  Search,
  ChevronDown,
  ChevronRight,
  Calendar,
  User,
  ShieldCheck,
  Settings,
  Activity,
  Lock,
  X,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, DataTable, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface AuditEntry {
  id: string
  timestamp: string
  actor: string
  action: string
  resource: string
  category: "Admin" | "Security" | "Config" | "Platform"
  details: string
  payload: Record<string, any>
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const AUDIT_ENTRIES: AuditEntry[] = [
  { id: "AUD-001", timestamp: "2026-07-04 09:32:15", actor: "alice.j@acmecorp.com", action: "user.login", resource: "Auth System", category: "Admin", details: "Successful login from IP 192.168.1.42", payload: { ip: "192.168.1.42", user_agent: "Mozilla/5.0", mfa_used: true } },
  { id: "AUD-002", timestamp: "2026-07-04 09:28:03", actor: "system", action: "role.update", resource: "Role: Operator", category: "Security", details: "Permission 'missions.cancel' added to Operator role", payload: { role_id: "ROLE-003", permission_added: "missions.cancel", changed_by: "eve.d@cyberdyne.ai" } },
  { id: "AUD-003", timestamp: "2026-07-04 09:15:44", actor: "bob.s@globex.io", action: "mission.execute", resource: "Mission EX-2401", category: "Platform", details: "New penetration test mission started on network segment B", payload: { mission_id: "EX-2401", objective: "Penetration test - network segment B", agent: "Atlas" } },
  { id: "AUD-004", timestamp: "2026-07-04 09:00:12", actor: "eve.d@cyberdyne.ai", action: "connector.configure", resource: "Connector: GitHub", category: "Config", details: "GitHub PAT rotated and re-authenticated", payload: { connector_id: "gh", auth_method: "OAuth 2.0", status: "connected" } },
  { id: "AUD-005", timestamp: "2026-07-04 08:45:30", actor: "system", action: "backup.completed", resource: "PostgreSQL", category: "Platform", details: "Automated backup completed successfully (8.3 GB)", payload: { service: "PostgreSQL", size_gb: 8.3, status: "completed" } },
  { id: "AUD-006", timestamp: "2026-07-04 08:30:00", actor: "admin@cortexprime.io", action: "user.invite", resource: "User: henry@oscorp.lab", category: "Admin", details: "New user invited with Viewer role", payload: { email: "henry@oscorp.lab", role: "Viewer", org: "Oscorp" } },
  { id: "AUD-007", timestamp: "2026-07-04 08:15:22", actor: "system", action: "alert.triggered", resource: "Alert: CPU Threshold", category: "Platform", details: "CPU usage exceeded 80% threshold on worker w-1002", payload: { worker_id: "w-1002", metric: "cpu", value: 87, threshold: 80 } },
  { id: "AUD-008", timestamp: "2026-07-04 07:55:18", actor: "grace.w@stark.ind", action: "secret.read", resource: "Secret: openai-api-key", category: "Security", details: "Secret accessed by authorized operator for model routing", payload: { secret_id: "SEC-001", accessed_from: "model-router" } },
  { id: "AUD-009", timestamp: "2026-07-04 07:30:05", actor: "system", action: "update.installed", resource: "Platform Update v3.2.2", category: "Config", details: "Security patch v3.2.2 installed successfully", payload: { version: "v3.2.2", size_mb: 12, components_updated: ["runtime-scheduler", "auth-module"] } },
  { id: "AUD-010", timestamp: "2026-07-04 07:00:00", actor: "system", action: "license.sync", resource: "License Server", category: "Admin", details: "Daily license validation check passed", payload: { seats_used: 50, seats_total: 250, expiry: "2026-12-31" } },
  { id: "AUD-011", timestamp: "2026-07-03 23:59:59", actor: "system", action: "audit.export", resource: "Audit Log Archive", category: "Platform", details: "Daily audit log export completed (24,312 entries)", payload: { entries_count: 24312, export_format: "json", size_mb: 4.2 } },
  { id: "AUD-012", timestamp: "2026-07-03 18:22:10", actor: "frank.m@wayne.ent", action: "secret.rotation_failed", resource: "Secret: aws-secret-key", category: "Security", details: "Automatic rotation failed - AWS credential mismatch", payload: { secret_id: "SEC-008", error: "credential_mismatch", retry_count: 3 } },
]

const CATEGORIES = ["All", "Admin", "Security", "Config", "Platform"]
const CATEGORY_COLORS: Record<string, string> = {
  Admin: "#38B88A",
  Security: "#EF4444",
  Config: "#F59E0B",
  Platform: "#3B82F6",
}

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function AuditPanel() {
  const [search, setSearch] = useState("")
  const [categoryFilter, setCategoryFilter] = useState("All")
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [dateFrom, setDateFrom] = useState("2026-07-01")
  const [dateTo, setDateTo] = useState("2026-07-04")

  const filtered = useMemo(() => {
    return AUDIT_ENTRIES.filter((entry) => {
      const matchesSearch =
        !search ||
        entry.actor.toLowerCase().includes(search.toLowerCase()) ||
        entry.action.toLowerCase().includes(search.toLowerCase()) ||
        entry.resource.toLowerCase().includes(search.toLowerCase()) ||
        entry.details.toLowerCase().includes(search.toLowerCase())
      const matchesCategory = categoryFilter === "All" || entry.category === categoryFilter
      const entryDate = entry.timestamp.split(" ")[0]
      const matchesDate = entryDate >= dateFrom && entryDate <= dateTo
      return matchesSearch && matchesCategory && matchesDate
    })
  }, [search, categoryFilter, dateFrom, dateTo])

  return (
    <div className="space-y-6">
      <SectionHeader title="Audit Log" subtitle="Track all platform events and changes" />

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search audit entries..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full h-10 pl-10 pr-4 rounded-[18px] bg-white border border-[#E8EDF3] text-sm text-[#111827] placeholder:text-[#9CA3AF] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30 focus:border-[#38B88A]"
          />
        </div>

        {/* Category Chips */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-[#6B7280]" />
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(cat)}
              className={cn(
                "px-3 py-1.5 rounded-[18px] text-xs font-medium transition-colors duration-150",
                categoryFilter === cat
                  ? "bg-[#38B88A] text-white"
                  : "bg-white border border-[#E8EDF3] text-[#6B7280] hover:text-[#111827] hover:bg-[#F4F7FA]",
              )}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-2 ml-auto">
          <Calendar className="w-4 h-4 text-[#6B7280]" />
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-9 px-3 rounded-[18px] bg-white border border-[#E8EDF3] text-xs text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30"
          />
          <span className="text-xs text-[#6B7280]">to</span>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-9 px-3 rounded-[18px] bg-white border border-[#E8EDF3] text-xs text-[#111827] focus:outline-none focus:ring-2 focus:ring-[#38B88A]/30"
          />
        </div>
      </div>

      {/* Audit Table */}
      <div className="border border-[#E8EDF3] bg-white rounded-[18px] overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#E8EDF3] bg-[#F4F7FA]">
              {["Timestamp", "Actor", "Action", "Resource", "Category", "Details", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-[#6B7280] uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center text-sm text-[#6B7280]">
                  No audit entries found for the selected filters.
                </td>
              </tr>
            ) : (
              filtered.map((entry) => (
                <>
                  <tr
                    key={entry.id}
                    onClick={() => setExpandedId(expandedId === entry.id ? null : entry.id)}
                    className="border-b border-[#E8EDF3] cursor-pointer hover:bg-[#F4F7FA] transition-colors duration-100"
                  >
                    <td className="px-4 py-3 text-xs text-[#6B7280] whitespace-nowrap font-mono">{entry.timestamp}</td>
                    <td className="px-4 py-3 text-[#111827] whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        <User className="w-3.5 h-3.5 text-[#6B7280]" />
                        <span className="text-xs">{entry.actor}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <code className="text-xs font-mono bg-[#F4F7FA] px-2 py-0.5 rounded text-[#111827]">{entry.action}</code>
                    </td>
                    <td className="px-4 py-3 text-xs text-[#111827]">{entry.resource}</td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold"
                        style={{
                          backgroundColor: `${CATEGORY_COLORS[entry.category]}15`,
                          color: CATEGORY_COLORS[entry.category],
                        }}
                      >
                        {entry.category === "Admin" && <Settings className="w-3 h-3" />}
                        {entry.category === "Security" && <ShieldCheck className="w-3 h-3" />}
                        {entry.category === "Config" && <Lock className="w-3 h-3" />}
                        {entry.category === "Platform" && <Activity className="w-3 h-3" />}
                        {entry.category}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[#6B7280] max-w-[200px] truncate">{entry.details}</td>
                    <td className="px-4 py-3 text-right">
                      {expandedId === entry.id ? (
                        <ChevronDown className="w-4 h-4 text-[#38B88A] inline" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-[#9CA3AF] inline" />
                      )}
                    </td>
                  </tr>
                  {expandedId === entry.id && (
                    <tr key={`${entry.id}-detail`}>
                      <td colSpan={7} className="px-6 py-4 bg-[#F4F7FA]">
                        <div className="space-y-2">
                          <p className="text-xs font-semibold text-[#6B7280] uppercase tracking-wider">Full Payload</p>
                          <pre className="bg-[#111827] text-[#E5E7EB] p-4 rounded-xl text-xs font-mono leading-relaxed overflow-x-auto">
                            {JSON.stringify(entry.payload, null, 2)}
                          </pre>
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Stats */}
      <div className="flex gap-4 text-xs text-[#6B7280]">
        <span>Showing {filtered.length} of {AUDIT_ENTRIES.length} entries</span>
        {CATEGORIES.filter((c) => c !== "All").map((cat) => (
          <span key={cat}>
            {cat}: {AUDIT_ENTRIES.filter((e) => e.category === cat).length}
          </span>
        ))}
      </div>
    </div>
  )
}