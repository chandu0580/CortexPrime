"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, Target, Bot, BookOpen, Activity,
  ShieldCheck, History, MessageSquare, Cpu, Settings,
  ChevronLeft,
} from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { useState } from "react"
import clsx from "clsx"

const navItems = [
  { icon: LayoutDashboard, label: "Dashboard", href: "/enterprise" },
  { icon: Target, label: "Mission Center", href: "/enterprise/missions" },
  { icon: Bot, label: "Agent Center", href: "/enterprise/agents" },
  { icon: BookOpen, label: "Knowledge Explorer", href: "/enterprise/knowledge" },
  { icon: Activity, label: "Operations", href: "/enterprise/operations" },
  { icon: ShieldCheck, label: "Governance", href: "/enterprise/governance" },
  { icon: History, label: "Replay", href: "/enterprise/replay" },
  { icon: MessageSquare, label: "AI Chat", href: "/enterprise/chat" },
  { icon: Cpu, label: "Digital Twin", href: "/enterprise/digital-twin" },
  { icon: Settings, label: "Settings", href: "/enterprise/settings" },
] as const

export default function EnterpriseSidebar() {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <motion.aside
      animate={{ width: collapsed ? 64 : 240 }}
      className={clsx(
        "h-full border-r border-[var(--border)] bg-[var(--surface)] flex flex-col shrink-0",
        "transition-[width] duration-300",
      )}
    >
      <div className="flex items-center justify-between p-4 border-b border-[var(--border)]">
        {!collapsed && (
          <span className="font-bold text-sm type-label text-[var(--text-primary)]">
            CORTEXPRIME
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-lg hover:bg-[var(--surface-raised)] text-[var(--text-muted)]"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <ChevronLeft className={clsx("w-4 h-4 transition-transform", collapsed && "rotate-180")} />
        </button>
      </div>

      <nav className="flex-1 py-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/")
          return (
            <Link key={item.href} href={item.href} className="block px-3">
              <motion.div
                whileHover={{ x: 4 }}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-xl transition-colors",
                  isActive
                    ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--surface-raised)]",
                )}
              >
                <item.icon className="w-5 h-5 shrink-0" />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      className="text-sm font-medium whitespace-nowrap overflow-hidden"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.div>
            </Link>
          )
        })}
      </nav>
    </motion.aside>
  )
}
