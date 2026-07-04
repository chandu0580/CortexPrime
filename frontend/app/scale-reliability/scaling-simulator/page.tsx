"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { ScaleReliabilitySidebar, ScaleReliabilityTopBar } from "@/components/scale-reliability/shared"
import { stagger, variants } from "@/lib/motion-tokens"
import ScalingSimulatorPanel from "@/components/scale-reliability/scaling-simulator-panel"
import { ChevronLeft, Scale } from "lucide-react"
import Link from "next/link"

export default function ScalingSimulatorPage() {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? 60 : 220
  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <ScaleReliabilitySidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <ScaleReliabilityTopBar sidebarWidth={sidebarWidth} />
      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1500px]">
            <motion.div variants={variants.fadeUp} className="mb-4">
              <Link href="/scale-reliability" className="inline-flex items-center gap-1 text-[0.72rem] font-semibold text-[#6B7280] hover:text-[#111827]"><ChevronLeft className="h-3.5 w-3.5" /> Back</Link>
              <div className="flex items-center gap-2 mt-2">
                <Scale className="h-5 w-5 text-[#38B88A]" />
                <h1 className="text-[1.5rem] font-bold tracking-[-0.02em] text-[#111827]">Scaling Simulator</h1>
              </div>
              <p className="text-[0.82rem] text-[#6B7280]">Estimate pods, CPU, memory, storage, databases, cost, and performance at any scale.</p>
            </motion.div>
            <motion.div variants={variants.fadeUp}><ScalingSimulatorPanel /></motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}