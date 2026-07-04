"use client";

import Image from "next/image";
import Link from "next/link";
import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Activity, Archive, BarChart2, Bell, Bot, Brain,
  ChevronDown, ChevronLeft, ChevronRight, Database,
  ExternalLink, FileText, Filter, Globe, HardDrive,
  Home, Mic, Monitor, MoreVertical, Network, Plus,
  Puzzle, RefreshCw, Search, Settings, Shield,
  ShieldCheck, Target, UploadCloud, CheckCircle2, Zap,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import { memoryMetrics, memoryRecords, usageData, recentActivity } from "./data";

// ─────────────────────────────────────────────────────────────────────────────
// SIDEBAR NAV
// ─────────────────────────────────────────────────────────────────────────────
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

// ─────────────────────────────────────────────────────────────────────────────
// SIDEBAR
// ─────────────────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside
      className={cn(
        "fixed inset-y-0 left-0 z-40 flex flex-col border-r border-[#E8EDF3] bg-white transition-all duration-300",
        collapsed ? "w-[60px]" : "w-[152px]"
      )}
    >
      {/* Logo */}
      <div className={cn("flex items-center gap-2 px-4 py-[18px]", collapsed && "justify-center px-2")}>
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-4.5 w-4.5 text-white" fill="none">
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

      {/* Nav Links */}
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-[2px]">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = label === "Memory";
          return (
            <Link
              key={label}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-[12px] px-2.5 py-2 text-[0.82rem] font-semibold transition-all",
                active
                  ? "bg-[#ECFBF4] text-[#2F9F77]"
                  : "text-[#6B7280] hover:bg-[#F5F7FA] hover:text-[#111827]",
                collapsed && "justify-center px-0"
              )}
            >
              <Icon className="h-[16px] w-[16px] shrink-0" />
              {!collapsed && <span>{label}</span>}
            </Link>
          );
        })}
      </nav>

      {/* Bottom: Status + Collapse */}
      <div className="px-2 pb-4 space-y-2">
        {!collapsed && (
          <div className="rounded-[12px] border border-[#E8EDF3] bg-[#F8FAF9] px-2.5 py-2">
            <p className="text-[0.66rem] font-bold text-[#6B7280] uppercase tracking-wider">System Status</p>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
              <span className="text-[0.72rem] font-bold text-[#38B88A]">Healthy</span>
            </div>
            <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5">All systems operational</p>
          </div>
        )}
        <button
          onClick={onCollapse}
          className={cn(
            "flex w-full items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-white px-2.5 py-1.5 text-[0.72rem] font-semibold text-[#6B7280] hover:bg-[#F5F7FA]",
            collapsed ? "justify-center" : ""
          )}
        >
          <ChevronLeft className={cn("h-3.5 w-3.5 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TOP HEADER
// ─────────────────────────────────────────────────────────────────────────────
function TopBar({ sidebarWidth }: { sidebarWidth: number }) {
  const avatar = useMemo(
    () =>
      `data:image/svg+xml;utf8,${encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
      )}`,
    []
  );

  return (
    <header
      className="fixed top-0 right-0 z-30 flex items-center gap-3 border-b border-[#E8EDF3] bg-white/96 px-5 py-2.5 backdrop-blur transition-all duration-300"
      style={{ left: sidebarWidth }}
    >
      {/* Search */}
      <label className="relative flex h-9 w-[220px] items-center">
        <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input
          type="search"
          placeholder="Search memory..."
          className="h-full w-full rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-12 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]"
        />
        <span className="absolute right-2.5 rounded-[6px] border border-[#E5E7EB] bg-white px-1 py-0.5 text-[0.6rem] font-semibold text-[#9CA3AF]">
          ⌘ K
        </span>
      </label>

      {/* Current Mission */}
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 xl:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]">
          <Target className="h-3 w-3" />
        </div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-1.5">
            <p className="text-[0.76rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.58rem] font-bold text-[#2F9F77]">
              <span className="h-1 w-1 rounded-full bg-[#38B88A]" />
              Running
            </span>
          </div>
        </div>
        <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
      </div>

      {/* Voice Status */}
      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 lg:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]">
          <Mic className="h-3 w-3" />
        </div>
        <div>
          <p className="text-[0.6rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <p className="text-[0.76rem] font-semibold text-[#111827]">Listening...</p>
        </div>
        <div className="ml-1 flex items-center gap-[2px]">
          {[3, 5, 4, 6, 3, 5, 4].map((h, i) => (
            <span
              key={i}
              className="w-[2px] rounded-full bg-[#38B88A]"
              style={{ height: `${h * 2}px` }}
            />
          ))}
        </div>
      </div>

      {/* Right: Bell + User */}
      <div className="ml-auto flex items-center gap-2.5">
        <button className="relative flex h-9 w-9 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-white text-[#374151] hover:bg-[#F5F7FA]">
          <Bell className="h-4 w-4" />
          <span className="absolute -right-1 -top-1 flex h-4.5 w-4.5 items-center justify-center rounded-full bg-[#EF4444] text-[0.58rem] font-bold text-white ring-2 ring-white">
            3
          </span>
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

// ─────────────────────────────────────────────────────────────────────────────
// SPARKLINE
// ─────────────────────────────────────────────────────────────────────────────
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const W = 120;
  const H = 36;
  const pts = data.map(
    (v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 8) - 4}`
  );
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const gid = `sp-${color.replace("#", "")}`;
  return (
    <div className="mt-3 h-9 w-full">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.16} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${gid})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// METRIC CARD
// ─────────────────────────────────────────────────────────────────────────────
const METRIC_ICONS: Record<string, React.FC<{ className?: string }>> = {
  "Total Memories":  Database,
  "Total Size":      HardDrive,
  "Embeddings":      Network,
  "Active Memories": CheckCircle2,
};

function MetricCard({ label, value, trend, data }: { label: string; value: string; trend: string; data: number[] }) {
  const Icon = METRIC_ICONS[label] || Database;
  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[0.72rem] font-semibold text-[#9CA3AF]">{label}</p>
        <div className="flex h-7 w-7 items-center justify-center rounded-[9px] border border-[#D6F0E5] bg-[#F0FBF6] text-[#38B88A]">
          <Icon className="h-3.5 w-3.5" />
        </div>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[1.6rem] font-bold tracking-tight text-[#111827]">{value}</span>
        <span className="text-[0.72rem] font-bold text-[#38B88A]">{trend}</span>
      </div>
      <Sparkline data={data} color="#38B88A" />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// DONUT CHART
// ─────────────────────────────────────────────────────────────────────────────
function DonutChart() {
  const total = usageData.reduce((acc, s) => acc + s.value, 0);
  const R = 40;
  const circ = 2 * Math.PI * R;
  let acc = 0;
  return (
    <div className="flex items-center gap-5">
      {/* SVG donut */}
      <div className="relative flex-shrink-0">
        <svg viewBox="0 0 100 100" className="h-[120px] w-[120px] -rotate-90">
          {usageData.map((s) => {
            const len = (s.value / total) * circ;
            const offset = circ - len;
            const rotate = (acc / total) * 360;
            acc += s.value;
            return (
              <circle
                key={s.label}
                cx="50" cy="50" r={R}
                fill="none"
                stroke={s.color}
                strokeWidth="11"
                strokeDasharray={`${len} ${circ - len}`}
                transform={`rotate(${rotate} 50 50)`}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[1rem] font-bold text-[#111827]">4.62 GB</span>
          <span className="text-[0.58rem] font-semibold uppercase tracking-wide text-[#9CA3AF]">Total Used</span>
        </div>
      </div>
      {/* Legend */}
      <div className="flex-1 space-y-2">
        {usageData.map((s) => (
          <div key={s.label} className="flex items-center justify-between text-[0.74rem]">
            <span className="flex items-center gap-1.5 font-medium text-[#6B7280]">
              <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: s.color }} />
              {s.label}
            </span>
            <span className="font-bold text-[#111827]">{s.amount}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// MEMORY CENTER
// ─────────────────────────────────────────────────────────────────────────────
export default function MemoryCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const [search, setSearch] = useState("");
  const sidebarWidth = collapsed ? 60 : 152;

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    if (!q) return memoryRecords;
    return memoryRecords.filter(
      (r) =>
        r.title.toLowerCase().includes(q) ||
        r.description.toLowerCase().includes(q) ||
        r.source.toLowerCase().includes(q)
    );
  }, [search]);

  const fourMetrics = memoryMetrics.slice(0, 4);

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <TopBar sidebarWidth={sidebarWidth} />

      <div
        className="flex min-h-screen flex-col pt-[57px] transition-all duration-300"
        style={{ paddingLeft: sidebarWidth }}
      >
        <main className="flex-1 px-5 py-5">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.01)}
            className="mx-auto max-w-[1400px] space-y-5"
          >
            {/* ── Page Header ────────────────────────────────────────────── */}
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Memory Center</h1>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">
                  Store, manage, and retrieve knowledge across your AI workforce.
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.8rem] font-semibold text-[#374151] hover:bg-[#F5F7FA]">
                  <Filter className="h-3.5 w-3.5 text-[#6B7280]" /> Filter
                </button>
                <button className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white shadow-[0_3px_10px_rgba(56,184,138,0.25)] hover:bg-[#2F9F77]">
                  <Plus className="h-3.5 w-3.5" /> Add Memory
                </button>
              </div>
            </motion.div>

            {/* ── 4 KPI Cards ────────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {fourMetrics.map((m) => (
                <MetricCard key={m.label} label={m.label} value={m.value} trend={m.trend} data={m.data} />
              ))}
            </motion.div>

            {/* ── Main Grid ─────────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-5 lg:grid-cols-12">

              {/* LEFT: Memory Explorer */}
              <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)] lg:col-span-9">
                {/* Table header */}
                <div className="flex flex-col gap-3 border-b border-[#E8EDF3] px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-[0.88rem] font-bold text-[#111827]">Memory Explorer</h2>
                  <div className="relative h-9 w-full sm:w-[280px]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search memories..."
                      className="h-full w-full rounded-[10px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-3 text-[0.78rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]"
                    />
                  </div>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[820px] border-collapse text-left">
                    <thead>
                      <tr className="border-b border-[#E8EDF3] text-[0.66rem] font-bold uppercase tracking-wider text-[#9CA3AF]">
                        <th className="px-5 py-3">Memory</th>
                        <th className="px-3 py-3">Type</th>
                        <th className="px-3 py-3">Source</th>
                        <th className="px-3 py-3">Created</th>
                        <th className="px-3 py-3">Last Accessed</th>
                        <th className="px-3 py-3">Relevance</th>
                        <th className="px-3 py-3">Status</th>
                        <th className="w-10 px-3 py-3" />
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((r, i) => {
                        const Icon = r.icon || FileText;
                        const isDoc = r.type === "Document";
                        const isWeb = r.type === "Web Page";
                        return (
                          <tr
                            key={i}
                            className="border-b border-[#F1F5F9] last:border-0 transition-colors hover:bg-[#F8FAF9]/60 cursor-pointer"
                          >
                            {/* Memory */}
                            <td className="px-5 py-3">
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] bg-[#F0FBF6] text-[#38B88A]">
                                  <Icon className="h-4 w-4" />
                                </div>
                                <div className="min-w-0">
                                  <p className="truncate text-[0.78rem] font-bold text-[#111827]">{r.title}</p>
                                  <p className="truncate text-[0.68rem] text-[#9CA3AF]">{r.description}</p>
                                </div>
                              </div>
                            </td>
                            {/* Type */}
                            <td className="px-3 py-3">
                              <span
                                className={cn(
                                  "inline-flex rounded-full px-2 py-0.5 text-[0.62rem] font-semibold",
                                  isDoc
                                    ? "bg-[#ECFBF4] text-[#2F9F77]"
                                    : isWeb
                                    ? "bg-[#DBEAFE] text-[#1D4ED8]"
                                    : "bg-[#F3E8FF] text-[#7C3AED]"
                                )}
                              >
                                {r.type}
                              </span>
                            </td>
                            {/* Source */}
                            <td className="px-3 py-3 text-[0.74rem] font-medium text-[#4B5563]">{r.source}</td>
                            {/* Created */}
                            <td className="px-3 py-3 text-[0.74rem] text-[#6B7280]">{r.indexed}</td>
                            {/* Last Accessed */}
                            <td className="px-3 py-3 text-[0.74rem] text-[#6B7280]">{r.lastAccessed}</td>
                            {/* Relevance */}
                            <td className="px-3 py-3">
                              <div className="flex items-center gap-2">
                                <span className="w-7 text-[0.74rem] font-bold text-[#111827]">
                                  {r.confidence}%
                                </span>
                                <div className="h-1.5 w-14 overflow-hidden rounded-full bg-[#E8EDF3]">
                                  <div
                                    className="h-full rounded-full bg-[#38B88A]"
                                    style={{ width: `${r.confidence}%` }}
                                  />
                                </div>
                              </div>
                            </td>
                            {/* Status */}
                            <td className="px-3 py-3">
                              <span
                                className={cn(
                                  "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.62rem] font-semibold",
                                  r.status === "active"
                                    ? "bg-[#ECFBF4] text-[#2F9F77]"
                                    : "bg-[#F3F4F6] text-[#6B7280]"
                                )}
                              >
                                <span
                                  className={cn(
                                    "h-1.5 w-1.5 rounded-full",
                                    r.status === "active" ? "bg-[#38B88A]" : "bg-[#9CA3AF]"
                                  )}
                                />
                                {r.status === "active" ? "Active" : "Archived"}
                              </span>
                            </td>
                            {/* Actions */}
                            <td className="px-3 py-3 text-right">
                              <button className="flex h-7 w-7 items-center justify-center rounded-[7px] text-[#9CA3AF] hover:bg-[#F1F5F9] hover:text-[#374151]">
                                <MoreVertical className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex flex-col gap-3 border-t border-[#E8EDF3] px-5 py-3.5 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-[0.74rem] text-[#6B7280]">
                    Showing 1 to 8 of 542,318 results
                  </p>
                  <div className="flex flex-wrap items-center gap-1">
                    <button className="flex h-8 w-8 items-center justify-center rounded-[9px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]">
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    {[1, 2, 3, 4, 5].map((p) => (
                      <button
                        key={p}
                        className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-[9px] border text-[0.74rem] font-semibold transition-all",
                          p === 1
                            ? "border-[#38B88A] bg-[#38B88A] text-white"
                            : "border-[#E8EDF3] text-[#374151] hover:bg-[#F5F7FA]"
                        )}
                      >
                        {p}
                      </button>
                    ))}
                    <span className="px-1 text-[0.74rem] text-[#9CA3AF]">...</span>
                    <button className="flex h-8 items-center justify-center rounded-[9px] border border-[#E8EDF3] px-2.5 text-[0.74rem] font-semibold text-[#374151] hover:bg-[#F5F7FA]">
                      67,790
                    </button>
                    <button className="flex h-8 w-8 items-center justify-center rounded-[9px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]">
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                    <div className="ml-1 flex h-8 items-center gap-1 rounded-[9px] border border-[#E8EDF3] px-2.5 text-[0.74rem] font-semibold text-[#374151] hover:bg-[#F5F7FA] cursor-pointer">
                      10 / page <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </div>
                  </div>
                </div>
              </div>

              {/* RIGHT: Widgets */}
              <div className="flex flex-col gap-4 lg:col-span-3">

                {/* Memory Usage */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <h3 className="mb-3.5 text-[0.85rem] font-bold text-[#111827]">Memory Usage</h3>
                  <DonutChart />
                </div>

                {/* Quick Actions */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <h3 className="mb-3 text-[0.85rem] font-bold text-[#111827]">Quick Actions</h3>
                  <div className="grid grid-cols-2 gap-2">
                    <button className="flex flex-col items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] py-3 text-[0.7rem] font-semibold text-[#374151] transition-all hover:border-[#B7E5D3] hover:bg-[#ECFBF4] hover:text-[#2F9F77]">
                      <UploadCloud className="h-4.5 w-4.5 text-[#38B88A]" />
                      Upload Document
                    </button>
                    <button className="flex flex-col items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] py-3 text-[0.7rem] font-semibold text-[#374151] transition-all hover:border-[#B7E5D3] hover:bg-[#ECFBF4] hover:text-[#2F9F77]">
                      <ExternalLink className="h-4.5 w-4.5 text-[#38B88A]" />
                      Add Web URL
                    </button>
                  </div>
                </div>

                {/* Recent Activity */}
                <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                  <h3 className="mb-3.5 text-[0.85rem] font-bold text-[#111827]">Recent Activity</h3>
                  <div className="space-y-3.5">
                    {recentActivity.map((a, i) => {
                      const Icon = a.icon;
                      return (
                        <div key={i} className="flex items-start gap-2.5">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] bg-[#F0FBF6] text-[#38B88A]">
                            <Icon className="h-3.5 w-3.5" />
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-[0.74rem] font-bold text-[#111827]">{a.label}</p>
                            <p className="truncate text-[0.66rem] text-[#9CA3AF]">{a.detail}</p>
                          </div>
                          <span className="shrink-0 text-[0.62rem] font-semibold text-[#9CA3AF]">{a.time}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

              </div>
            </motion.div>

            {/* ── Footer ───────────────────────────────────────────────── */}
            <motion.footer
              variants={variants.fadeUp}
              className="flex flex-col gap-1.5 border-t border-[#E8EDF3] pt-4 pb-2 text-[0.72rem] text-[#9CA3AF] sm:flex-row sm:items-center sm:justify-between"
            >
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
