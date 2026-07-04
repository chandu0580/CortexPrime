"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { PortalSidebar, PortalTopBar, SearchOverlay } from "@/components/developer-portal/layout"
import { SECTIONS } from "@/components/developer-portal/content"
import { stagger, variants } from "@/lib/motion-tokens"
import { cn } from "@/utils/cn"
import { ArrowRight, BookOpen, Code, Sparkles } from "lucide-react"
import Link from "next/link"

export default function DeveloperPortalHome() {
  const [collapsed, setCollapsed] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const sidebarWidth = collapsed ? 60 : 220

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <PortalSidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <PortalTopBar sidebarWidth={sidebarWidth} onToggleSearch={() => setSearchOpen(true)} />
      {searchOpen && <SearchOverlay onClose={() => setSearchOpen(false)} />}

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1400px] space-y-6">

            <motion.div variants={variants.fadeUp} className="text-center py-8">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-[16px] bg-gradient-to-br from-[#38B88A] to-[#2F9F77] mb-4">
                <BookOpen className="h-7 w-7 text-white" />
              </div>
              <h1 className="text-[2rem] font-bold tracking-[-0.03em] text-[#111827]">CortexPrime Developer Portal</h1>
              <p className="mt-2 text-[0.95rem] text-[#6B7280] max-w-2xl mx-auto">
                Everything you need to understand, extend, integrate, and deploy CortexPrime — without reading source code.
              </p>
              <div className="flex items-center justify-center gap-2 mt-4">
                <Sparkles className="h-4 w-4 text-[#38B88A]" />
                <span className="text-[0.78rem] text-[#6B7280]">13 interactive sections &mdash; SDKs, APIs, tutorials, and playground</span>
              </div>
            </motion.div>

            <motion.div variants={stagger(0.03)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {SECTIONS.map((section) => (
                <Link key={section.id} href={`/developer-portal/${section.id}`}
                  className="group rounded-[18px] border border-[#E8EDF3] bg-white p-5 hover:shadow-md transition-all hover:border-[#38B88A]/30">
                  <div className="flex items-center gap-3 mb-3">
                    <span className="text-2xl">{section.icon}</span>
                    <div>
                      <p className="text-[0.85rem] font-bold text-[#111827] group-hover:text-[#2F9F77] transition-colors">{section.label}</p>
                    </div>
                  </div>
                  <p className="text-[0.72rem] text-[#6B7280] leading-relaxed">{section.description}</p>
                  <div className="flex items-center gap-1 mt-3 text-[0.7rem] font-semibold text-[#38B88A] opacity-0 group-hover:opacity-100 transition-opacity">
                    Explore <ArrowRight className="h-3 w-3" />
                  </div>
                </Link>
              ))}
            </motion.div>

            <motion.div variants={variants.fadeUp} className="rounded-[18px] border border-[#E8EDF3] bg-gradient-to-r from-[#ECFBF4] to-white p-6 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Code className="h-8 w-8 text-[#38B88A]" />
                <div>
                  <p className="text-[0.9rem] font-bold text-[#111827]">Ready to build?</p>
                  <p className="text-[0.75rem] text-[#6B7280]">Jump to the Code Playground for ready-to-copy examples</p>
                </div>
              </div>
              <Link href="/developer-portal/code-playground"
                className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-4 py-2 text-[0.8rem] font-semibold text-white hover:bg-[#2F9F77]">
                Open Playground <ArrowRight className="h-4 w-4" />
              </Link>
            </motion.div>

          </motion.div>
        </main>
      </div>
    </div>
  )
}