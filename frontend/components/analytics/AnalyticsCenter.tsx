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
  Globe,
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
  TrendingUp,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  kpiMetrics,
  performanceSeries,
  usageByCategory,
  topAgents,
  actionTypes,
  successRateOverTime,
  keyInsights,
  heatmapData,
  heatmapHours,
  summaryItems,
  type KPICardData,
  type InsightData,
  type PerformanceData,
  type SuccessRateData,
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
          const active = label === "Analytics";
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
  sessions: { icon: Users, bg: "bg-[#E6F3FF]", text: "text-[#3B82F6]", border: "border-[#D1E7FF]" },
  actions: { icon: Zap, bg: "bg-[#F3E8FF]", text: "text-[#8B5CF6]", border: "border-[#E9D5FF]" },
  compute: { icon: Clock, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  data: { icon: Database, bg: "bg-[#FFF3E0]", text: "text-[#F59E0B]", border: "border-[#FFE0B2]" },
  success: { icon: Target, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  errors: { icon: AlertTriangle, bg: "bg-[#FEF2F2]", text: "text-[#EF4444]", border: "border-[#FEE2E2]" },
};

function KPICard({ item }: { item: KPICardData }) {
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
          <span className={cn("text-[0.72rem] font-bold flex items-center gap-0.5", item.isPositive ? "text-[#38B88A]" : "text-[#EF4444]")}>
            {item.change}
          </span>
        </div>
        <p className="text-[0.66rem] text-[#9CA3AF] mt-1">{item.vsText}</p>
      </div>
      <Sparkline data={item.sparkline} color={item.color} />
    </div>
  );
}

// ─── PERFORMANCE OVER TIME CHART ──────────────────────────────────────────────
function PerformanceLineChart({ data }: { data: PerformanceData[] }) {
  const W = 600;
  const H = 220;
  const padL = 40;
  const padR = 40;
  const padT = 20;
  const padB = 30;

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  // X coords mapper
  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;
  // Left Y axis (0 - 300)
  const getYLeft = (val: number) => padT + plotH - (val / 300) * plotH;
  // Right Y axis (80 - 100)
  const getYRight = (val: number) => padT + plotH - ((val - 80) / 20) * plotH;

  // Generate paths
  const sessionsPoints = data.map((d, i) => `${getX(i)},${getYLeft(d.sessions)}`);
  const actionsPoints = data.map((d, i) => `${getX(i)},${getYLeft(d.actions)}`);
  const successPoints = data.map((d, i) => `${getX(i)},${getYRight(d.successRate)}`);

  const sessionsPath = `M ${sessionsPoints.join(" L ")}`;
  const actionsPath = `M ${actionsPoints.join(" L ")}`;
  const successPath = `M ${successPoints.join(" L ")}`;

  // Area under Sessions
  const sessionsFill = `${sessionsPath} L ${getX(data.length - 1)},${padT + plotH} L ${getX(0)},${padT + plotH} Z`;

  const gridTicks = [0, 50, 100, 150, 200, 250, 300];

  return (
    <div className="w-full h-[220px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id="sessionsGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#38B88A" stopOpacity={0.06} />
            <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {gridTicks.map((tick, i) => {
          const y = getYLeft(tick);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#F1F5F9" strokeWidth="1" strokeDasharray={tick === 0 ? "none" : "3 3"} />
              <text x={padL - 10} y={y + 4} textAnchor="end" className="text-[10px] font-semibold fill-[#9CA3AF]">{tick}</text>
            </g>
          );
        })}

        {/* Right axis ticks (80% to 100%) */}
        {[80, 85, 90, 95, 100].map((tick, i) => {
          const y = getYRight(tick);
          return (
            <text key={i} x={W - padR + 10} y={y + 4} textAnchor="start" className="text-[10px] font-semibold fill-[#9CA3AF]">{tick}%</text>
          );
        })}

        {/* Bottom X Labels */}
        {data.map((d, i) => (
          <text key={i} x={getX(i)} y={H - 8} textAnchor="middle" className="text-[10px] font-semibold fill-[#9CA3AF]">{d.date}</text>
        ))}

        {/* Fill */}
        <path d={sessionsFill} fill="url(#sessionsGrad)" />

        {/* Line paths */}
        <path d={sessionsPath} fill="none" stroke="#38B88A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={actionsPath} fill="none" stroke="#3B82F6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        <path d={successPath} fill="none" stroke="#8B5CF6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Data points */}
        {data.map((d, i) => (
          <g key={i}>
            <circle cx={getX(i)} cy={getYLeft(d.sessions)} r="3" fill="#38B88A" stroke="#FFFFFF" strokeWidth="1.5" />
            <circle cx={getX(i)} cy={getYLeft(d.actions)} r="3" fill="#3B82F6" stroke="#FFFFFF" strokeWidth="1.5" />
            <circle cx={getX(i)} cy={getYRight(d.successRate)} r="3" fill="#8B5CF6" stroke="#FFFFFF" strokeWidth="1.5" />
          </g>
        ))}
      </svg>
    </div>
  );
}

// ─── SUCCESS RATE OVER TIME ──────────────────────────────────────────────────
function SuccessRateLineChart({ data }: { data: SuccessRateData[] }) {
  const W = 400;
  const H = 220;
  const padL = 36;
  const padR = 15;
  const padT = 20;
  const padB = 30;

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;
  const getY = (val: number) => padT + plotH - ((val - 80) / 20) * plotH;

  const points = data.map((d, i) => `${getX(i)},${getY(d.rate)}`);
  const linePath = `M ${points.join(" L ")}`;

  const gridTicks = [80, 85, 90, 95, 100];

  return (
    <div className="w-full h-[220px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        {/* Grid lines */}
        {gridTicks.map((tick, i) => {
          const y = getY(tick);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#F1F5F9" strokeWidth="1" strokeDasharray="3 3" />
              <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[10px] font-semibold fill-[#9CA3AF]">{tick}%</text>
            </g>
          );
        })}

        {/* Bottom X Labels */}
        {data.map((d, i) => (
          <text key={i} x={getX(i)} y={H - 8} textAnchor="middle" className="text-[10px] font-semibold fill-[#9CA3AF]">{d.date}</text>
        ))}

        {/* Line path */}
        <path d={linePath} fill="none" stroke="#38B88A" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />

        {/* Dots */}
        {data.map((d, i) => (
          <circle key={i} cx={getX(i)} cy={getY(d.rate)} r="3.5" fill="#38B88A" stroke="#FFFFFF" strokeWidth="1.5" />
        ))}
      </svg>
    </div>
  );
}

// ─── DONUT CHART ──────────────────────────────────────────────────────────────
function DonutChart() {
  const radius = 70;
  const circumference = 2 * Math.PI * radius; // 439.82

  let accumulatedPercent = 0;
  const sectors = usageByCategory.map((item) => {
    const dashArray = `${(item.percentage / 100) * circumference} ${circumference}`;
    const dashOffset = -((accumulatedPercent / 100) * circumference);
    accumulatedPercent += item.percentage;
    return {
      ...item,
      dashArray,
      dashOffset,
    };
  });

  return (
    <div className="flex flex-col items-center justify-center">
      <div className="relative h-44 w-44">
        <svg viewBox="0 0 200 200" className="h-full w-full rotate-[-90deg]">
          {sectors.map((sector, i) => (
            <circle
              key={i}
              cx="100"
              cy="100"
              r={radius}
              fill="transparent"
              stroke={sector.color}
              strokeWidth="22"
              strokeDasharray={sector.dashArray}
              strokeDashoffset={sector.dashOffset}
              className="transition-all duration-500"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[1.4rem] font-bold text-[#111827]">12,842</span>
          <span className="text-[0.62rem] font-bold text-[#6B7280]">Total Actions</span>
        </div>
      </div>
      <div className="mt-4 w-full space-y-1 px-2">
        {usageByCategory.map((c) => (
          <div key={c.category} className="flex items-center justify-between text-[0.74rem]">
            <div className="flex items-center gap-2 text-[#374151] font-semibold">
              <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
              <span>{c.category}</span>
            </div>
            <div className="flex gap-1.5 text-[#6B7280] font-semibold">
              <span className="text-[#111827]">{c.percentage}%</span>
              <span>({c.actions.toLocaleString()})</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── KEY INSIGHTS LIST ────────────────────────────────────────────────────────
const insightStyles = {
  success: { bg: "bg-[#ECFBF4]", border: "border-[#D6F0E5]", text: "text-[#2F9F77]", icon: TrendingUp },
  info: { bg: "bg-[#EFF6FF]", border: "border-[#DBEAFE]", text: "text-[#2563EB]", icon: Clock },
  purple: { bg: "bg-[#F5F3FF]", border: "border-[#EDE9FE]", text: "text-[#7C3AED]", icon: Brain },
  warning: { bg: "bg-[#FFFBEB]", border: "border-[#FDECC8]", text: "text-[#B45309]", icon: AlertTriangle },
};

function InsightRow({ insight }: { insight: InsightData }) {
  const style = insightStyles[insight.type];
  const Icon = style.icon;
  return (
    <div className="flex items-start gap-3 rounded-[12px] border border-[#E8EDF3] bg-white p-3 shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
      <div className={cn("flex h-8 w-8 items-center justify-center rounded-[10px] border shrink-0", style.bg, style.text, style.border)}>
        <Icon className="h-4.5 w-4.5" />
      </div>
      <div>
        <p className="text-[0.78rem] font-bold text-[#111827]">{insight.title}</p>
        <p className="text-[0.72rem] text-[#6B7280] mt-0.5 font-medium leading-relaxed">{insight.text}</p>
      </div>
    </div>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function AnalyticsCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;

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
              <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827]">Analytics Center</h1>
              <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5">
                Track performance, analyze trends, and gain insights across your AI operations.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-[0.76rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
                <Clock className="h-3.5 w-3.5 text-[#9CA3AF]" />
                <span>May 6 – May 12, 2024</span>
                <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
              </button>
              <button className="flex items-center gap-1 rounded-[12px] bg-[#38B88A] hover:bg-[#2F9F77] px-3.5 py-2 text-[0.76rem] font-bold text-white transition-colors">
                <Plus className="h-3.5 w-3.5" />
                <span>Export</span>
                <ChevronDown className="h-3 w-3" />
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
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6">
              {kpiMetrics.map((kpi) => (
                <KPICard key={kpi.title} item={kpi} />
              ))}
            </motion.div>

            {/* Row 2: Performance Over Time / Usage By Category / Top Agents */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Performance Over Time */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-6 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Performance Over Time</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>Last 7 Days</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>
                  <div className="flex items-center gap-4 mb-4 text-[0.7rem] font-bold">
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
                      <span className="text-[#6B7280]">Sessions</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-[#3B82F6]" />
                      <span className="text-[#6B7280]">Actions</span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="h-2 w-2 rounded-full bg-[#8B5CF6]" />
                      <span className="text-[#6B7280]">Success Rate (%)</span>
                    </div>
                  </div>
                </div>
                <PerformanceLineChart data={performanceSeries} />
              </div>

              {/* Usage by Category */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-3">
                <p className="text-[0.88rem] font-bold text-[#111827] mb-4">Usage by Category</p>
                <DonutChart />
              </div>

              {/* Top Agents */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-3 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Top Agents by Activity</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>This Week</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>
                  <div className="flex items-center justify-between border-b border-[#F1F5F9] pb-1.5 text-[0.68rem] font-bold text-[#9CA3AF] uppercase tracking-wider mb-2">
                    <span>Agent</span>
                    <div className="flex gap-8">
                      <span>Actions</span>
                      <span className="w-10 text-right">Change</span>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {topAgents.map((agent) => (
                      <div key={agent.name} className="flex items-center justify-between text-[0.74rem] font-semibold">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="flex h-6 w-6 items-center justify-center rounded-[6px] border border-[#F1F5F9] bg-[#F8FAF9] shrink-0 text-[#6B7280]">
                            <Bot className="h-3.5 w-3.5" />
                          </div>
                          <span className="truncate text-[#374151]">{agent.name}</span>
                        </div>
                        <div className="flex items-center gap-4 shrink-0">
                          {/* visual miniature bar */}
                          <div className="hidden sm:block w-16 h-1.5 rounded-full bg-[#F1F5F9] overflow-hidden">
                            <div className="h-full rounded-full" style={{ width: `${(agent.actions / 4158) * 100}%`, backgroundColor: agent.color }} />
                          </div>
                          <span className="text-[#111827] font-bold w-10 text-right">{agent.actions.toLocaleString()}</span>
                          <span className={cn("text-[0.68rem] font-bold w-10 text-right", agent.isPositive ? "text-[#38B88A]" : "text-[#EF4444]")}>
                            {agent.change}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Row 3: Actions by Type / Success Rate Over Time / Key Insights */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Actions by Type */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Actions by Type</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>This Week</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>
                  <div className="space-y-3.5 mt-2">
                    {actionTypes.map((act) => (
                      <div key={act.type} className="space-y-1">
                        <div className="flex items-center justify-between text-[0.74rem] font-semibold">
                          <span className="text-[#374151]">{act.type}</span>
                          <span className="text-[#6B7280] font-bold">
                            {act.actions.toLocaleString()} <span className="text-[0.68rem] font-semibold text-[#9CA3AF]">({act.percentage}%)</span>
                          </span>
                        </div>
                        <div className="h-2 w-full rounded-full bg-[#F1F5F9] overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${act.percentage}%`, backgroundColor: act.color }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {/* Horizontal scale */}
                <div className="mt-4 border-t border-[#F1F5F9] pt-2 flex justify-between text-[0.64rem] font-bold text-[#9CA3AF] px-1">
                  <span>0</span>
                  <span>1K</span>
                  <span>2K</span>
                  <span>3K</span>
                  <span>4K</span>
                </div>
              </div>

              {/* Success Rate Over Time */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-5 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-[0.88rem] font-bold text-[#111827]">Success Rate Over Time</p>
                  <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                    <span>Last 7 Days</span>
                    <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                  </button>
                </div>
                <SuccessRateLineChart data={successRateOverTime} />
              </div>

              {/* Key Insights */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-3">
                <p className="text-[0.88rem] font-bold text-[#111827] mb-3">Key Insights</p>
                <div className="space-y-2.5">
                  {keyInsights.map((insight, idx) => (
                    <InsightRow key={idx} insight={insight} />
                  ))}
                </div>
              </div>
            </motion.div>

            {/* Row 4: Activity Heatmap / Summary */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Activity Heatmap */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-9 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Activity Heatmap</p>
                    <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      <span>This Week</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>

                  <div className="overflow-x-auto">
                    <div className="min-w-[600px] mt-2">
                      <div className="grid gap-1 text-[0.64rem] font-bold text-[#9CA3AF] text-center mb-1" style={{ gridTemplateColumns: 'repeat(13, minmax(0, 1fr))' }}>
                        <div className="w-8 shrink-0 text-left"></div>
                        {heatmapHours.map((h, i) => (
                          <div key={i} className="flex-1">{h}</div>
                        ))}
                      </div>
                      <div className="space-y-1">
                        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, rIdx) => (
                          <div key={day} className="grid gap-1 items-center" style={{ gridTemplateColumns: 'repeat(13, minmax(0, 1fr))' }}>
                            <div className="w-8 shrink-0 text-[0.66rem] font-bold text-[#6B7280] text-left">{day}</div>
                            {heatmapData[rIdx].map((val, cIdx) => {
                              // Shade colors based on intensity
                              let bg = "bg-[#ECFBF4]"; // default min (very light green)
                              if (val > 8) bg = "bg-[#1B664B]"; // dark green
                              else if (val > 6) bg = "bg-[#288B67]";
                              else if (val > 4) bg = "bg-[#38B88A]"; // brand green
                              else if (val > 2) bg = "bg-[#71D2AC]";
                              else if (val > 1) bg = "bg-[#A7ECCE]";
                              return (
                                <div
                                  key={cIdx}
                                  className={cn("h-7 rounded-[4px] border border-white flex-1 transition-all duration-300", bg)}
                                  title={`${day} @ Hour ${heatmapHours[cIdx]}: Intensity ${val}`}
                                />
                              );
                            })}
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Summary */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-3 flex flex-col justify-between">
                <div>
                  <p className="text-[0.88rem] font-bold text-[#111827] mb-3">Summary</p>
                  <div className="divide-y divide-[#F1F5F9]">
                    {summaryItems.map((item) => (
                      <div key={item.label} className="py-2.5 flex items-center justify-between text-[0.74rem] font-semibold">
                        <div className="flex items-center gap-2 text-[#6B7280]">
                          {item.label === "Total Users" && <Users className="h-4 w-4 shrink-0 text-[#9CA3AF]" />}
                          {item.label === "Active Missions" && <Target className="h-4 w-4 shrink-0 text-[#9CA3AF]" />}
                          {item.label === "Active Agents" && <Bot className="h-4 w-4 shrink-0 text-[#9CA3AF]" />}
                          {item.label === "System Uptime" && <Activity className="h-4 w-4 shrink-0 text-[#9CA3AF]" />}
                          {item.label === "Avg. Response Time" && <Clock className="h-4 w-4 shrink-0 text-[#9CA3AF]" />}
                          <span>{item.label}</span>
                        </div>
                        <div className="flex items-center gap-1.5 font-bold">
                          <span className="text-[#111827]">{item.value}</span>
                          {item.change && (
                            <span className={cn("text-[0.66rem] font-bold flex items-center", item.isPositive ? "text-[#38B88A]" : "text-[#EF4444]")}>
                              {item.change}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
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
