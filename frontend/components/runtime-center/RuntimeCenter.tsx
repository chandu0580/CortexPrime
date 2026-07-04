"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  Activity,
  Archive,
  BarChart2,
  Bell,
  Bot,
  Brain,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Database,
  Filter,
  Globe,
  Home,
  Mic,
  Monitor,
  MoreVertical,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  modelUsage,
  resources,
  runtimeEvents,
  runtimeMissions,
  type RuntimeTone,
} from "@/components/runtime-center/data";

// ─── Tone helpers ─────────────────────────────────────────────────────────────
const toneStyles: Record<string, string> = {
  running:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  healthy:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  searching: "bg-[#EFF6FF] text-[#3B82F6] ring-[#DBEAFE]",
  executing: "bg-[#EFF6FF] text-[#3B82F6] ring-[#DBEAFE]",
  thinking:  "bg-[#F5F3FF] text-[#7C3AED] ring-[#EDE9FE]",
  waiting:   "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]",
  queued:    "bg-[#FFF7ED] text-[#C2410C] ring-[#FED7AA]",
  warning:   "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  failed:    "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  idle:      "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]",
  info:      "bg-[#F8FAFC] text-[#374151] ring-[#E5E7EB]",
  finalizing:"bg-[#F5F3FF] text-[#7C3AED] ring-[#EDE9FE]",
};
const toneDot: Record<string, string> = {
  running:   "bg-[#38B88A]",
  healthy:   "bg-[#38B88A]",
  completed: "bg-[#38B88A]",
  searching: "bg-[#3B82F6]",
  executing: "bg-[#3B82F6]",
  thinking:  "bg-[#7C3AED]",
  waiting:   "bg-[#9CA3AF]",
  queued:    "bg-[#F97316]",
  warning:   "bg-[#F59E0B]",
  failed:    "bg-[#EF4444]",
  idle:      "bg-[#9CA3AF]",
  info:      "bg-[#6B7280]",
  finalizing:"bg-[#7C3AED]",
};

function Badge({ tone, children }: { tone: string; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.73rem] font-semibold ring-1", toneStyles[tone] ?? toneStyles.info)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone] ?? "bg-[#6B7280]")} />
      {children}
    </span>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("rounded-[20px] border border-[#EAEFF5] bg-white shadow-[0_2px_16px_rgba(148,163,184,0.07)]", className)}>
      {children}
    </div>
  );
}

function SectionHead({ title, action, extra }: { title: string; action?: React.ReactNode; extra?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <h2 className="text-[0.98rem] font-semibold text-[#111827]">{title}</h2>
        {extra}
      </div>
      {action && <span className="text-[0.8rem] font-semibold text-[#38B88A] cursor-pointer hover:underline">{action}</span>}
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",          label: "Dashboard",    icon: Home     },
  { href: "/runtime",          label: "Runtime",      icon: Zap      },
  { href: "/agents",           label: "Agents",       icon: Bot      },
  { href: "/command#missions", label: "Missions",     icon: Target   },
  { href: "/voice",            label: "Voice",        icon: Mic      },
  { href: "/memory",           label: "Memory",       icon: Brain    },
  { href: "/workspace",        label: "Research",     icon: Search   },
  { href: "/operator",         label: "Computer Use", icon: Monitor  },
  { href: "/operator",         label: "Browser",      icon: Globe    },
  { href: "/replay",           label: "Replay",       icon: Archive  },
  { href: "/analytics",        label: "Analytics",    icon: BarChart2 },
  { href: "/governance",       label: "Governance",   icon: Shield   },
  { href: "/system-status",    label: "Monitoring",   icon: Activity },
  { href: "/integrations",     label: "Integrations", icon: Puzzle   },
  { href: "/settings",         label: "Settings",     icon: Settings },
];

function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  const pathname = usePathname();
  return (
    <aside className={cn("fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#EAEFF5] bg-white transition-all duration-300", collapsed ? "w-[68px]" : "w-[220px]")}>
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

      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href || (href !== "/" && !href.includes("#") && pathname.startsWith(href));
          return (
            <Link
              key={label}
              href={href}
              className={cn(
                "flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 transition-all",
                isActive ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]",
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
          className={cn("flex w-full items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.82rem] font-semibold text-[#6B7280] transition hover:bg-[#F8FAFC]", collapsed && "justify-center")}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : (<><ChevronLeft className="h-4 w-4" /><span>Collapse</span></>)}
        </button>
      </div>
    </aside>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ collapsed }: { collapsed: boolean }) {
  const avatar = useMemo(() =>
    `data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`)}`, []);

  return (
    <header className={cn("sticky top-0 z-30 flex items-center gap-3 border-b border-[#EAEFF5] bg-white/96 px-5 py-3 backdrop-blur transition-all duration-300", collapsed ? "pl-[80px]" : "pl-[232px]")}>
      <label className="relative flex h-10 w-[230px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#9CA3AF]" />
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] pl-10 pr-14 text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]" />
        <span className="absolute right-3 rounded-[7px] border border-[#E5E7EB] bg-white px-1.5 py-0.5 text-[0.66rem] font-semibold text-[#9CA3AF]">⌘K</span>
      </label>

      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 xl:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Target className="h-3.5 w-3.5" /></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <p className="text-[0.8rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
        </div>
        <Badge tone="running">Running</Badge>
        <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
      </div>

      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 lg:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Mic className="h-3.5 w-3.5" /></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.8rem] font-semibold text-[#111827]">Listening...</p>
        </div>
        <motion.span animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.4, repeat: Infinity }} className="h-2 w-2 rounded-full bg-[#38B88A] shadow-[0_0_5px_#38B88A]" />
      </div>

      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white">2</span>
        </button>
        <Link href="/settings" className="flex items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-white px-2.5 py-1.5 transition hover:bg-[#F8FAFC]">
          <Image src={avatar} alt="Alex Morgan" width={32} height={32} className="rounded-[10px]" />
          <div className="hidden xl:block">
            <p className="text-[0.82rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.7rem] text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
        </Link>
      </div>
    </header>
  );
}

// ─── KPI Cards ─────────────────────────────────────────────────────────────────
const KPI_METRICS = [
  { label: "Active Executions", value: "24", trend: "+14%",   color: "#38B88A", data: [14,16,18,20,21,23,22,25,24] },
  { label: "Total Tokens / min", value: "2.45M", trend: "+7.2%", color: "#38B88A", data: [1.8,1.9,2.0,2.1,2.2,2.3,2.35,2.4,2.45] },
  { label: "Avg. Latency",      value: "92ms",  trend: "+8.4%",  color: "#38B88A", data: [110,108,105,102,100,97,95,93,92] },
  { label: "Success Rate",      value: "98.7%", trend: "+1.8%",  color: "#38B88A", data: [95,96,96.5,97,97.5,98,98.2,98.5,98.7] },
  { label: "Cost / hour",       value: "$124.58",trend: "+3.3%", color: "#38B88A", data: [105,108,110,114,116,119,121,123,124.58] },
];

function KpiCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {KPI_METRICS.map((m) => (
        <Card key={m.label} className="px-4 py-3.5">
          <p className="text-[0.77rem] font-medium text-[#9CA3AF]">{m.label}</p>
          <p className="mt-1.5 text-[1.75rem] font-bold leading-none tracking-[-0.04em] text-[#111827]">{m.value}</p>
          <div className="mt-2.5 flex items-end justify-between gap-2">
            <p className="text-[0.78rem] font-semibold text-[#38B88A]">
              {m.trend} <span className="font-normal text-[#9CA3AF]">vs 1 hour ago</span>
            </p>
            <div className="h-8 w-[70px] shrink-0" aria-hidden>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={m.data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                  <Area type="monotone" dataKey="v" stroke={m.color} strokeWidth={1.8} fill={m.color} fillOpacity={0.1} dot={false} isAnimationActive />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

// ─── Live Executions Table ─────────────────────────────────────────────────────
function statusLabel(s: string) {
  if (s === "running")   return "Running";
  if (s === "searching") return "Running";
  if (s === "executing") return "Running";
  if (s === "thinking")  return "Running";
  if (s === "waiting")   return "Running";
  if (s === "queued")    return "Queued";
  if (s === "finalizing")return "Finalizing";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const EXEC_ICON_MAP: Record<string, React.ElementType> = {
  "Research Agent": Search,
  "Browser Agent": Globe,
  "Voice Agent": Mic,
  "Computer Use Agent": Monitor,
  "Memory Agent": Database,
  "Analytics Agent": BarChart2,
  "Supervisor": ShieldCheck,
};

function LiveExecutions() {
  return (
    <Card className="p-5">
      <SectionHead
        title="Live Executions"
        action="View All"
        extra={
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ECFBF4] px-2.5 py-[3px] text-[0.73rem] font-semibold text-[#2F9F77]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
            {runtimeMissions.length} Running
          </span>
        }
      />
      <div className="space-y-2">
        {runtimeMissions.map((m) => {
          const Icon = EXEC_ICON_MAP[m.agent] ?? Bot;
          const isQueued = m.status === "queued";
          const label = isQueued ? "Queued" : m.name === "Executive Brief Generation" ? "Finalizing" : "Running";
          const tone = isQueued ? "queued" : m.name === "Executive Brief Generation" ? "finalizing" : "running";
          return (
            <div key={m.id} className="flex items-center gap-3 rounded-[12px] border border-[#F0F4F8] bg-[#FAFCFE] px-3.5 py-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.84rem] font-semibold text-[#111827]">{m.name}</p>
                <p className="truncate text-[0.73rem] text-[#9CA3AF]">{m.agent}</p>
              </div>
              <span className="w-12 shrink-0 text-right text-[0.78rem] text-[#9CA3AF]">{m.runtime}</span>
              {/* Progress bar */}
              <div className="hidden w-[90px] shrink-0 sm:block">
                <div className="h-1.5 overflow-hidden rounded-full bg-[#EEF2F7]">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${m.progress}%` }}
                    transition={{ duration: 0.8 }}
                    className="h-full rounded-full bg-[#38B88A]"
                  />
                </div>
              </div>
              <span className="hidden w-8 shrink-0 text-right text-[0.78rem] font-semibold text-[#374151] sm:block">{m.progress}%</span>
              <Badge tone={tone}>{label}</Badge>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Runtime Flow Diagram ──────────────────────────────────────────────────────
const FLOW_AGENTS = [
  { label: "Research Agent", status: "Running" },
  { label: "Browser Agent",  status: "Running" },
  { label: "Memory Agent",   status: "Running" },
  { label: "Computer Agent", status: "Running" },
];
const FLOW_ICON_MAP: Record<string, React.ElementType> = {
  "Research Agent": Search,
  "Browser Agent":  Globe,
  "Memory Agent":   Database,
  "Computer Agent": Monitor,
};

function RuntimeFlow() {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[0.98rem] font-semibold text-[#111827]">Runtime Flow</h2>
        <div className="flex items-center gap-2">
          <button className="flex items-center gap-1.5 rounded-[10px] border border-[#EAEFF5] bg-white px-2.5 py-1.5 text-[0.78rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
            Live Graph <ChevronDown className="h-3.5 w-3.5" />
          </button>
          <button className="flex h-8 w-8 items-center justify-center rounded-[10px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
            <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M1 1h5v5H1zM10 1h5v5h-5zM1 10h5v5H1zM10 10h5v5h-5z" />
            </svg>
          </button>
        </div>
      </div>

      {/* SVG Flow diagram */}
      <div className="relative flex items-center gap-4 overflow-x-auto rounded-[16px] bg-[#F8FAFC] p-5">
        {/* Trigger/Schedule */}
        <div className="flex shrink-0 flex-col items-center text-center">
          <div className="rounded-[12px] border border-[#EAEFF5] bg-white px-3.5 py-2.5 shadow-sm">
            <p className="text-[0.78rem] font-semibold text-[#374151]">Trigger</p>
            <p className="text-[0.68rem] text-[#9CA3AF]">Schedule</p>
            <p className="mt-1 text-[0.7rem] text-[#9CA3AF]">10:30 AM</p>
          </div>
        </div>

        {/* Arrow */}
        <svg viewBox="0 0 32 16" className="h-4 w-8 shrink-0" fill="none">
          <line x1="0" y1="8" x2="24" y2="8" stroke="#38B88A" strokeWidth="2" />
          <polyline points="18,4 24,8 18,12" stroke="#38B88A" strokeWidth="2" strokeLinejoin="round" />
          <circle cx="4" cy="8" r="3.5" fill="#38B88A" />
        </svg>

        {/* Supervisor */}
        <div className="flex shrink-0 flex-col items-center text-center">
          <div className="rounded-[14px] border border-[#38B88A]/30 bg-white px-4 py-3 shadow-[0_0_0_3px_rgba(56,184,138,0.08)]">
            <div className="mx-auto mb-1.5 flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
              <ShieldCheck className="h-4.5 w-4.5" />
            </div>
            <p className="text-[0.8rem] font-semibold text-[#111827]">Supervisor</p>
            <p className="text-[0.68rem] text-[#9CA3AF]">Cortex Supervisor</p>
            <Badge tone="running">Running</Badge>
          </div>
        </div>

        {/* Arrow */}
        <svg viewBox="0 0 32 16" className="h-4 w-8 shrink-0" fill="none">
          <line x1="0" y1="8" x2="24" y2="8" stroke="#38B88A" strokeWidth="2" />
          <polyline points="18,4 24,8 18,12" stroke="#38B88A" strokeWidth="2" strokeLinejoin="round" />
          <circle cx="4" cy="8" r="3.5" fill="#38B88A" />
        </svg>

        {/* Agent cluster */}
        <div className="flex shrink-0 flex-col gap-2">
          {FLOW_AGENTS.map((ag) => {
            const Icon = FLOW_ICON_MAP[ag.label] ?? Bot;
            return (
              <div key={ag.label} className="flex items-center gap-2.5 rounded-[12px] border border-[#EAEFF5] bg-white px-3 py-2">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]">
                  <Icon className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-[0.78rem] font-semibold text-[#111827]">{ag.label}</p>
                  <p className="text-[0.68rem] text-[#38B88A]">{ag.status}</p>
                </div>
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                  className="ml-1 h-2 w-2 shrink-0 rounded-full bg-[#38B88A] shadow-[0_0_5px_#38B88A]"
                />
              </div>
            );
          })}
        </div>

        {/* Arrow */}
        <svg viewBox="0 0 32 16" className="h-4 w-8 shrink-0" fill="none">
          <line x1="0" y1="8" x2="24" y2="8" stroke="#38B88A" strokeWidth="2" />
          <polyline points="18,4 24,8 18,12" stroke="#38B88A" strokeWidth="2" strokeLinejoin="round" />
          <circle cx="4" cy="8" r="3.5" fill="#38B88A" />
        </svg>

        {/* Output */}
        <div className="flex shrink-0 flex-col gap-1.5">
          <div className="rounded-[12px] border border-[#EAEFF5] bg-white px-3.5 py-2.5">
            <p className="text-[0.78rem] font-semibold text-[#374151]">Output</p>
          </div>
          <div className="rounded-[12px] border border-[#EAEFF5] bg-white px-3.5 py-2.5">
            <p className="text-[0.78rem] font-semibold text-[#374151]">Mission Output</p>
            <p className="text-[0.68rem] text-[#9CA3AF]">Generating</p>
          </div>
        </div>
      </div>
    </Card>
  );
}

// ─── Resource Utilization ─────────────────────────────────────────────────────
const RESOURCE_DATA = [
  { label: "CPU",     value: "32%", color: "#38B88A", icon: Zap,      data: [18,22,21,29,27,32,30,35,32] },
  { label: "Memory",  value: "61%", color: "#3B82F6", icon: Database,  data: [48,54,53,58,60,62,59,61,61] },
  { label: "GPU",     value: "24%", color: "#8B5CF6", icon: Sparkles,  data: [22,24,23,26,21,24,25,23,24] },
  { label: "Network", value: "18%", color: "#F59E0B", icon: Globe,     data: [12,14,13,19,18,21,17,18,18] },
];

function ResourceUtilization() {
  return (
    <Card className="p-5">
      <SectionHead title="Resource Utilization" action="View All" />
      <div className="space-y-3">
        {RESOURCE_DATA.map((r) => (
          <div key={r.label} className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#F8FAFC]" style={{ color: r.color }}>
              <r.icon className="h-4 w-4" />
            </div>
            <p className="w-16 shrink-0 text-[0.84rem] font-semibold text-[#374151]">{r.label}</p>
            <div className="h-8 flex-1">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={r.data.map((v, i) => ({ i, v }))} margin={{ top: 2, right: 2, bottom: 0, left: 2 }}>
                  <Line type="monotone" dataKey="v" stroke={r.color} strokeWidth={2} dot={false} isAnimationActive />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <span className="w-10 shrink-0 text-right text-[0.86rem] font-bold text-[#111827]">{r.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Model Usage ──────────────────────────────────────────────────────────────
const MODEL_COLORS = ["#38B88A", "#3B82F6", "#8B5CF6", "#F59E0B", "#EF4444"];
const MODEL_ICONS = ["G", "C", "Gm", "L", "M"]; // short labels

function ModelUsagePanel() {
  return (
    <Card className="p-5">
      <SectionHead title="Model Usage (Top 5)" action="View All" />
      <div className="space-y-3">
        {modelUsage.map((m, i) => (
          <div key={m.label} className="flex items-center gap-3">
            <div
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] text-[0.7rem] font-bold text-white"
              style={{ background: MODEL_COLORS[i] }}
            >
              {MODEL_ICONS[i]}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-[0.83rem] font-semibold text-[#374151]">{m.label}</p>
                <span className="shrink-0 text-[0.8rem] font-semibold text-[#111827]">{m.value} ({m.share}%)</span>
              </div>
              <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#EEF2F7]">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${m.share * 2}%` }}
                  transition={{ duration: 0.8, delay: i * 0.1 }}
                  className="h-full rounded-full"
                  style={{ background: MODEL_COLORS[i] }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Recent Runtime Events ────────────────────────────────────────────────────
const EVENT_ICONS: Record<string, React.ElementType> = {
  running:   Search,
  completed: Globe,
  healthy:   Database,
  info:      Mic,
  warning:   Monitor,
  searching: Globe,
};

function RecentRuntimeEvents() {
  return (
    <Card className="p-5">
      <SectionHead title="Recent Runtime Events" action="View All" />
      <div className="space-y-2.5">
        {runtimeEvents.map((ev, idx) => {
          const Icon = ev.icon;
          return (
            <div key={idx} className="flex items-start gap-3">
              <div className={cn("mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]", toneStyles[ev.tone] ?? toneStyles.info)}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[0.82rem] text-[#374151]">{ev.detail}</p>
              </div>
              <span className="shrink-0 text-[0.73rem] text-[#9CA3AF] whitespace-nowrap">{ev.time}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function RuntimeCenter() {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />

      <div className={cn("flex min-h-screen flex-col transition-all duration-300", collapsed ? "pl-[68px]" : "pl-[220px]")}>
        <Header collapsed={collapsed} />

        <main className="flex-1 px-5 py-5 lg:px-6">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.02)}
            className="mx-auto max-w-[1500px] space-y-5"
          >
            {/* Page title row */}
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-[1.4rem] font-bold tracking-[-0.03em] text-[#111827]">Runtime Control Center</h1>
                  <Badge tone="running">Live</Badge>
                </div>
                <p className="mt-1 text-[0.86rem] text-[#6B7280]">Monitor, orchestrate, and optimize your AI workforce in real-time.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                <button className="flex items-center gap-2 rounded-[12px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.84rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
                  All Environments <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                </button>
                <button className="flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
                  <Filter className="h-4 w-4" />
                </button>
                <button className="flex items-center gap-2 rounded-[12px] bg-[#38B88A] px-4 py-2 text-[0.84rem] font-semibold text-white shadow-[0_4px_12px_rgba(56,184,138,0.28)] transition hover:bg-[#2F9F77]">
                  <Plus className="h-4 w-4" /> Start New Run
                </button>
              </div>
            </motion.div>

            {/* KPI Row */}
            <motion.div variants={variants.fadeUp}>
              <KpiCards />
            </motion.div>

            {/* Live Executions + Runtime Flow */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-[1fr_420px]">
              <LiveExecutions />
              <RuntimeFlow />
            </motion.div>

            {/* Resource Utilization + Model Usage + Recent Events */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-3">
              <ResourceUtilization />
              <ModelUsagePanel />
              <RecentRuntimeEvents />
            </motion.div>
          </motion.div>
        </main>
      </div>
    </div>
  );
}
