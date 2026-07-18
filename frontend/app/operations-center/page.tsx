"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { LayoutDashboard, Code2, GitBranch, MessageSquare, Container, Server, Activity, BarChart3, Settings, Cpu, Shield, Users, Puzzle, Bot, KeyRound, PlayCircle, FileKey, RefreshCw, Database, ScrollText, Building2 } from "lucide-react"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"
import CortexShell from "@/components/layout/CortexShell"
import { IntegrationStatusCards, GitHubPanel, JiraPanel, SlackPanel, DockerPanel, KubernetesPanel, PrometheusPanel, GrafanaPanel } from "@/components/operations-center/IntegrationPanels"

const navItems = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "github", label: "GitHub", icon: Code2 },
  { id: "jira", label: "Jira", icon: GitBranch },
  { id: "slack", label: "Slack", icon: MessageSquare },
  { id: "docker", label: "Docker", icon: Container },
  { id: "kubernetes", label: "Kubernetes", icon: Server },
  { id: "prometheus", label: "Prometheus", icon: Activity },
  { id: "grafana", label: "Grafana", icon: BarChart3 },
  { id: "users", label: "Users", icon: Users },
  { id: "roles", label: "Roles", icon: Shield },
  { id: "connectors", label: "Connectors", icon: Puzzle },
  { id: "workers", label: "Workers", icon: Bot },
  { id: "secrets", label: "Secrets", icon: KeyRound },
  { id: "audit", label: "Audit", icon: ScrollText },
]

export default function OperationsCenterPage() {
  const [activeTab, setActiveTab] = useState("dashboard")

  return (
    <CortexShell title="Operations Center" subtitle="Unified control plane for enterprise operations">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <div className="flex items-center gap-1 rounded-[12px] bg-[#F5F7FA] p-1 overflow-x-auto flex-wrap">
          {navItems.map((item) => {
            const Icon = item.icon
            return (
              <button key={item.id} onClick={() => setActiveTab(item.id)} className={cn(
                "flex items-center gap-1.5 rounded-[8px] px-3 py-1.5 text-[0.7rem] font-semibold transition-all whitespace-nowrap",
                activeTab === item.id ? "bg-white text-[#111827] shadow-sm" : "text-[#6B7280] hover:text-[#111827]"
              )}>
                <Icon className="h-3.5 w-3.5" /> {item.label}
              </button>
            )
          })}
        </div>

        <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.2 }}>
          {activeTab === "dashboard" && (
            <div className="space-y-6">
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
                <h2 className="text-[0.95rem] font-bold text-[#111827] mb-4">System Integrations</h2>
                <IntegrationStatusCards />
              </div>
            </div>
          )}
          {activeTab === "github" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <GitHubPanel />
            </div>
          )}
          {activeTab === "jira" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <JiraPanel />
            </div>
          )}
          {activeTab === "slack" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <SlackPanel />
            </div>
          )}
          {activeTab === "docker" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <DockerPanel />
            </div>
          )}
          {activeTab === "kubernetes" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <KubernetesPanel />
            </div>
          )}
          {activeTab === "prometheus" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <PrometheusPanel />
            </div>
          )}
          {activeTab === "grafana" && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <GrafanaPanel />
            </div>
          )}
          {(activeTab === "users" || activeTab === "roles" || activeTab === "connectors" || activeTab === "workers" || activeTab === "secrets" || activeTab === "audit") && (
            <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-6">
              <div className="flex flex-col items-center py-12 text-center">
                <Settings className="h-12 w-12 text-[#D1D5DB] mb-4" />
                <p className="text-[0.9rem] font-semibold text-[#6B7280] capitalize">{activeTab} Management</p>
                <p className="text-[0.75rem] text-[#9CA3AF] mt-1">This module is available in the admin panel</p>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </CortexShell>
  )
}
