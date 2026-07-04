"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { OperationsSidebar, OperationsTopBar } from "@/components/operations-center/shared"
import { stagger, variants } from "@/lib/motion-tokens"
import LicensingPanel from "@/components/operations-center/licensing-panel"
import { ChevronLeft } from "lucide-react"
import Link from "next/link"

export default function OpsLicensingPage() {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? 60 : 220
  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <OperationsSidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <OperationsTopBar sidebarWidth={sidebarWidth} />
      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1500px]">
            <motion.div variants={variants.fadeUp} className="mb-4">
              <Link href="/operations-center" className="inline-flex items-center gap-1 text-[0.72rem] font-semibold text-[#6B7280] hover:text-[#111827]"><ChevronLeft className="h-3.5 w-3.5" /> Back</Link>
              <h1 className="text-[1.5rem] font-bold tracking-[-0.02em] text-[#111827] mt-2">Licensing</h1>
              <p className="text-[0.82rem] text-[#6B7280]">View license details, usage, consumption, seats, and expiry.</p>
            </motion.div>
            <motion.div variants={variants.fadeUp}><LicensingPanel /></motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}