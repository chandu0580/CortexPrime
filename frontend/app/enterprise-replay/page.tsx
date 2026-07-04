"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { EnterpriseReplaySidebar, EnterpriseReplayTopBar, ExportButton, ExecutionIdInput, KpiCard } from "@/components/enterprise-replay/shared"
import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { stagger, variants } from "@/lib/motion-tokens"
import { Archive, Activity, Bot, Clock3, TrendingUp, TriangleAlert, Workflow, CheckCircle2, ListRestart } from "lucide-react"

export default function EnterpriseReplayOverview() {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? 60 : 172
  const loadAll = useEnterpriseReplayStore((s) => s.loadAll)
  const executionId = useEnterpriseReplayStore((s) => s.executionId)
  const mission = useEnterpriseReplayStore((s) => s.mission)
  const workers = useEnterpriseReplayStore((s) => s.workers)
  const connectors = useEnterpriseReplayStore((s) => s.connectors)
  const costs = useEnterpriseReplayStore((s) => s.costs)
  const isLoading = useEnterpriseReplayStore((s) => s.isLoading)

  const handleLoad = (id: string) => loadAll(id)

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <EnterpriseReplaySidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <EnterpriseReplayTopBar sidebarWidth={sidebarWidth} />

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="mx-auto max-w-[1500px] space-y-5">
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Enterprise Replay Center</h1>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">Replay every mission, worker action, connector interaction, reasoning decision, memory update, and governance event.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <ExportButton executionId={executionId} />
              </div>
            </motion.div>

            <motion.div variants={variants.fadeUp}>
              <ExecutionIdInput onLoad={handleLoad} />
            </motion.div>

            {isLoading && (
              <div className="flex items-center justify-center py-12 text-[0.82rem] text-[#6B7280]">
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 0.9, ease: "linear" }}
                  className="w-4 h-4 border-2 border-[#E8EDF3] border-t-[#38B88A] rounded-full mr-3" />
                Loading enterprise replay data...
              </div>
            )}

            {mission?.found && !isLoading && (
              <>
                <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                  <KpiCard label="Total Events" value={String(mission.metrics?.total_events ?? 0)} icon={Archive} />
                  <KpiCard label="Mission Duration" value={mission.metrics?.duration_ms ? `${(mission.metrics.duration_ms as number / 1000).toFixed(1)}s` : "—"} icon={Clock3} />
                  <KpiCard label="Agents Used" value={String((mission.metrics?.agents as string[])?.length ?? 0)} icon={Bot} />
                  <KpiCard label="Avg Latency" value={mission.metrics?.avg_latency_ms ? `${(mission.metrics.avg_latency_ms as number).toFixed(0)}ms` : "—"} icon={Activity} />
                  <KpiCard label="Status" value={mission.status === "completed" ? "Completed" : "In Progress"} icon={CheckCircle2} tone={mission.status === "completed" ? "completed" : "running"} />
                </motion.div>

                <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {workers && (
                    <KpiCard label="Worker Actions" value={String(workers.total_actions)} icon={Workflow} trend={workers.total_actions > 0 ? "+active" : undefined} />
                  )}
                  {connectors && (
                    <KpiCard label="Connector Calls" value={String(connectors.total_calls)} icon={TrendingUp} />
                  )}
                  {costs && (
                    <KpiCard label="Total Cost" value={`$${costs.total_cost.toFixed(4)}`} icon={TrendingUp} />
                  )}
                  {costs && (
                    <KpiCard label="Total Tokens" value={(costs.summary.total_tokens as number ?? 0).toLocaleString()} icon={Activity} />
                  )}
                </motion.div>
              </>
            )}

            {!mission?.found && !isLoading && executionId && (
              <div className="text-center py-16 text-[0.9rem] text-[#6B7280]">
                <ListRestart className="h-12 w-12 mx-auto mb-4 text-[#D1D5DB]" />
                <p>No replay data found for this execution ID.</p>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </div>
  )
}