"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
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
  Download,
  FileText,
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
  ShieldCheck,
  Target,
  Zap,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  metrics,
  sessions,
  topDomains,
  recentActivity,
  activityOverview,
  pagesVisitedSeries,
  extractedSeries,
  type BrowserTone,
  type BrowserSession,
} from "./data";

// ─── Status badge styling ─────────────────────────────────────────────────────
const toneStyles: Record<BrowserTone, string> = {
  browsing: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  extracting: "bg-[#EFF6FF] text-[#2563EB] ring-[#DBEAFE]",
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  idle: "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]",
  reading: "bg-[#F8FAFC] text-[#374151] ring-[#E5E7EB]",
  clicking: "bg-[#F8FAFC] text-[#374151] ring-[#E5E7EB]",
  typing: "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  waiting: "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  reviewing: "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  info: "bg-[#F8FAFC] text-[#374151] ring-[#E5E7EB]",
};

const toneDot: Record<BrowserTone, string> = {
  browsing: "bg-[#38B88A]",
  extracting: "bg-[#3B82F6]",
  completed: "bg-[#38B88A]",
  idle: "bg-[#9CA3AF]",
  reading: "bg-[#6B7280]",
  clicking: "bg-[#6B7280]",
  typing: "bg-[#F59E0B]",
  waiting: "bg-[#F59E0B]",
  reviewing: "bg-[#EF4444]",
  info: "bg-[#6B7280]",
};

const statusText: Record<BrowserTone, string> = {
  browsing: "Browsing",
  extracting: "Extracting",
  completed: "Completed",
  idle: "Idle",
  reading: "Reading",
  clicking: "Clicking",
  typing: "Typing",
  waiting: "Waiting",
  reviewing: "Reviewing",
  info: "Info",
};

function StatusBadge({ tone }: { tone: BrowserTone }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.72rem] font-semibold ring-1", toneStyles[tone] || toneStyles.info)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone] || "bg-[#6B7280]")} />
      {statusText[tone] || "Info"}
    </span>
  );
}

// ─── NAV ─────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home      },
  { href: "/runtime",       label: "Runtime",      icon: Zap       },
  { href: "/agents",        label: "Agents",       icon: Bot       },
  { href: "/missions",      label: "Missions",     icon: Target    },
  { href: "/voice",         label: "Voice",        icon: Mic       },
  { href: "/memory",        label: "Memory",       icon: Brain     },
  { href: "/workspace",     label: "Research",     icon: Search    },
  { href: "/operator",      label: "Computer Use", icon: Monitor   },
  { href: "/browser",       label: "Browser",      icon: Globe     },
  { href: "/replay",        label: "Replay",       icon: Archive   },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2 },
  { href: "/governance",    label: "Governance",   icon: ShieldCheck },
  { href: "/system-status", label: "Monitoring",   icon: Activity  },
  { href: "/integrations",  label: "Integrations", icon: Puzzle    },
  { href: "/settings",      label: "Settings",     icon: Settings  },
];

// ─── SIDEBAR ─────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#E8EDF3] bg-white transition-all duration-300",
      collapsed ? "w-[60px]" : "w-[152px]"
    )}>
      <div className={cn("flex items-center gap-2 px-4 py-[18px]", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-4 w-4 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round"/>
            <path d="M24 13 31 17v14l-7 4-7-4V17Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round"/>
          </svg>
        </div>
        {!collapsed && (
          <div className="min-w-0">
            <p className="text-[0.82rem] font-bold leading-tight text-[#111827]">CortexPrime</p>
            <p className="text-[0.62rem] font-medium text-[#9CA3AF]">AI Operating System</p>
          </div>
        )}
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-[2px]">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = label === "Browser";
          return (
            <Link key={label} href={href} className={cn(
              "flex items-center gap-2.5 rounded-[12px] px-2.5 py-2 text-[0.82rem] font-semibold transition-all",
              active ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F5F7FA] hover:text-[#111827]",
              collapsed && "justify-center px-0"
            )}>
              <Icon className="h-[16px] w-[16px] shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>
      <div className="px-2 pb-4 space-y-2">
        {!collapsed && (
          <div className="rounded-[12px] relative border border-[#E8EDF3] bg-[#F8FAF9] px-2.5 py-2">
            <div className="absolute right-2 top-2 text-[0.65rem] font-bold text-[#38B88A] bg-[#ECFBF4] h-4 w-4 rounded-full flex items-center justify-center">8</div>
            <p className="text-[0.66rem] font-bold uppercase tracking-wider text-[#6B7280]">System Status</p>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
              <span className="text-[0.72rem] font-bold text-[#38B88A]">Healthy</span>
            </div>
            <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5">All systems operational</p>
          </div>
        )}
        <div className="flex gap-1.5">
          <button onClick={onCollapse} className={cn(
            "flex-1 flex items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
            collapsed && "justify-center"
          )}>
            <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
            {!collapsed && <span>Collapse</span>}
          </button>
          {!collapsed && (
            <button className="flex h-8 w-8 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#6B7280] hover:bg-[#F5F7FA]">
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>
    </aside>
  );
}

// ─── TOPBAR ───────────────────────────────────────────────────────────────────
function TopBar({ sidebarWidth }: { sidebarWidth: number }) {
  const avatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, []);
  return (
    <header className="fixed top-0 right-0 z-30 flex items-center gap-3 border-b border-[#E8EDF3] bg-white/96 px-5 py-2.5 backdrop-blur transition-all duration-300"
      style={{ left: sidebarWidth }}>
      <label className="relative flex h-9 w-[200px] items-center">
        <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-12 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]" />
        <span className="absolute right-2.5 rounded-[6px] border border-[#E5E7EB] bg-white px-1 py-0.5 text-[0.6rem] font-semibold text-[#9CA3AF]">⌘ K</span>
      </label>
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 xl:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]"><Target className="h-3 w-3" /></div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-1.5">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.58rem] font-bold text-[#2F9F77]">
              <span className="h-1 w-1 rounded-full bg-[#38B88A]" />Running
            </span>
          </div>
        </div>
        <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
      </div>
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 lg:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]"><Mic className="h-3 w-3" /></div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.76rem] font-semibold text-[#111827]">Listening...</p>
        </div>
        <div className="ml-1 flex items-end gap-[2px]">
          {[3, 5, 4, 6, 3, 5, 4].map((h, i) => (
            <span key={i} className="w-[2px] rounded-full bg-[#38B88A]" style={{ height: `${h * 2}px` }} />
          ))}
        </div>
      </div>
      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#374151] hover:bg-[#F5F7FA]">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-[#EF4444] text-[0.56rem] font-bold text-white ring-2 ring-white">3</span>
        </button>
        <div className="flex cursor-pointer items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white p-1 pr-2.5 hover:bg-[#F5F7FA]">
          <Image src={avatar} alt="Alex Morgan" width={28} height={28} className="rounded-[8px]" />
          <div className="hidden leading-tight sm:block">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.62rem] text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="hidden h-3 w-3 text-[#9CA3AF] sm:block" />
        </div>
      </div>
    </header>
  );
}

// ─── SPARKLINE ────────────────────────────────────────────────────────────────
function Sparkline({ data, color = "#38B88A" }: { data: number[]; color?: string }) {
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const W = 150, H = 32;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 8) - 4}`);
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const uid = useMemo(() => Math.random().toString(36).slice(2, 7), []);
  return (
    <div className="h-8 w-full mt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.12} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${uid})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ─── BROWSER LOGOS ────────────────────────────────────────────────────────────
function BrowserIcon({ type }: { type: BrowserSession["browser"] }) {
  if (type === "chrome") {
    return (
      <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" fill="#34A853" />
        <path d="M12 2a10 10 0 0 1 8.66 5L12 12V2z" fill="#EA4335" />
        <path d="M20.66 7a10 10 0 0 1-5 8.66L12 12l8.66-5z" fill="#FBBC05" />
        <circle cx="12" cy="12" r="5" fill="#FFF" />
        <circle cx="12" cy="12" r="3.5" fill="#4285F4" />
      </svg>
    );
  }
  if (type === "edge") {
    return (
      <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 12C2 6.48 6.48 2 12 2c5.07 0 9.24 3.79 9.87 8.75H13c-3 0-5.5 2.5-5.5 5.5s2.5 5.5 5.5 5.5c4.96 0 8.75-4.17 8.75-9.22h-1.5" fill="#06B6D4" />
        <path d="M12 22c5.52 0 10-4.48 10-10h-6c0 2.21-1.79 4-4 4v6z" fill="#10B981" />
        <circle cx="12" cy="12" r="3" fill="#2563EB" />
      </svg>
    );
  }
  if (type === "firefox") {
    return (
      <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" fill="#3B82F6" />
        <path d="M22 12c0 5.52-4.48 10-10 10s-10-4.48-10-10C2 7 6 3 12 3c4 0 7 2 8.5 4.5L16 10c0-1-1-2-2-2a3 3 0 0 0-3 3c0 2 1.5 3 3.5 3s4-1.5 4-4.5L22 12z" fill="#F97316" />
        <path d="M15 11c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z" fill="#EF4444" opacity="0.8" />
      </svg>
    );
  }
  if (type === "safari") {
    return (
      <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" fill="#E0F2FE" stroke="#0284C7" strokeWidth="1.5" />
        <circle cx="12" cy="12" r="8" fill="#38BDF8" />
        <path d="M16.5 7.5L13 11l-2 2-3.5 3.5L11 13l2-2 3.5-3.5z" fill="#EF4444" />
        <path d="M7.5 16.5L11 13l2-2 3.5-3.5L13 11l-2 2-3.5 3.5z" fill="#F8FAFC" />
      </svg>
    );
  }
  if (type === "brave") {
    return (
      <svg className="h-[18px] w-[18px] shrink-0" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L2 9.5l3.5 11L12 22l6.5-1.5 3.5-11L12 2z" fill="#EA580C" />
        <path d="M12 5l-6 4 2 8 4 2 4-2 2-8-6-4z" fill="#F97316" />
        <path d="M12 9l-3 2 1.5 4 1.5 1 1.5-1 1.5-4-3-2z" fill="#111827" />
      </svg>
    );
  }
  return <Globe className="h-[18px] w-[18px] text-[#38B88A]" />;
}

// ─── ACTIVE BROWSER SESSIONS TABLE ────────────────────────────────────────────
function SessionsTable() {
  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-0 min-w-0">
      <div className="flex flex-col gap-3 border-b border-[#E8EDF3] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <h2 className="text-[0.98rem] font-bold text-[#111827]">Active Browser Sessions</h2>
          <span className="rounded-full bg-[#F3F4F6] px-2 py-0.5 text-[0.72rem] font-semibold text-[#6B7280]">12</span>
        </div>
        <div className="relative h-9 w-full sm:w-[220px]">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
          <input placeholder="Search sessions..." className="h-full w-full rounded-[10px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-3 text-[0.78rem] text-[#111827] outline-none placeholder:text-[#9CA3AF]" />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[900px] text-left border-collapse">
          <thead>
            <tr className="border-b border-[#E8EDF3] text-[0.74rem] font-semibold text-[#9CA3AF]">
              <th className="px-5 py-3">Session</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Mission</th>
              <th className="px-4 py-3">Current URL</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Pages</th>
              <th className="px-4 py-3">Duration</th>
              <th className="px-4 py-3">Progress</th>
              <th className="px-5 py-3 w-10" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id} className="border-b border-[#E8EDF3] last:border-0 hover:bg-[#F9FAFB] transition-colors">
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <BrowserIcon type={session.browser} />
                    <div>
                      <p className="text-[0.82rem] font-bold text-[#111827]">Session {session.id}</p>
                      <p className="text-[0.66rem] text-[#9CA3AF] font-medium">{session.os}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2 text-[0.8rem] font-semibold text-[#374151]">
                    <span className="flex h-5 w-5 items-center justify-center rounded-[6px] bg-[#F5F3FF] text-[#7C3AED]">
                      <Bot className="h-3 w-3" />
                    </span>
                    {session.agent}
                  </div>
                </td>
                <td className="px-4 py-3 text-[0.8rem] text-[#6B7280] font-medium">{session.mission}</td>
                <td className="px-4 py-3 text-[0.76rem] text-[#6B7280] font-medium font-mono max-w-[200px] truncate">{session.url}</td>
                <td className="px-4 py-3"><StatusBadge tone={session.status} /></td>
                <td className="px-4 py-3 text-[0.8rem] text-[#374151] font-bold">{session.pages}</td>
                <td className="px-4 py-3 text-[0.8rem] text-[#6B7280] font-medium">{session.duration}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <span className="h-1.5 w-16 overflow-hidden rounded-full bg-[#E8EDF3] inline-block">
                      <span className="block h-full rounded-full bg-[#38B88A]" style={{ width: `${session.progress}%` }} />
                    </span>
                    <span className="text-[0.78rem] font-bold text-[#374151]">{session.progress}%</span>
                  </div>
                </td>
                <td className="px-5 py-3 text-center">
                  <button className="flex h-7 w-7 items-center justify-center rounded-[8px] text-[#9CA3AF] hover:bg-[#F5F7FA] hover:text-[#111827]">
                    <MoreVertical className="h-3.5 w-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 border-t border-[#E8EDF3] p-4 sm:flex-row sm:items-center sm:justify-between text-[0.78rem] text-[#6B7280] font-semibold">
        <p>Showing 1 to 6 of 12 sessions</p>
        <div className="flex items-center gap-1.5">
          <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#E8EDF3] hover:bg-[#F5F7FA]"><ChevronLeft className="h-3.5 w-3.5" /></button>
          <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77]">1</button>
          <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#E8EDF3] hover:bg-[#F5F7FA]">2</button>
          <button className="flex h-8 w-8 items-center justify-center rounded-[8px] border border-[#E8EDF3] hover:bg-[#F5F7FA]"><ChevronRight className="h-3.5 w-3.5" /></button>
          <button className="ml-1 rounded-[8px] border border-[#E8EDF3] px-2.5 py-1 hover:bg-[#F5F7FA]">10 / page <ChevronDown className="h-3 w-3 inline ml-0.5" /></button>
        </div>
      </div>
    </div>
  );
}

// ─── TOP DOMAINS CARD ─────────────────────────────────────────────────────────
function TopDomainsCard() {
  const maxVisits = useMemo(() => Math.max(...topDomains.map((item) => item.visits)), []);

  const logoBgs: Record<string, string> = {
    "bloomberg.com": "bg-[#000000]",
    "crunchbase.com": "bg-[#0284C7]",
    "mckinsey.com": "bg-[#0F172A]",
    "sec.gov": "bg-[#1E3A8A]",
    "statista.com": "bg-[#1E40AF]",
  };

  const logoTexts: Record<string, string> = {
    "bloomberg.com": "B",
    "crunchbase.com": "c",
    "mckinsey.com": "M",
    "sec.gov": "S",
    "statista.com": "s",
  };

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[0.92rem] font-bold text-[#111827]">Top Domains</h2>
        <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.72rem] font-bold text-[#6B7280] flex items-center gap-1 hover:bg-[#F5F7FA]">
          This Week <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
        </button>
      </div>

      <div className="space-y-3.5">
        {topDomains.map((domain) => (
          <div key={domain.domain}>
            <div className="mb-1.5 flex items-center gap-2.5">
              <span className={cn(
                "flex h-6 w-6 items-center justify-center rounded-[6px] text-[0.7rem] font-bold text-white uppercase",
                logoBgs[domain.domain] || "bg-[#6B7280]"
              )}>
                {logoTexts[domain.domain] || domain.logo}
              </span>
              <span className="min-w-0 flex-1 text-[0.8rem] font-bold text-[#374151]">{domain.domain}</span>
              <span className="text-[0.74rem] font-semibold text-[#9CA3AF]">{domain.visits} visits</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[#E8EDF3]">
              <div className="h-full rounded-full bg-[#38B88A]" style={{ width: `${(domain.visits / maxVisits) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>

      <button className="mt-4 flex h-9 w-full items-center justify-center rounded-[10px] border border-[#E8EDF3] text-[0.78rem] font-bold text-[#374151] hover:bg-[#F5F7FA]">
        View All Domains
      </button>
    </div>
  );
}

// ─── RECENT ACTIVITY CARD ─────────────────────────────────────────────────────
function RecentActivityCard() {
  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-[0.92rem] font-bold text-[#111827]">Recent Activity</h2>
        <button className="text-[0.72rem] font-bold text-[#38B88A] hover:underline">View All</button>
      </div>

      <div className="space-y-3">
        {recentActivity.map((item, index) => {
          const Icon = item.icon;
          return (
            <div key={index} className="flex items-start gap-2.5">
              <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]">
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[0.78rem] font-bold text-[#374151] leading-snug">{item.label}</p>
                <p className="text-[0.68rem] text-[#9CA3AF] font-medium mt-0.5">{item.time}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── DONUT CHART CARD (BROWSER ACTIVITY OVERVIEW) ────────────────────────────
function ActivityOverviewCard() {
  const total = useMemo(() => activityOverview.reduce((a, c) => a + c.value, 0), []);
  const R = 35;
  const strokeW = 8;
  const circ = 2 * Math.PI * R;
  let acc = 0;

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-4">
      <h2 className="text-[0.92rem] font-bold text-[#111827] mb-4">Browser Activity Overview</h2>
      
      <div className="flex flex-col sm:flex-row items-center gap-6 justify-center">
        {/* SVG Donut */}
        <div className="relative h-[110px] w-[110px] flex-shrink-0">
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            {activityOverview.map((s) => {
              const len = (s.value / total) * circ;
              const rotate = (acc / total) * 360;
              acc += s.value;
              return (
                <circle key={s.label} cx="50" cy="50" r={R} fill="none"
                  stroke={s.color} strokeWidth={strokeW}
                  strokeDasharray={`${len} ${circ - len}`}
                  strokeLinecap="round"
                  transform={`rotate(${rotate} 50 50)`}
                />
              );
            })}
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-[1.2rem] font-bold text-[#111827] leading-none">{total}</span>
            <span className="text-[0.62rem] font-semibold text-[#9CA3AF] mt-0.5">Active</span>
          </div>
        </div>

        {/* Legend */}
        <div className="flex-1 space-y-2 w-full">
          {activityOverview.map((s) => (
            <div key={s.label} className="flex items-center justify-between text-[0.76rem]">
              <span className="flex items-center gap-2 font-semibold text-[#6B7280]">
                <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: s.color }} />
                {s.label}
              </span>
              <span className="font-bold text-[#374151]">{s.value} ({((s.value / total) * 100).toFixed(1)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── PAGES VISITED OVER TIME (LINE CHART) ─────────────────────────────────────
function PagesVisitedCard() {
  const W = 500, H = 100;
  const data = pagesVisitedSeries;
  const pts = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - (d.value / 2500) * (H - 16) - 8;
    return `${x},${y}`;
  });
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const yTicks = [2500, 2000, 1500, 1000, 500, 0];
  const yLabels = ["2.5K", "2K", "1.5K", "1K", "500", "0"];

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-[0.92rem] font-bold text-[#111827]">Pages Visited Over Time</h2>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-[1.1rem] font-bold text-[#38B88A]">1,842</span>
            <span className="text-[0.66rem] font-bold text-[#2F9F77] ml-1">▲ 18.3%</span>
          </div>
          <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.72rem] font-bold text-[#6B7280] flex items-center gap-1 hover:bg-[#F5F7FA]">
            This Week <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
          </button>
        </div>
      </div>

      <div>
        <div className="flex gap-2">
          {/* Y-axis */}
          <div className="flex flex-col justify-between text-[0.62rem] text-[#9CA3AF] h-[100px] w-8 pr-1 py-1 text-right font-medium">
            {yLabels.map((l) => <span key={l}>{l}</span>)}
          </div>
          {/* Chart SVG */}
          <div className="relative flex-1 h-[100px]">
            <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
              <defs>
                <linearGradient id="pv-grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#38B88A" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
                </linearGradient>
              </defs>
              {/* Horizontal Grid Lines */}
              {yTicks.map((val) => {
                const y = H - (val / 2500) * (H - 16) - 8;
                return (
                  <line key={val} x1={0} y1={y} x2={W} y2={y} stroke="#E8EDF3" strokeWidth="1" strokeDasharray="4 4" />
                );
              })}
              <path d={fillPath} fill="url(#pv-grad)" />
              <path d={linePath} fill="none" stroke="#38B88A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              {/* Data points */}
              {data.map((d, i) => {
                const x = (i / (data.length - 1)) * W;
                const y = H - (d.value / 2500) * (H - 16) - 8;
                return (
                  <circle key={i} cx={x} cy={y} r="2.5" fill="#38B88A" stroke="white" strokeWidth="1.5" />
                );
              })}
            </svg>
          </div>
        </div>
        {/* X-axis */}
        <div className="mt-1 flex justify-between pl-10 pr-2 text-[0.62rem] text-[#9CA3AF] font-medium">
          {["May 6", "May 11", "May 16", "May 21", "May 26", "May 31"].map((l) => <span key={l}>{l}</span>)}
        </div>
      </div>
    </div>
  );
}

// ─── DATA EXTRACTED OVER TIME (BAR CHART) ─────────────────────────────────────
function DataExtractedCard() {
  const W = 500, H = 100;
  const data = extractedSeries;
  const yTicks = [5, 4, 3, 2, 1, 0];
  const yLabels = ["5 GB", "4 GB", "3 GB", "2 GB", "1 GB", "0"];
  const barWidth = (W / data.length) * 0.55;

  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-[0.92rem] font-bold text-[#111827]">Data Extracted Over Time</h2>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right">
            <span className="text-[1.1rem] font-bold text-[#38B88A]">3.24 GB</span>
            <span className="text-[0.66rem] font-bold text-[#2F9F77] ml-1">▲ 24.7%</span>
          </div>
          <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.72rem] font-bold text-[#6B7280] flex items-center gap-1 hover:bg-[#F5F7FA]">
            This Week <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
          </button>
        </div>
      </div>

      <div>
        <div className="flex gap-2">
          {/* Y-axis */}
          <div className="flex flex-col justify-between text-[0.62rem] text-[#9CA3AF] h-[100px] w-8 pr-1 py-1 text-right font-medium">
            {yLabels.map((l) => <span key={l}>{l}</span>)}
          </div>
          {/* Chart SVG */}
          <div className="relative flex-1 h-[100px]">
            <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
              {/* Horizontal Grid Lines */}
              {yTicks.map((val) => {
                const y = H - (val / 5) * (H - 16) - 8;
                return (
                  <line key={val} x1={0} y1={y} x2={W} y2={y} stroke="#E8EDF3" strokeWidth="1" strokeDasharray="4 4" />
                );
              })}
              {/* Vertical Bars */}
              {data.map((d, i) => {
                const x = (i / data.length) * W + (W / data.length) * 0.22;
                const y = H - (d.value / 5) * (H - 16) - 8;
                const barHeight = (H - 8) - y;
                return (
                  <rect key={i} x={x} y={y} width={barWidth} height={Math.max(barHeight, 2)} fill="#38B88A" rx={1} />
                );
              })}
            </svg>
          </div>
        </div>
        {/* X-axis */}
        <div className="mt-1 flex justify-between pl-10 pr-2 text-[0.62rem] text-[#9CA3AF] font-medium">
          {["May 6", "May 11", "May 16", "May 21", "May 26", "May 31"].map((l) => <span key={l}>{l}</span>)}
        </div>
      </div>
    </div>
  );
}

// ─── MAIN BROWSER CENTER COMPONENT ───────────────────────────────────────────
export default function BrowserCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <TopBar sidebarWidth={sidebarWidth} />

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="mx-auto max-w-[1400px] space-y-5">
            
            {/* ── Page Header ───────────────────────────────────────────── */}
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Browser Center</h1>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">AI agents browsing the web, extracting data, and gathering insights.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.8rem] font-semibold text-[#374151] hover:bg-[#F5F7FA]">
                  <Filter className="h-3.5 w-3.5 text-[#6B7280]" /> Filter
                </button>
                <button className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white shadow-[0_3px_10px_rgba(56,184,138,0.25)] hover:bg-[#2F9F77]">
                  <Plus className="h-3.5 w-3.5" /> New Browser Session <ChevronDown className="h-3 w-3 ml-0.5" />
                </button>
              </div>
            </motion.div>

            {/* ── 5 KPI Cards ───────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {metrics.map((m) => {
                const Icon = m.icon;
                const isExtracting = m.tone === "extracting";
                const chartColor = isExtracting ? "#3B82F6" : "#38B88A";
                const iconBg = isExtracting ? "bg-[#EFF6FF] text-[#2563EB] border-[#DBEAFE]" : "bg-[#ECFBF4] text-[#38B88A] border-[#D6F0E5]";
                return (
                  <div key={m.label} className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.71rem] font-semibold text-[#9CA3AF]">{m.label}</p>
                      <div className={cn("flex h-7 w-7 items-center justify-center rounded-[9px] border", iconBg)}>
                        <Icon className="h-3.5 w-3.5" />
                      </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-[1.5rem] font-bold tracking-tight text-[#111827]">{m.value}</span>
                      <span className="text-[0.7rem] font-bold text-[#38B88A] flex items-center gap-0.5">
                        <ChevronRight className="h-3 w-3 -rotate-90 shrink-0 stroke-[3]" />
                        {m.trend.replace("+", "")}
                      </span>
                    </div>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium">vs last 7 days</p>
                    <Sparkline data={m.data} color={chartColor} />
                  </div>
                );
              })}
            </motion.div>

            {/* ── Middle Table & Cards ──────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-5 lg:grid-cols-12">
              <div className="lg:col-span-8">
                <SessionsTable />
              </div>
              <div className="lg:col-span-4 space-y-5">
                <TopDomainsCard />
                <RecentActivityCard />
              </div>
            </motion.div>

            {/* ── Bottom Analytics Charts ───────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-5 md:grid-cols-3">
              <ActivityOverviewCard />
              <PagesVisitedCard />
              <DataExtractedCard />
            </motion.div>

          </motion.div>
        </main>

        <footer className="border-t border-[#E8EDF3] px-5 py-4">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 text-[0.76rem] font-semibold text-[#9CA3AF]">
            <p className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-[#38B88A]" /> Enterprise Secure</p>
            <p>&copy; 2026 CortexPrime. All rights reserved.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
