"use client"

import { useState } from "react"
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
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react"

import { cn } from "@/utils/cn"
import { StatusBadge, SectionHeader } from "./shared"

// ─── TYPES ─────────────────────────────────────────────────────────────────────

interface Connector {
  id: string
  name: string
  icon: typeof GitFork
  color: string
  status: "connected" | "error"
  lastSync: string
  authMethod: string
  health: string
}

// ─── MOCK DATA ─────────────────────────────────────────────────────────────────

const CONNECTORS: Connector[] = [
  { id: "gh", name: "GitHub", icon: GitFork, color: "#24292E", status: "connected", lastSync: "2 min ago", authMethod: "OAuth 2.0", health: "All repos accessible" },
  { id: "jira", name: "Jira", icon: Kanban, color: "#0052CC", status: "connected", lastSync: "5 min ago", authMethod: "API Token", health: "All projects synced" },
  { id: "slack", name: "Slack", icon: MessageSquare, color: "#4A154B", status: "connected", lastSync: "1 min ago", authMethod: "OAuth 2.0", health: "Webhook active" },
  { id: "teams", name: "Teams", icon: MessageCircle, color: "#6264A7", status: "connected", lastSync: "10 min ago", authMethod: "Azure AD", health: "Channels active" },
  { id: "servicenow", name: "ServiceNow", icon: Headphones, color: "#81B136", status: "error", lastSync: "1 hour ago", authMethod: "Basic Auth", health: "Rate limit exceeded" },
  { id: "confluence", name: "Confluence", icon: FileText, color: "#0052CC", status: "connected", lastSync: "15 min ago", authMethod: "API Token", health: "Spaces synced" },
  { id: "notion", name: "Notion", icon: Layout, color: "#000000", status: "connected", lastSync: "8 min ago", authMethod: "Integration Token", health: "Databases accessible" },
  { id: "azure-devops", name: "Azure DevOps", icon: Server, color: "#0078D4", status: "connected", lastSync: "3 min ago", authMethod: "PAT", health: "Pipelines monitored" },
]

// ─── COMPONENT ─────────────────────────────────────────────────────────────────

export default function ConnectorsPanel() {
  const [connectors, setConnectors] = useState(CONNECTORS)

  const connected = connectors.filter((c) => c.status === "connected").length
  const error = connectors.filter((c) => c.status === "error").length

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
            <span className="text-2xl font-bold text-[#EF4444]">{error}</span>
            <span className="text-sm text-[#6B7280] ml-1">Error</span>
          </div>
        </div>
      </div>

      {/* Connector Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {connectors.map((connector) => {
          const Icon = connector.icon
          return (
            <div
              key={connector.id}
              className={cn(
                "border bg-white rounded-[18px] p-5 transition-all duration-200",
                connector.status === "error" ? "border-[#FEE2E2]" : "border-[#E8EDF3]",
              )}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ backgroundColor: `${connector.color}10` }}>
                    <Icon className="w-5 h-5" style={{ color: connector.color }} />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-[#111827]">{connector.name}</h3>
                    <StatusBadge tone={connector.status} label={connector.status} />
                  </div>
                </div>
                <div className={cn("w-2 h-2 rounded-full", connector.status === "connected" ? "bg-[#38B88A]" : "bg-[#EF4444]")} />
              </div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between"><span className="text-[#6B7280]">Last Sync</span><span className="text-[#111827] font-medium">{connector.lastSync}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Auth</span><span className="text-[#111827] font-medium">{connector.authMethod}</span></div>
                <div className="flex justify-between"><span className="text-[#6B7280]">Health</span><span className={cn("font-medium", connector.status === "error" ? "text-[#EF4444]" : "text-[#38B88A]")}>{connector.health}</span></div>
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