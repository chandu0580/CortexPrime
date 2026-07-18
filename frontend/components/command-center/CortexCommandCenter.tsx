"use client"

import { useState, useEffect } from "react"
import { motion } from "framer-motion"
import { stagger, variants } from "@/lib/motion-tokens"
import { useExecutiveStore } from "@/store/executiveStore"

import { PulseDot } from "./ExecPanel"
import { ExecutiveChatPanel } from "./ExecutiveChatPanel"
import { ConnectedEnterprisePanel } from "./ConnectedEnterprisePanel"
import { MissionQueuePanel } from "./MissionQueuePanel"
import { QuickActionsPanel } from "./QuickActionsPanel"

function MissionTimelinePanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function RunningWorkflowsPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function ActiveAgentsPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function EnterpriseHealthPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function RecentActivityPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function AlertsNotificationsPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function GovernanceStatusPanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }
function ResourceUsagePanel() { return <div className="flex items-center justify-center h-full rounded-xl border border-dashed border-white/10 bg-white/[0.02] p-6"><p className="text-xs text-white/30">Coming soon</p></div> }

import Link from "next/link"
import {
  Sparkles, RefreshCw, LayoutDashboard, Crosshair,
  Bot, Activity, ShieldCheck, BarChart3, Terminal,
} from "lucide-react"

export default function CortexCommandCenter() {
  const lastRefresh = useExecutiveStore((s) => s.lastRefresh)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    void useExecutiveStore.getState().refreshAll()
    const id = setInterval(() => {
      void useExecutiveStore.getState().refreshAll()
      setRefreshKey((k) => k + 1)
    }, 30000)
    return () => clearInterval(id)
  }, [])

  const refreshTime = lastRefresh
    ? new Date(lastRefresh).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : null

  return (
    <div className="min-h-screen bg-[#06080a] text-white">
      {/* Background effects */}
      <div className="fixed inset-0 pointer-events-none" style={{
        background: `
          radial-gradient(ellipse at 15% 8%, rgba(56,184,138,0.06) 0%, transparent 50%),
          radial-gradient(ellipse at 85% 12%, rgba(99,102,241,0.04) 0%, transparent 50%),
          radial-gradient(ellipse at 50% 90%, rgba(124,58,237,0.03) 0%, transparent 50%)
        `,
      }} />

      <div className="relative z-10 max-w-[1600px] mx-auto px-4 py-4 lg:px-6 lg:py-6">
        {/* ─── Header ─── */}
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between mb-5"
        >
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-600 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <LayoutDashboard className="w-5 h-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-xl font-bold tracking-tight text-white">Executive Command Center</h1>
                <PulseDot />
              </div>
              <p className="text-xs text-white/30 mt-0.5">
                {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}
                {refreshTime && <span className="ml-2 text-white/15">· Updated {refreshTime}</span>}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/executive-platform"
              className="text-[10px] text-white/30 hover:text-white/60 transition-colors flex items-center gap-1 px-2.5 py-1.5 rounded-lg hover:bg-white/5"
            >
              <Terminal className="w-3 h-3" />
              Executive Suite
            </Link>
            <button
              onClick={() => {
                void useExecutiveStore.getState().refreshAll()
                setRefreshKey((k) => k + 1)
              }}
              className="p-1.5 rounded-lg hover:bg-white/5 text-white/30 hover:text-white/60 transition-all"
            >
              <RefreshCw className="w-3.5 h-3.5" />
            </button>
          </div>
        </motion.div>

        {/* ─── Grid Layout ─── */}
        <div className="grid grid-cols-12 gap-3 auto-rows-min">
          {/* Row 1: Executive Chat (sticky, spans full height) + Mission Timeline */}
          <div className="col-span-12 lg:col-span-4 row-span-2 min-h-[400px] lg:min-h-[500px]">
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.05 }}
              className="h-full"
            >
              <ExecutiveChatPanel />
            </motion.div>
          </div>

          <div className="col-span-12 lg:col-span-5">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.08 }}
              className="h-full"
            >
              <MissionTimelinePanel />
            </motion.div>
          </div>

          <div className="col-span-12 lg:col-span-3">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="h-full"
            >
              <QuickActionsPanel />
            </motion.div>
          </div>

          {/* Row 2: Running Workflows + Enterprise Health + Mission Queue */}
          <div className="col-span-12 sm:col-span-6 lg:col-span-3">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.12 }}
              className="h-full"
            >
              <RunningWorkflowsPanel />
            </motion.div>
          </div>

          <div className="col-span-6 sm:col-span-3 lg:col-span-1">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.14 }}
              className="h-full"
            >
              <MissionQueuePanel />
            </motion.div>
          </div>

          <div className="col-span-6 sm:col-span-3 lg:col-span-1">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.16 }}
              className="h-full"
            >
              <EnterpriseHealthPanel />
            </motion.div>
          </div>

          {/* Row 3: Active Agents + Connected Enterprise + Alerts */}
          <div className="col-span-12 sm:col-span-4 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.18 }}
              className="h-full"
            >
              <ActiveAgentsPanel />
            </motion.div>
          </div>

          <div className="col-span-12 sm:col-span-4 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="h-full"
            >
              <ConnectedEnterprisePanel />
            </motion.div>
          </div>

          <div className="col-span-12 sm:col-span-4 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.22 }}
              className="h-full"
            >
              <GovernanceStatusPanel />
            </motion.div>
          </div>

          {/* Row 4: Recent Activity + Resource Usage + Alerts */}
          <div className="col-span-12 sm:col-span-6 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.24 }}
              className="h-full"
            >
              <AlertsNotificationsPanel />
            </motion.div>
          </div>

          <div className="col-span-12 sm:col-span-6 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.26 }}
              className="h-full"
            >
              <RecentActivityPanel />
            </motion.div>
          </div>

          <div className="col-span-12 sm:col-span-12 lg:col-span-2">
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.28 }}
              className="h-full"
            >
              <ResourceUsagePanel />
            </motion.div>
          </div>
        </div>

        {/* ─── Footer ─── */}
        <motion.footer
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="mt-6 pt-4 border-t border-white/5 flex items-center justify-between text-[10px] text-white/15"
        >
          <div className="flex items-center gap-3">
            <Sparkles className="w-3 h-3 text-emerald-400/50" />
            <span>CortexPrime Executive Command Center</span>
            <span>·</span>
            <span>Enterprise AI Operations Platform</span>
          </div>
          <div className="flex items-center gap-3">
            <span>All systems monitored in real-time</span>
            <span>·</span>
            <span>Data refreshes automatically</span>
          </div>
        </motion.footer>
      </div>
    </div>
  )
}