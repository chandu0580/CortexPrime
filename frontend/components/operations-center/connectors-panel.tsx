"use client"

import {
  GitFork,
  Kanban,
  MessageSquare,
  MessageCircle,
  Headphones,
  FileText,
  Layout,
  Server,
  Plug,
  Settings,
  AlertTriangle,
  CheckCircle,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, SectionHeader } from "./shared"
import { useConnectors } from "@/hooks/queries/connectors"

const CONNECTOR_ICONS: Record<string, { icon: typeof GitFork; color: string }> = {
  github: { icon: GitFork, color: "#24292E" },
  jira: { icon: Kanban, color: "#0052CC" },
  slack: { icon: MessageSquare, color: "#4A154B" },
  "microsoft-teams": { icon: MessageCircle, color: "#6264A7" },
  "azure-devops": { icon: Server, color: "#0078D4" },
  confluence: { icon: FileText, color: "#0052CC" },
  servicenow: { icon: Headphones, color: "#81B136" },
  notion: { icon: Layout, color: "#000000" },
}

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function ConnectorsPanel() {
  const { data, isLoading } = useConnectors()
  const connectors = data?.connectors ?? []

  const connected = connectors.filter((c) => c.connection_state === "connected").length
  const errorCount = connectors.filter((c) => c.connection_state === "disconnected").length

  if (isLoading) {
    return <div className="text-[#6B7280] text-sm">Loading connectors...</div>
  }

  return (
    <div className="space-y-6">
      <SectionHeader title="Connectors" subtitle="Manage third-party integrations" />

      {/* Stats */}
      <div className="flex gap-4">
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] px-5 py-3 flex items-center gap-3">
          <Plug className="w-5 h-5 text-[#38B88A]" />
          <div>
            <span className="text-2xl font-bold text-[#111827]">{connectors.length}</span>
            <span className="text-sm text-[#6B7280] ml-1">Total</span>
          </div>
        </div>
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] px-5 py-3 flex items-center gap-3">
          <CheckCircle className="w-5 h-5 text-[#38B88A]" />
          <div>
            <span className="text-2xl font-bold text-[#38B88A]">{connected}</span>
            <span className="text-sm text-[#6B7280] ml-1">Connected</span>
          </div>
        </div>
        <div className="border border-[#E8EDF3] bg-white rounded-[18px] px-5 py-3 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-[#EF4444]" />
          <div>
            <span className="text-2xl font-bold text-[#EF4444]">{errorCount}</span>
            <span className="text-sm text-[#6B7280] ml-1">Disconnected</span>
          </div>
        </div>
      </div>

      {/* Connector Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {connectors.map((connector) => {
          const meta = CONNECTOR_ICONS[connector.type] ?? { icon: Plug, color: "#6B7280" }
          const Icon = meta.icon
          const connStatus = connector.connection_state === "connected" ? "connected" : "error"
          return (
            <div
              key={connector.type}
              className={cn(
                "border bg-white rounded-[18px] p-5 transition-all duration-200",
                connStatus === "error" ? "border-[#FEE2E2]" : "border-[#E8EDF3]",
              )}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${meta.color}10` }}>
                    <Icon className="w-5 h-5" style={{ color: meta.color }} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#111827]">{connector.name}</h3>
                    <StatusBadge tone={connStatus} label={connStatus} />
                  </div>
                </div>
                <div className={cn("w-2 h-2 rounded-full", connStatus === "connected" ? "bg-[#38B88A]" : "bg-[#EF4444]")} />
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-[#6B7280]">Latency</span><span className="text-[#111827] font-medium">{connector.latency_ms != null ? `${connector.latency_ms}ms` : "--"}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Auth</span><span className="text-[#111827] font-medium">{connector.authentication_type}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Status</span><span className={cn("font-medium", connStatus === "error" ? "text-[#EF4444]" : "text-[#38B88A]")}>{connector.connection_state}</span></div>
              </div>
              <div className="mt-4 pt-3 border-t border-[#E8EDF3]">
                <button className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-[18px] text-xs font-medium text-[#6B7280] hover:bg-[#F4F7FA] hover:text-[#111827] border border-[#E8EDF3] transition-colors duration-150">
                  <Settings className="w-3.5 h-3.5" />
                  Configure
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}