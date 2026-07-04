"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, Archive, BarChart2, Bell, Bot, Brain,
  Camera, CheckCircle2, ChevronDown, ChevronLeft,
  ChevronRight, Clock, Database, Filter, Globe,
  Home, Mic, Monitor, MoreVertical, Pause, Plus,
  Puzzle, RefreshCw, Search, Settings, Shield,
  ShieldCheck, Target, TrendingUp, Zap,
  SquareArrowOutUpRight, Image as ImageIcon, X,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  metrics,
  sessions,
  actionCards,
  usageOverview,
  recentActivity,
  taskCategories,
  successRateSeries,
  currentTask,
} from "./data";

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
  { href: "/operator",      label: "Browser",      icon: Globe     },
  { href: "/replay",        label: "Replay",       icon: Archive   },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2 },
  { href: "/governance",    label: "Governance",   icon: Shield    },
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
          const active = label === "Computer Use";
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
          <div className="rounded-[12px] border border-[#E8EDF3] bg-[#F8FAF9] px-2.5 py-2">
            <p className="text-[0.66rem] font-bold uppercase tracking-wider text-[#6B7280]">System Status</p>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
              <span className="text-[0.72rem] font-bold text-[#38B88A]">Healthy</span>
            </div>
            <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5">All systems operational</p>
          </div>
        )}
        <button onClick={onCollapse} className={cn(
          "flex w-full items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
          collapsed && "justify-center"
        )}>
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </button>
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
  const W = 120, H = 36;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 8) - 4}`);
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const uid = Math.random().toString(36).slice(2, 7);
  return (
    <div className="mt-2 h-8 w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.15} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${uid})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ─── MOCK SCREEN PREVIEW ──────────────────────────────────────────────────────
function ScreenPreview() {
  return (
    <div className="relative rounded-[10px] overflow-hidden border border-[#E8EDF3] bg-white shadow-sm">
      {/* Fake browser chrome */}
      <div className="flex items-center gap-1.5 bg-[#F1F5F9] px-3 py-1.5 border-b border-[#E8EDF3]">
        <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
        <span className="h-2 w-2 rounded-full bg-[#F59E0B]" />
        <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
        <div className="ml-2 flex-1 rounded-[4px] bg-white px-2 py-0.5 text-[0.6rem] text-[#9CA3AF]">Sales Report – Q2 2024</div>
      </div>
      {/* Fake spreadsheet content */}
      <div className="p-3 bg-white min-h-[160px]">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[0.72rem] font-bold text-[#111827]">Sales Report – Q2 2024</p>
          <p className="text-[0.62rem] text-[#9CA3AF]">Revenue by Region</p>
        </div>
        {/* Table rows */}
        <table className="w-full text-[0.6rem] border-collapse mb-3">
          <thead>
            <tr className="bg-[#F8FAFC]">
              {["Region", "Revenue", "Growth %"].map((h) => (
                <th key={h} className="border border-[#E8EDF3] px-1.5 py-1 text-left font-bold text-[#6B7280]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              ["North America", "$4,212,000", "12.4%"],
              ["Europe", "$3,890,000", "9.8%"],
              ["Asia Pacific", "$2,860,000", "18.7%"],
              ["Latin America", "$1,205,000", "6.2%"],
              ["Middle East & Africa", "$800,000", "4.8%"],
              ["Enterprise Store", "$742,000", "8.3%"],
            ].map((row, i) => (
              <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-[#FAFBFC]"}>
                {row.map((cell, j) => (
                  <td key={j} className="border border-[#E8EDF3] px-1.5 py-0.5 text-[#374151]">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {/* Mini bar chart */}
        <div className="flex items-end gap-0.5 h-8 mt-2">
          {[65, 58, 43, 18, 12, 11].map((v, i) => (
            <div key={i} className="flex-1 rounded-sm" style={{ height: `${v}%`, backgroundColor: ["#38B88A","#3B82F6","#8B5CF6","#F59E0B","#EF4444","#9CA3AF"][i] }} />
          ))}
        </div>
        <p className="mt-1 text-[0.55rem] text-[#9CA3AF] text-center">Revenue Trend</p>
      </div>
    </div>
  );
}

// ─── TASK CATEGORY DONUT ─────────────────────────────────────────────────────
function TaskCategoryDonut() {
  const total = taskCategories.reduce((a, c) => a + c.value, 0);
  const R = 40, circ = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="flex items-center gap-5">
      <div className="relative flex-shrink-0">
        <svg viewBox="0 0 100 100" className="h-[120px] w-[120px] -rotate-90">
          {taskCategories.map((s) => {
            const len = (s.value / total) * circ;
            const rotate = (acc / total) * 360;
            acc += s.value;
            return (
              <circle key={s.label} cx="50" cy="50" r={R} fill="none"
                stroke={s.color} strokeWidth="11"
                strokeDasharray={`${len} ${circ - len}`}
                transform={`rotate(${rotate} 50 50)`}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[1.2rem] font-bold text-[#111827]">{total}</span>
          <span className="text-[0.6rem] font-semibold text-[#9CA3AF]">Total</span>
        </div>
      </div>
      <div className="flex-1 space-y-2">
        {taskCategories.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-[0.72rem]">
            <span className="flex items-center gap-1.5 font-medium text-[#6B7280]">
              <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: s.color }} />
              {s.label}
            </span>
            <span className="font-bold text-[#374151]">{s.value} ({((s.value / total) * 100).toFixed(1)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── SUCCESS RATE CHART ───────────────────────────────────────────────────────
function SuccessRateChart() {
  const W = 400, H = 100;
  const min = Math.min(...successRateSeries.map((d) => d.value));
  const max = Math.max(...successRateSeries.map((d) => d.value));
  const range = max - min || 1;
  const pts = successRateSeries.map((d, i) => {
    const x = (i / (successRateSeries.length - 1)) * W;
    const y = H - ((d.value - min) / range) * (H - 16) - 8;
    return `${x},${y}`;
  });
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  // X-axis labels: every 3rd
  const xLabels = successRateSeries.filter((_, i) => i % 3 === 0 || i === successRateSeries.length - 1);
  return (
    <div>
      <div className="relative h-[100px] w-full">
        <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id="sr-grad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#38B88A" stopOpacity={0.15} />
              <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
            </linearGradient>
          </defs>
          {/* Grid lines */}
          {[0, 33, 66, 100].map((p) => {
            const y = H - (p / 100) * (H - 16) - 8;
            return <line key={p} x1={0} y1={y} x2={W} y2={y} stroke="#E8EDF3" strokeWidth="1" strokeDasharray="4 4" />;
          })}
          <path d={fillPath} fill="url(#sr-grad)" />
          <path d={linePath} fill="none" stroke="#38B88A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          {/* Dots */}
          {successRateSeries.map((d, i) => {
            const x = (i / (successRateSeries.length - 1)) * W;
            const y = H - ((d.value - min) / range) * (H - 16) - 8;
            return <circle key={i} cx={x} cy={y} r="2.5" fill="#38B88A" stroke="white" strokeWidth="1.5" />;
          })}
        </svg>
      </div>
      {/* X axis labels */}
      <div className="mt-1 flex justify-between text-[0.6rem] text-[#9CA3AF]">
        {["May 6", "May 11", "May 16", "May 21", "May 26", "May 31"].map((l) => <span key={l}>{l}</span>)}
      </div>
    </div>
  );
}

// ─── COMPUTER USE CENTER ──────────────────────────────────────────────────────
export default function ComputerUseCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;

  // Metrics matching screenshot: Active Sessions, Tasks Completed, Success Rate, Avg Task Time, Screens Captured
  const displayMetrics = [
    metrics[0],  // Active Sessions: 8
    metrics[2],  // Tasks Completed: 156
    metrics[5],  // Success Rate: 94.6%
    metrics[4],  // Avg. Task Time: 02:41
    { label: "Screens Captured", value: "1,248", trend: "+22.1%", status: "Running", tone: "running" as const, icon: Camera, data: [680, 720, 760, 810, 880, 940, 1020, 1120, 1248] },
  ];

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
                <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Computer Use Center</h1>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">AI agents operating computers, automating tasks, and interacting with applications.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.8rem] font-semibold text-[#374151] hover:bg-[#F5F7FA]">
                  <Filter className="h-3.5 w-3.5 text-[#6B7280]" /> Filter
                </button>
                <button className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white shadow-[0_3px_10px_rgba(56,184,138,0.25)] hover:bg-[#2F9F77]">
                  <Plus className="h-3.5 w-3.5" /> New Task <ChevronDown className="h-3 w-3 ml-0.5" />
                </button>
              </div>
            </motion.div>

            {/* ── 5 KPI Cards ───────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {displayMetrics.map((m) => {
                const Icon = m.icon;
                return (
                  <div key={m.label} className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.71rem] font-semibold text-[#9CA3AF]">{m.label}</p>
                      <div className="flex h-7 w-7 items-center justify-center rounded-[9px] border border-[#D6F0E5] bg-[#F0FBF6] text-[#38B88A]">
                        <Icon className="h-3.5 w-3.5" />
                      </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-[1.5rem] font-bold tracking-tight text-[#111827]">{m.value}</span>
                      <span className="text-[0.7rem] font-bold text-[#38B88A]">{m.trend}</span>
                    </div>
                    <p className="text-[0.64rem] text-[#9CA3AF]">vs last 7 days</p>
                    <Sparkline data={m.data} />
                  </div>
                );
              })}
            </motion.div>

            {/* ── Main 3-col Grid ───────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-5 lg:grid-cols-12">

              {/* Active Sessions */}
              <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] lg:col-span-5">
                <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-3">
                  <div className="flex items-center gap-2">
                    <h2 className="text-[0.88rem] font-bold text-[#111827]">Active Sessions</h2>
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#ECFBF4] text-[0.62rem] font-bold text-[#2F9F77]">8</span>
                  </div>
                  <ChevronDown className="h-4 w-4 text-[#9CA3AF]" />
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[440px] border-collapse text-left">
                    <thead>
                      <tr className="border-b border-[#E8EDF3] text-[0.64rem] font-bold uppercase tracking-wider text-[#9CA3AF]">
                        <th className="px-4 py-2.5">Session</th>
                        <th className="px-2 py-2.5">Agent</th>
                        <th className="px-2 py-2.5">Task</th>
                        <th className="px-2 py-2.5">Status</th>
                        <th className="px-2 py-2.5">Started</th>
                        <th className="px-2 py-2.5">Progress</th>
                        <th className="w-6 px-2 py-2.5" />
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.map((s, i) => {
                        const barColor = s.status === "completed" ? "#3B82F6" : "#38B88A";
                        return (
                          <tr key={i} className="border-b border-[#F1F5F9] last:border-0 hover:bg-[#F8FAF9]/60 cursor-pointer transition-colors">
                            <td className="px-4 py-2.5">
                              <div className="flex items-center gap-2 min-w-0">
                                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[7px] bg-[#F5F7FA]">
                                  <Monitor className="h-3.5 w-3.5 text-[#6B7280]" />
                                </div>
                                <div className="min-w-0">
                                  <p className="text-[0.72rem] font-bold text-[#111827]">Session {s.id}</p>
                                  <p className="text-[0.62rem] text-[#9CA3AF]">{s.os}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-2 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <div className="h-4.5 w-4.5 rounded-full bg-[#ECFBF4] flex items-center justify-center">
                                  <span className="text-[0.5rem] font-bold text-[#38B88A]">{s.agent[0]}</span>
                                </div>
                                <span className="text-[0.68rem] font-semibold text-[#374151] whitespace-nowrap">{s.agent}</span>
                              </div>
                            </td>
                            <td className="px-2 py-2.5">
                              <p className="text-[0.68rem] text-[#4B5563] max-w-[100px] truncate">{s.task}</p>
                            </td>
                            <td className="px-2 py-2.5">
                              <span className={cn(
                                "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[0.6rem] font-semibold",
                                s.status === "running" ? "bg-[#ECFBF4] text-[#2F9F77]" : "bg-[#DBEAFE] text-[#1D4ED8]"
                              )}>
                                <span className={cn("h-1 w-1 rounded-full", s.status === "running" ? "bg-[#38B88A]" : "bg-[#3B82F6]")} />
                                {s.status === "running" ? "Running" : "Completed"}
                              </span>
                            </td>
                            <td className="px-2 py-2.5 text-[0.66rem] text-[#9CA3AF] whitespace-nowrap">{s.started}</td>
                            <td className="px-2 py-2.5">
                              <div className="flex items-center gap-1.5">
                                <div className="h-1.5 w-14 overflow-hidden rounded-full bg-[#E8EDF3]">
                                  <div className="h-full rounded-full" style={{ width: `${s.progress}%`, backgroundColor: barColor }} />
                                </div>
                                <span className="text-[0.62rem] font-bold text-[#374151]">{s.progress}%</span>
                              </div>
                            </td>
                            <td className="px-2 py-2.5 text-right">
                              <button className="flex h-6 w-6 items-center justify-center rounded-[6px] text-[#9CA3AF] hover:bg-[#F1F5F9] hover:text-[#374151]">
                                <MoreVertical className="h-3.5 w-3.5" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between border-t border-[#E8EDF3] px-4 py-3">
                  <p className="text-[0.72rem] text-[#6B7280]">Showing 1 to 6 of 8 sessions</p>
                  <button className="text-[0.72rem] font-bold text-[#38B88A] hover:underline">View All Sessions</button>
                </div>
              </div>

              {/* Live Screen */}
              <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] lg:col-span-4">
                <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-3">
                  <div className="flex items-center gap-2">
                    <h2 className="text-[0.88rem] font-bold text-[#111827]">Live Screen — Session #7821</h2>
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[0.62rem] font-bold text-[#2F9F77]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] animate-pulse" />Live
                  </span>
                </div>

                <div className="p-4">
                  <ScreenPreview />

                  {/* Current Task */}
                  <div className="mt-3 rounded-[10px] border border-[#E8EDF3] bg-[#F8FAF9] p-3">
                    <p className="text-[0.64rem] font-bold uppercase tracking-wider text-[#9CA3AF]">Current Task</p>
                    <p className="mt-1 text-[0.78rem] font-semibold text-[#111827]">Generate sales performance report for Q2 2024</p>
                    <div className="mt-2 flex items-center justify-between">
                      <div>
                        <p className="text-[0.62rem] text-[#9CA3AF]">Step 7 of 12</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[0.62rem] text-[#9CA3AF]">ETA</p>
                        <p className="text-[0.72rem] font-bold text-[#111827]">01:24 min</p>
                      </div>
                    </div>
                  </div>

                  {/* Action buttons */}
                  <div className="mt-3 flex items-center gap-2">
                    {[
                      { label: "Take Control", icon: SquareArrowOutUpRight },
                      { label: "Pause", icon: Pause },
                      { label: "Screenshot", icon: ImageIcon },
                      { label: "End Session", icon: X },
                      { label: "More", icon: MoreVertical },
                    ].map(({ label, icon: Icon }) => (
                      <button key={label} className="flex flex-col items-center gap-1 text-[0.6rem] font-semibold text-[#6B7280] hover:text-[#111827]">
                        <div className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#E8EDF3] bg-white hover:bg-[#F5F7FA]">
                          <Icon className="h-3.5 w-3.5" />
                        </div>
                        <span className="whitespace-nowrap">{label}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Right: Actions + Usage + Activity */}
              <div className="flex flex-col gap-4 lg:col-span-3">

                {/* Actions */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <h3 className="mb-3 text-[0.85rem] font-bold text-[#111827]">Actions</h3>
                  <div className="space-y-2">
                    {actionCards.map((a, i) => {
                      const Icon = a.icon;
                      return (
                        <button key={i} className="flex w-full items-center gap-3 rounded-[10px] border border-[#E8EDF3] bg-[#F8FAF9] p-2.5 text-left hover:bg-[#ECFBF4] hover:border-[#D6F0E5] transition-all">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-white border border-[#E8EDF3] text-[#38B88A]">
                            <Icon className="h-3.5 w-3.5" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-[0.74rem] font-bold text-[#111827]">{a.label}</p>
                            <p className="text-[0.64rem] text-[#9CA3AF]">{a.detail}</p>
                          </div>
                          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-[#9CA3AF]" />
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Usage Overview */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-[0.85rem] font-bold text-[#111827]">Usage Overview</h3>
                    <button className="flex items-center gap-1 text-[0.68rem] font-semibold text-[#6B7280] hover:text-[#111827]">
                      This Month <ChevronDown className="h-3 w-3" />
                    </button>
                  </div>
                  <div className="space-y-2.5">
                    {usageOverview.map((u, i) => {
                      const Icon = u.icon;
                      return (
                        <div key={i} className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex h-6 w-6 items-center justify-center rounded-[7px] bg-[#F0FBF6] text-[#38B88A]">
                              <Icon className="h-3 w-3" />
                            </div>
                            <span className="text-[0.72rem] font-semibold text-[#374151]">{u.label}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[0.72rem] font-bold text-[#111827]">{u.value}</span>
                            <span className="text-[0.62rem] font-bold text-[#38B88A]">{u.trend}</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Recent Activity */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-[0.85rem] font-bold text-[#111827]">Recent Activity</h3>
                    <button className="text-[0.68rem] font-bold text-[#38B88A] hover:underline">View All</button>
                  </div>
                  <div className="space-y-3">
                    {recentActivity.map((a, i) => {
                      const Icon = a.icon;
                      return (
                        <div key={i} className="flex items-start gap-2.5">
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-[7px] bg-[#F0FBF6] text-[#38B88A]">
                            <Icon className="h-3 w-3" />
                          </div>
                          <p className="flex-1 text-[0.7rem] font-semibold text-[#374151] leading-snug">{a.label}</p>
                          <span className="shrink-0 text-[0.62rem] font-semibold text-[#9CA3AF] whitespace-nowrap">{a.time}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

              </div>
            </motion.div>

            {/* ── Bottom Row ────────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-5 lg:grid-cols-12">

              {/* Task Categories */}
              <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 shadow-[0_1px_8px_rgba(148,163,184,0.06)] lg:col-span-4">
                <h3 className="mb-4 text-[0.88rem] font-bold text-[#111827]">Task Categories</h3>
                <TaskCategoryDonut />
              </div>

              {/* Task Success Rate */}
              <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 shadow-[0_1px_8px_rgba(148,163,184,0.06)] lg:col-span-8">
                <div className="mb-4 flex items-center justify-between">
                  <h3 className="text-[0.88rem] font-bold text-[#111827]">Task Success Rate</h3>
                  <button className="flex items-center gap-1 text-[0.72rem] font-semibold text-[#6B7280] hover:text-[#111827]">
                    This Month <ChevronDown className="h-3 w-3" />
                  </button>
                </div>
                {/* Y-axis labels */}
                <div className="flex gap-3">
                  <div className="flex flex-col justify-between text-[0.6rem] font-semibold text-[#9CA3AF] h-[100px] pb-0">
                    {["100%", "75%", "50%", "25%", "0%"].map((l) => <span key={l}>{l}</span>)}
                  </div>
                  <div className="flex-1">
                    <SuccessRateChart />
                  </div>
                </div>
              </div>

            </motion.div>

            {/* ── Footer ────────────────────────────────────────────────── */}
            <motion.footer variants={variants.fadeUp}
              className="flex flex-col gap-1.5 border-t border-[#E8EDF3] pt-4 pb-2 text-[0.72rem] text-[#9CA3AF] sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]" />
                <span>Enterprise Secure</span>
                <span>•</span><span>SOC 2 Type II</span>
                <span>•</span><span>GDPR Compliant</span>
                <span>•</span><span>ISO 27001</span>
              </div>
              <p>© 2026 CortexPrime. All rights reserved.</p>
            </motion.footer>

          </motion.div>
        </main>
      </div>
    </div>
  );
}
