"use client"

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Archive,
  BarChart2,
  Bot,
  Brain,
  ChevronLeft,
  ChevronRight,
  Globe,
  Home,
  MessageSquare,
  Mic,
  Monitor,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  Shield,
  Target,
  Zap,
} from "lucide-react";
import { cn } from "@/utils/cn";

const NAV = [
  { href: "/command",          label: "Dashboard",    icon: Home         },
  { href: "/runtime",          label: "Runtime",      icon: Zap          },
  { href: "/agents",           label: "Agents",       icon: Bot          },
  { href: "/chat",             label: "Chat",         icon: MessageSquare },
  { href: "/command#missions", label: "Missions",     icon: Target       },
  { href: "/voice",            label: "Voice",        icon: Mic          },
  { href: "/memory",           label: "Memory",       icon: Brain        },
  { href: "/workspace",        label: "Research",     icon: Search       },
  { href: "/operator",         label: "Computer Use", icon: Monitor      },
  { href: "/operator",         label: "Browser",      icon: Globe        },
  { href: "/replay",           label: "Replay",       icon: Archive      },
  { href: "/analytics",        label: "Analytics",    icon: BarChart2    },
  { href: "/governance",       label: "Governance",   icon: Shield       },
  { href: "/system-status",    label: "Monitoring",   icon: Activity     },
  { href: "/integrations",     label: "Integrations", icon: Puzzle       },
  { href: "/settings",         label: "Settings",     icon: Settings     },
];

export function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  const pathname = usePathname();

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#EAEFF5] bg-white transition-all duration-300",
        collapsed ? "w-[68px]" : "w-[220px]",
      )}
    >
      {/* Logo */}
      <div className={cn("flex items-center gap-2.5 px-4 py-5", collapsed && "justify-center px-0")}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-5 w-5 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round" />
            <path d="M24 13 31 17v14l-7 4-7-4V17l7-4Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round" />
          </svg>
        </div>
        {!collapsed && (
          <div>
            <p className="text-[0.95rem] font-bold leading-tight tracking-[-0.03em] text-[#111827]">CortexPrime</p>
            <p className="text-[0.68rem] font-medium text-[#9CA3AF]">AI Operating System</p>
          </div>
        )}
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== "/" && !href.includes("#") && pathname.startsWith(href));
          return (
            <Link
              key={label}
              href={href}
              className={cn(
                "flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 text-left transition-all",
                isActive
                  ? "bg-[#ECFBF4] text-[#2F9F77]"
                  : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]",
                collapsed && "justify-center px-0",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="text-[0.875rem] font-semibold">{label}</span>}
              {!collapsed && isActive && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-[#38B88A]" />}
            </Link>
          );
        })}
      </nav>

      {/* Bottom: system status + collapse */}
      <div className={cn("px-2 pb-4 space-y-2", collapsed && "px-1")}>
        {!collapsed && (
          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-2.5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
              <div className="flex-1 min-w-0">
                <p className="text-[0.72rem] font-semibold text-[#2F9F77]">System Status</p>
                <p className="text-[0.7rem] font-bold text-[#38B88A]">Healthy</p>
                <p className="text-[0.66rem] text-[#9CA3AF]">All systems operational</p>
              </div>
              <RefreshCw className="h-3.5 w-3.5 text-[#D1D5DB] cursor-pointer hover:text-[#38B88A]" />
            </div>
          </div>
        )}
        <button
          onClick={onCollapse}
          className={cn(
            "flex w-full items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.82rem] font-semibold text-[#6B7280] transition hover:bg-[#F8FAFC]",
            collapsed && "justify-center",
          )}
        >
          {collapsed
            ? <ChevronRight className="h-4 w-4" />
            : (<><ChevronLeft className="h-4 w-4" /><span>Collapse</span></>)
          }
        </button>
      </div>
    </aside>
  );
}
