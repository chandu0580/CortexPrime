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
  Database,
  Home,
  Mic,
  Monitor,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Target,
  Zap,
  Users,
  Clock,
  AlertTriangle,
  FileText,
  CheckCircle,
  Server,
  Filter,
  MoreVertical,
  Globe,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  monitoringKPIs,
  systemOverviewPoints,
  systemHealthComponents,
  SREAlerts,
  resourceGauges,
  topProcesses,
  liveEvents,
  type MonitoringKPI,
  type SystemOverviewPoint,
  type SystemHealthComponent,
  type MonitoringAlert,
  type ResourceGauge,
  type TopProcess,
  type LiveEventLog,
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
          const active = label === "Monitoring";
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
  const W = 180, H = 36;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 8) - 4}`);
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const uid = useMemo(() => "sl-" + Math.random().toString(36).slice(2, 7), []);
  return (
    <div className="h-9 w-full overflow-hidden mt-3">
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

// ─── STYLING/ICONS MAPPING FOR KPI CARDS ──────────────────────────────────────
const iconMap = {
  uptime: { icon: CheckCircle, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  response: { icon: Clock, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  agents: { icon: Users, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  tasks: { icon: AlertTriangle, bg: "bg-[#FEF2F2]", text: "text-[#EF4444]", border: "border-[#FEE2E2]" },
  load: { icon: Server, bg: "bg-[#E6F3FF]", text: "text-[#3B82F6]", border: "border-[#D1E7FF]" },
};

function KPICard({ item }: { item: MonitoringKPI }) {
  const style = iconMap[item.icon];
  const Icon = style.icon;

  return (
    <div className="rounded-[16px] border border-[#E8EDF3] bg-white pt-4 px-4 flex flex-col justify-between shadow-sm relative overflow-hidden">
      <div>
        <div className="flex items-start justify-between">
          <p className="text-[0.8rem] font-semibold text-[#6B7280]">{item.title}</p>
          <div className={cn("flex h-8 w-8 items-center justify-center rounded-[10px] border shrink-0", style.bg, style.text, style.border)}>
            <Icon className="h-4.5 w-4.5" />
          </div>
        </div>
        <div className="mt-2.5 flex items-baseline gap-2">
          <span className="text-[1.5rem] font-bold text-[#111827]">{item.value}</span>
          <span className="text-[0.72rem] font-bold flex items-center gap-0.5 text-[#38B88A]">
            {item.change}
          </span>
        </div>
        <p className="text-[0.66rem] text-[#9CA3AF] mt-1">{item.vsText}</p>
      </div>
      <Sparkline data={item.sparkline} color={item.color} />
    </div>
  );
}

// ─── SYSTEM OVERVIEW MULTI-LINE CHART ─────────────────────────────────────────
function SystemOverviewChart({ data }: { data: SystemOverviewPoint[] }) {
  const W = 600;
  const H = 220;
  const padL = 36;
  const padR = 15;
  const padT = 20;
  const padB = 30;

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;
  const getY = (val: number) => padT + plotH - (val / 100) * plotH;

  const cpuPoints = data.map((d, i) => `${getX(i)},${getY(d.cpu)}`);
  const memPoints = data.map((d, i) => `${getX(i)},${getY(d.memory)}`);
  const diskPoints = data.map((d, i) => `${getX(i)},${getY(d.disk)}`);
  const netPoints = data.map((d, i) => `${getX(i)},${getY(d.network * 5)}`); // scale network slightly for visual balance

  const cpuPath = `M ${cpuPoints.join(" L ")}`;
  const memPath = `M ${memPoints.join(" L ")}`;
  const diskPath = `M ${diskPoints.join(" L ")}`;
  const netPath = `M ${netPoints.join(" L ")}`;

  const gridTicks = [0, 25, 50, 75, 100];

  return (
    <div className="w-full h-[220px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        {/* Grid lines */}
        {gridTicks.map((tick, i) => {
          const y = getY(tick);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#F1F5F9" strokeWidth="1" strokeDasharray="3 3" />
              <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[10px] font-semibold fill-[#9CA3AF]">{tick}</text>
            </g>
          );
        })}

        {/* Bottom X Labels */}
        {data.map((d, i) => (
          <text key={i} x={getX(i)} y={H - 8} textAnchor="middle" className="text-[10px] font-semibold fill-[#9CA3AF]">{d.time}</text>
        ))}

        {/* Lines */}
        <path d={cpuPath} fill="none" stroke="#38B88A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={memPath} fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={diskPath} fill="none" stroke="#8B5CF6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={netPath} fill="none" stroke="#F59E0B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Dots */}
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={getX(i)} cy={getY(d.cpu)} r="3" fill="#38B88A" stroke="#FFFFFF" strokeWidth="1" />
            <circle cx={getX(i)} cy={getY(d.memory)} r="3" fill="#3B82F6" stroke="#FFFFFF" strokeWidth="1" />
            <circle cx={getX(i)} cy={getY(d.disk)} r="3" fill="#8B5CF6" stroke="#FFFFFF" strokeWidth="1" />
            <circle cx={getX(i)} cy={getY(d.network * 5)} r="3" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="1" />
          </g>
        ))}
      </svg>
    </div>
  );
}

// ─── CIRCULAR GAUGES ──────────────────────────────────────────────────────────
function CircularGauge({ item }: { item: ResourceGauge }) {
  const radius = 36;
  const circumference = 2 * Math.PI * radius; // 226.19
  const offset = circumference - (item.percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center text-center">
      <div className="relative h-24 w-24">
        <svg viewBox="0 0 100 100" className="h-full w-full rotate-[-90deg]">
          {/* Background circle */}
          <circle cx="50" cy="50" r={radius} fill="transparent" stroke="#F1F5F9" strokeWidth="8" />
          {/* Progress circle */}
          <circle
            cx="50"
            cy="50"
            r={radius}
            fill="transparent"
            stroke={item.color}
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-500"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center leading-tight">
          <span className="text-[1.2rem] font-bold text-[#111827]">{item.percentage}%</span>
          <span className="text-[0.54rem] font-bold text-[#9CA3AF]">Avg Usage</span>
        </div>
      </div>
      <span className="text-[0.74rem] font-bold text-[#374151] mt-2">{item.label}</span>
      <span className="text-[0.62rem] font-bold text-[#9CA3AF] mt-0.5">{item.peak}</span>
    </div>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function MonitoringCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;
  const [activeTab, setActiveTab] = useState("Overview");

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed(!collapsed)} />

      <div className="flex flex-col min-h-screen transition-all duration-300" style={{ marginLeft: sidebarWidth }}>
        <TopBar sidebarWidth={sidebarWidth} />

        {/* Content container */}
        <main className="flex-1 px-6 pt-20 pb-12">
          {/* Page Heading */}
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center mb-6">
            <div>
              <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827]">Monitoring Center</h1>
              <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5">
                Real-time monitoring of system health, performance, and resources.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-[0.76rem] font-bold text-[#374151]">
                <span className="h-2 w-2 rounded-full bg-[#38B88A] animate-pulse" />
                <span>Live</span>
              </div>
              <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-[0.76rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
                <span>Last 24 Hours</span>
                <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
              </button>
              <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.76rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                <Filter className="h-3.5 w-3.5 text-[#9CA3AF]" />
                <span>Filters</span>
              </button>
            </div>
          </div>

          {/* Staggered container for dashboard components */}
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.01)}
            className="space-y-6"
          >
            {/* Row 1: KPI Cards */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
              {monitoringKPIs.map((kpi) => (
                <KPICard key={kpi.title} item={kpi} />
              ))}
            </motion.div>

            {/* Row 2: System Overview / System Health Component table */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* System Overview line chart */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-8 flex flex-col justify-between">
                <div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">System Overview</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>Last 24 Hours</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>

                  {/* Tabs */}
                  <div className="flex border-b border-[#F1F5F9] pb-px mb-4">
                    {["Overview", "Performance", "Resources", "Network"].map((tab) => (
                      <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        className={cn(
                          "px-4 py-2 text-[0.74rem] font-bold border-b-2 -mb-px transition-all shrink-0",
                          activeTab === tab
                            ? "border-[#38B88A] text-[#2F9F77]"
                            : "border-transparent text-[#6B7280] hover:text-[#374151]"
                        )}
                      >
                        {tab}
                      </button>
                    ))}
                  </div>

                  {/* Legends */}
                  <div className="flex flex-wrap items-center gap-4 text-[0.66rem] font-bold mb-4">
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
                      <span className="text-[#6B7280]">CPU Usage (%)</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#3B82F6]" />
                      <span className="text-[#6B7280]">Memory Usage (%)</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#8B5CF6]" />
                      <span className="text-[#6B7280]">Disk Usage (%)</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B]" />
                      <span className="text-[#6B7280]">Network I/O (MB/s)</span>
                    </div>
                  </div>
                </div>

                <SystemOverviewChart data={systemOverviewPoints} />
              </div>

              {/* System Health */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">System Health</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[0.7rem] font-semibold">
                      <thead>
                        <tr className="border-b border-[#F1F5F9] pb-1.5 text-[0.62rem] font-bold text-[#9CA3AF] uppercase tracking-wider">
                          <th className="py-1">Component</th>
                          <th className="py-1">Status</th>
                          <th className="py-1">Health</th>
                          <th className="py-1">Details</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F1F5F9]">
                        {systemHealthComponents.map((comp) => (
                          <tr key={comp.name} className="hover:bg-[#FAFCFB] transition-colors">
                            <td className="py-2 text-[#374151] font-bold">{comp.name}</td>
                            <td className="py-2">
                              <span className="inline-flex items-center gap-1">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
                                <span className="text-[#2F9F77]">{comp.status}</span>
                              </span>
                            </td>
                            <td className="py-2">
                              <div className="flex items-center gap-2">
                                <span className="text-[#111827] font-bold w-8">{comp.health}%</span>
                                <div className="w-12 h-1 rounded-full bg-[#F1F5F9] overflow-hidden shrink-0">
                                  <div className="h-full bg-[#38B88A] rounded-full" style={{ width: `${comp.health}%` }} />
                                </div>
                              </div>
                            </td>
                            <td className="py-2 text-[#6B7280] max-w-[100px] truncate">{comp.details}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Row 3: Alerts / Resource Usage gauges / Events Feed */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Alerts timeline */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Alerts</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>
                  <div className="space-y-3">
                    {SREAlerts.map((alert, i) => (
                      <div key={i} className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-2.5 last:border-0 last:pb-0">
                        <div className="flex items-start gap-2.5 min-w-0">
                          <div className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] border",
                            alert.risk === "High" ? "bg-[#FEF2F2] text-[#EF4444] border-[#FEE2E2]" :
                            alert.risk === "Medium" ? "bg-[#FFFBEB] text-[#F59E0B] border-[#FDECC8]" :
                            "bg-[#EFF6FF] text-[#3B82F6] border-[#DBEAFE]"
                          )}>
                            <AlertTriangle className="h-3.5 w-3.5" />
                          </div>
                          <div>
                            <p className="text-[#374151] font-bold truncate">{alert.title}</p>
                            <p className="text-[0.64rem] text-[#9CA3AF] mt-0.5 font-medium leading-normal">{alert.description}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0 ml-2">
                          <span className={cn("inline-flex items-center rounded px-1.5 py-0.5 text-[0.58rem] font-extrabold uppercase tracking-wider",
                            alert.risk === "High" ? "bg-[#FEF2F2] text-[#EF4444]" :
                            alert.risk === "Medium" ? "bg-[#FFFBEB] text-[#F59E0B]" :
                            "bg-[#EFF6FF] text-[#3B82F6]"
                          )}>
                            {alert.risk}
                          </span>
                          <span className="text-[0.62rem] text-[#9CA3AF] font-semibold">{alert.time}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="pt-2 border-t border-[#F1F5F9] mt-3 text-[0.68rem] font-semibold text-[#9CA3AF]">
                  Showing 1 to 5 of 12 alerts
                </div>
              </div>

              {/* Resource Usage Circular Gauges & Processes Table */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Resource Usage</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>Last 24 Hours</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>

                  {/* 3 Circular gauges */}
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    {resourceGauges.map((g) => (
                      <CircularGauge key={g.label} item={g} />
                    ))}
                  </div>

                  {/* Processes Table */}
                  <p className="text-[0.74rem] font-bold text-[#111827] mb-2 uppercase tracking-wide">Top Processes</p>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[0.7rem] font-semibold">
                      <thead>
                        <tr className="border-b border-[#F1F5F9] pb-1.5 text-[0.62rem] font-bold text-[#9CA3AF] uppercase tracking-wider">
                          <th className="py-1">Process</th>
                          <th className="py-1">CPU</th>
                          <th className="py-1">Memory</th>
                          <th className="py-1 text-right">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F1F5F9]">
                        {topProcesses.map((p) => (
                          <tr key={p.name}>
                            <td className="py-1.5 text-[#374151] font-bold">{p.name}</td>
                            <td className="py-1.5 text-[#111827] font-bold">{p.cpu}</td>
                            <td className="py-1.5 text-[#6B7280]">{p.memory}</td>
                            <td className="py-1.5 text-right">
                              <span className="inline-flex items-center gap-1">
                                <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
                                <span className="text-[#2F9F77]">{p.status}</span>
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>

              {/* Events Feed timeline */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Events Feed</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>

                  <div className="relative pl-4 border-l-2 border-[#F1F5F9] space-y-4">
                    {liveEvents.map((evt, idx) => (
                      <div key={idx} className="relative">
                        {/* Dot indicator aligned to the vertical left border */}
                        <div className={cn("absolute -left-[21px] top-1 h-2.5 w-2.5 rounded-full border-2 border-white",
                          evt.tag === "Success" || evt.tag === "Resolved" ? "bg-[#38B88A]" : "bg-[#3B82F6]"
                        )} />
                        <div className="flex items-start justify-between gap-2 text-[0.74rem] font-semibold">
                          <div>
                            <p className="text-[0.64rem] text-[#9CA3AF] font-bold">{evt.timestamp}</p>
                            <p className="text-[#374151] mt-0.5 font-bold leading-normal">{evt.message}</p>
                          </div>
                          <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[0.58rem] font-bold tracking-wider shrink-0",
                            evt.tag === "Success" ? "bg-[#ECFBF4] text-[#2F9F77]" :
                            evt.tag === "Resolved" ? "bg-[#ECFBF4] text-[#2F9F77]" :
                            "bg-[#EFF6FF] text-[#2563EB]"
                          )}>
                            {evt.tag}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="pt-2 border-t border-[#F1F5F9] mt-3 text-[0.68rem] font-semibold text-[#9CA3AF]">
                  Showing 1 to 5 of 25 events
                </div>
              </div>
            </motion.div>
          </motion.div>
        </main>

        {/* Footer */}
        <footer className="mt-auto border-t border-[#E8EDF3] bg-white px-6 py-4 flex flex-col sm:flex-row justify-between items-center gap-2 text-[0.7rem] font-semibold text-[#9CA3AF]">
          <div className="flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4 text-[#38B88A]" />
            <span>Enterprise-Grade Encryption & Audit Logging Active</span>
          </div>
          <p>© {new Date().getFullYear()} CortexPrime OS. All rights reserved.</p>
        </footer>
      </div>
    </div>
  );
}
