"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { EnterpriseReplaySidebar, EnterpriseReplayTopBar, ExportButton, ExecutionIdInput } from "@/components/enterprise-replay/shared"
import { TimelineExplorerPanel } from "@/components/enterprise-replay/timeline-explorer"
import { useEnterpriseReplayStore } from "@/store/enterpriseReplayStore"
import { stagger, variants } from "@/lib/motion-tokens"
import { Clock } from "lucide-react"

export default function TimelineExplorerPage() {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? 60 : 172
  const loadTimeline = useEnterpriseReplayStore((s) => s.loadTimeline)
  const executionId = useEnterpriseReplayStore((s) => s.executionId)

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <EnterpriseReplaySidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <EnterpriseReplayTopBar sidebarWidth={sidebarWidth} />
      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="mx-auto max-w-[1500px] space-y-5">
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <Clock className="h-6 w-6 text-[#38B88A]" />
                  <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Timeline Explorer</h1>
                </div>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">Chronological execution with zoom, filter, search, and export.</p>
              </div>
              <ExportButton executionId={executionId} />
            </motion.div>
            <motion.div variants={variants.fadeUp}>
              <ExecutionIdInput onLoad={(id) => loadTimeline(id)} />
            </motion.div>
            <motion.div variants={variants.fadeUp}>
              <TimelineExplorerPanel />
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}