"use client"

import { useState, useMemo } from "react"
import { motion } from "framer-motion"
import { OperationsSidebar, OperationsTopBar } from "@/components/operations-center/shared"
import { stagger, variants } from "@/lib/motion-tokens"
import { cn } from "@/utils/cn"
import DashboardPanel from "@/components/operations-center/dashboard-panel"
import Link from "next/link"
import { LayoutDashboard, Building2, Users, ShieldCheck, Cpu, Bot, Puzzle, KeyRound, PlayCircle, FileKey, RefreshCw, Database, ScrollText, ArrowRight } from "lucide-react"

const NAV = [
  { href: "/operations-center", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/operations-center/organizations", icon: Building2, label: "Organizations" },
  { href: "/operations-center/users", icon: Users, label: "Users" },
  { href: "/operations-center/roles", icon: ShieldCheck, label: "Roles & Permissions" },
  { href: "/operations-center/models", icon: Cpu, label: "AI Models" },
  { href: "/operations-center/workers", icon: Bot, label: "Workers" },
  { href: "/operations-center/connectors", icon: Puzzle, label: "Connectors" },
  { href: "/operations-center/secrets", icon: KeyRound, label: "Secrets" },
  { href: "/operations-center/runtime", icon: PlayCircle, label: "Runtime" },
  { href: "/operations-center/licensing", icon: FileKey, label: "Licensing" },
  { href: "/operations-center/updates", icon: RefreshCw, label: "Platform Updates" },
  { href: "/operations-center/backup", icon: Database, label: "Backup & Restore" },
  { href: "/operations-center/audit", icon: ScrollText, label: "Audit" },
]

export default function OperationsCenterHome() {
  const [collapsed, setCollapsed] = useState(false)
  const sidebarWidth = collapsed ? 60 : 220

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <OperationsSidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <OperationsTopBar sidebarWidth={sidebarWidth} />

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04)} className="mx-auto max-w-[1500px] space-y-6">

            <motion.div variants={variants.fadeUp} className="text-center py-8">
              <div className="inline-flex h-14 w-14 items-center justify-center rounded-[16px] bg-gradient-to-br from-[#38B88A] to-[#2F9F77] mb-4">
                <LayoutDashboard className="h-7 w-7 text-white" />
              </div>
              <h1 className="text-[1.8rem] font-bold tracking-[-0.03em] text-[#111827]">Enterprise Operations Center</h1>
              <p className="mt-2 text-[0.9rem] text-[#6B7280] max-w-2xl mx-auto">
                Unified administrative control plane for operating CortexPrime in production.
              </p>
            </motion.div>

            <motion.div variants={stagger(0.03)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {NAV.map(({ href, icon: Icon, label }) => (
                <Link key={label} href={href}
                  className="group rounded-[18px] border border-[#E8EDF3] bg-white p-5 hover:shadow-md transition-all hover:border-[#38B88A]/30">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-[12px] bg-[#ECFBF4] text-[#38B88A]">
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="text-[0.85rem] font-bold text-[#111827] group-hover:text-[#2F9F77] transition-colors">{label}</p>
                  </div>
                  <div className="flex items-center gap-1 text-[0.7rem] font-semibold text-[#38B88A] opacity-0 group-hover:opacity-100 transition-opacity">
                    Manage <ArrowRight className="h-3 w-3" />
                  </div>
                </Link>
              ))}
            </motion.div>

          </motion.div>
        </main>
      </div>
    </div>
  )
}