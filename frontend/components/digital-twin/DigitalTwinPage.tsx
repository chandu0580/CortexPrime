"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Box, Server, BarChart3, Cpu, HardDrive, Activity, RefreshCw, Globe, AlertTriangle, CheckCircle2 } from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import TopologyView from "@/components/digital-twin/TopologyView"
import SimulationPanel from "@/components/digital-twin/SimulationPanel"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

const tabs = [
  { id: "topology", label: "Infrastructure Topology", icon: Server },
  { id: "simulation", label: "Mission Simulation", icon: BarChart3 },
  { id: "metrics", label: "Live Metrics", icon: Activity },
]

const mockMetrics = [
  { label: "Total Clusters", value: "3", icon: Globe, change: "+1", color: "text-[var(--success)]", iconBg: "bg-[var(--success-muted)]" },
  { label: "Active Nodes", value: "24", icon: Server, change: "+2", color: "text-[var(--success)]", iconBg: "bg-[var(--success-muted)]" },
  { label: "Running Pods", value: "142", icon: HardDrive, change: "+12", color: "text-[var(--success)]", iconBg: "bg-[var(--success-muted)]" },
  { label: "Avg CPU", value: "62%", icon: Cpu, change: "+5%", color: "text-[var(--warning)]", iconBg: "bg-[var(--warning-muted)]" },
  { label: "Avg Memory", value: "78%", icon: Cpu, change: "+3%", color: "text-[var(--warning)]", iconBg: "bg-[var(--warning-muted)]" },
  { label: "Active Alerts", value: "4", icon: AlertTriangle, change: "-2", color: "text-[var(--danger)]", iconBg: "bg-[var(--danger-muted)]" },
]

export default function DigitalTwinPage() {
  const [activeTab, setActiveTab] = useState<"topology" | "simulation" | "metrics">("topology")

  return (
    <CortexShell title="Digital Twin" subtitle="Infrastructure topology & mission simulation">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6">
        <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[var(--success-muted)]">
              <Box size={18} className="text-[var(--success)]" />
            </div>
            <div>
              <h1 className="text-[1.3rem] font-extrabold text-[var(--text-primary)] tracking-tight">Digital Twin</h1>
              <p className="text-[0.75rem] text-[var(--text-secondary)]">Real-time infrastructure topology, simulation, and live metrics</p>
            </div>
          </div>
          <button
            aria-label="Refresh infrastructure data"
            className="flex items-center gap-1.5 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[0.75rem] font-semibold text-[var(--text-secondary)] hover:bg-[var(--surface-raised)]"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Sync
          </button>
        </motion.div>

        <motion.div variants={stagger(0.04)} initial="hidden" animate="visible" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {mockMetrics.map((m) => {
            const Icon = m.icon
            return (
              <div key={m.label} className="rounded-[14px] border border-[var(--border)] bg-[var(--surface)] p-4">
                <div className="flex items-center justify-between">
                  <span className="text-[0.65rem] font-semibold text-[var(--text-muted)] uppercase tracking-wider">{m.label}</span>
                  <Icon className={cn("h-4 w-4", m.color)} />
                </div>
                <p className="mt-1.5 text-[1.3rem] font-extrabold text-[var(--text-primary)] tracking-tight">{m.value}</p>
                <span className={cn("text-[0.65rem] font-semibold", m.change.startsWith("+") ? "text-[var(--success)]" : "text-[var(--danger)]")}>{m.change}</span>
              </div>
            )
          })}
        </motion.div>

        <div role="tablist" aria-label="Digital twin views" className="flex items-center gap-1 rounded-[12px] bg-[var(--surface-raised)] p-1 w-fit">
          {tabs.map((tab) => {
            const Icon = tab.icon
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={active}
                aria-controls={`tabpanel-${tab.id}`}
                id={`tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={cn(
                  "flex items-center gap-2 rounded-[10px] px-4 py-2 text-[0.8rem] font-semibold transition-all",
                  active ? "bg-[var(--surface)] text-[var(--success)] shadow-sm" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        <div aria-live="polite" aria-atomic="false">
          <motion.div key={activeTab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25 }}>
            {activeTab === "topology" && (
              <div
                role="tabpanel"
                id="tabpanel-topology"
                aria-labelledby="tab-topology"
                className="rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6"
              >
                <TopologyView />
              </div>
            )}
            {activeTab === "simulation" && (
              <div
                role="tabpanel"
                id="tabpanel-simulation"
                aria-labelledby="tab-simulation"
                className="rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6"
              >
                <SimulationPanel />
              </div>
            )}
            {activeTab === "metrics" && (
              <div
                role="tabpanel"
                id="tabpanel-metrics"
                aria-labelledby="tab-metrics"
                className="rounded-[16px] border border-[var(--border)] bg-[var(--surface)] p-6"
              >
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Activity className="h-12 w-12 text-[var(--text-muted)] mb-4" />
                  <p className="text-[0.9rem] font-semibold text-[var(--text-secondary)]">Live metrics dashboard</p>
                  <p className="text-[0.75rem] text-[var(--text-muted)] mt-1">Connect Prometheus to view real-time metrics</p>
                </div>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </CortexShell>
  )
}
