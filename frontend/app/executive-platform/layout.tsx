"use client"

import { ReactNode, useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, Crosshair, Terminal, MessageSquare, Play, Share2,
  History, BarChart3, Activity, PlugZap, ShieldCheck,
  Lock, Settings, ChevronLeft, ChevronRight, Sparkles, Brain, Bot, Shield,
} from "lucide-react"
import { cn } from "@/utils/cn"
import { IntelligenceOverlay } from "@/components/executive-intelligence/command-palette"
import { EnterpriseDataProvider } from "@/services/enterprise/EnterpriseDataProvider"

const NAV_ITEMS = [
  { href: "/executive-platform", icon: LayoutDashboard, label: "Executive Home" },
  { href: "/executive-platform/intelligence", icon: Brain, label: "Intelligence Hub" },
  { href: "/executive-platform/executive-agent", icon: Bot, label: "Executive Agent" },
  { href: "/executive-platform/demo-center", icon: Play, label: "Demo Center" },
  { href: "/executive-platform/certification", icon: Shield, label: "Certification" },
  { href: "/executive-platform/mission-control", icon: Crosshair, label: "Mission Control" },
  { href: "/executive-platform/live-console", icon: Terminal, label: "Live Agent Console" },
  { href: "/executive-platform/chat", icon: MessageSquare, label: "Executive Chat" },
  { href: "/executive-platform/knowledge-graph", icon: Share2, label: "Knowledge Graph" },
  { href: "/executive-platform/memory-timeline", icon: History, label: "Memory Timeline" },
  { href: "/executive-platform/analytics", icon: BarChart3, label: "Analytics" },
  { href: "/executive-platform/observability", icon: Activity, label: "Observability" },
  { href: "/executive-platform/connectors", icon: PlugZap, label: "Connectors" },
  { href: "/executive-platform/approvals", icon: ShieldCheck, label: "Approvals" },
  { href: "/executive-platform/security", icon: Lock, label: "Security" },
  { href: "/executive-platform/settings", icon: Settings, label: "Settings" },
]

export default function ExecutivePlatformLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <EnterpriseDataProvider>
      <div className="flex h-screen bg-[#0a0a0f] text-white overflow-hidden">
        <nav className={cn(
          "flex flex-col border-r border-white/5 bg-[#0d0d14] transition-all duration-300 relative",
          collapsed ? "w-16" : "w-56"
        )}>
          <div className="flex items-center gap-2 px-4 h-14 border-b border-white/5 shrink-0">
            <Sparkles className="w-5 h-5 text-emerald-400 shrink-0" />
            {!collapsed && <span className="text-sm font-semibold tracking-wide">CortexPrime</span>}
          </div>
          <div className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href || pathname.startsWith(item.href + "/")
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all",
                    active
                      ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                      : "text-white/40 hover:text-white/80 hover:bg-white/5"
                  )}
                >
                  <item.icon className="w-4 h-4 shrink-0" />
                  {!collapsed && <span>{item.label}</span>}
                </Link>
              )
            })}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center justify-center h-10 border-t border-white/5 text-white/30 hover:text-white/60"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </nav>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
        <IntelligenceOverlay />
      </div>
    </EnterpriseDataProvider>
  )
}