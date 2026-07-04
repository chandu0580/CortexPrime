"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { useParams } from "next/navigation"
import { PortalSidebar, PortalTopBar, SearchOverlay, SectionPage } from "@/components/developer-portal/layout"
import { SECTIONS, type SectionId } from "@/components/developer-portal/content"
import { stagger, variants } from "@/lib/motion-tokens"
import { ChevronLeft } from "lucide-react"
import Link from "next/link"

export default function DeveloperPortalSection() {
  const params = useParams<{ section: string }>()
  const sectionId = params.section as SectionId
  const section = SECTIONS.find((s) => s.id === sectionId)
  const [collapsed, setCollapsed] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const sidebarWidth = collapsed ? 60 : 220

  if (!section) {
    return (
      <div className="min-h-screen bg-[#F4F7FA] flex items-center justify-center">
        <p className="text-[1rem] text-[#6B7280]">Section not found</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <PortalSidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <PortalTopBar sidebarWidth={sidebarWidth} onToggleSearch={() => setSearchOpen(true)} />
      {searchOpen && <SearchOverlay onClose={() => setSearchOpen(false)} />}

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1400px]">
            <motion.div variants={variants.fadeUp} className="mb-6">
              <Link href="/developer-portal"
                className="inline-flex items-center gap-1 text-[0.72rem] font-semibold text-[#6B7280] hover:text-[#111827] mb-4">
                <ChevronLeft className="h-3.5 w-3.5" /> Back to Portal
              </Link>
            </motion.div>
            <motion.div variants={variants.fadeUp}>
              <SectionPage sectionId={sectionId} />
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  )
}