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
  Shield,
  CheckCircle,
  Lock,
  MoreVertical,
  Globe,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  governanceKPIs,
  governancePolicies,
  complianceBreakdown,
  recentIncidents,
  accessRequests,
  violationSeries,
  topPolicyCategories,
  type GovernanceKPI,
  type GovernancePolicy,
  type GovernanceIncident,
  type AccessRequest,
  type PolicyViolationData,
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
          const active = label === "Governance";
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

// ─── USER AVATAR WITH SYSTEM INITIALS ──────────────────────────────────────────
function UserAvatar({ name }: { name: string }) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("");
  let bg = "bg-[#ECFBF4] text-[#2F9F77] border-[#D6F0E5]";
  if (name.includes("Morgan") || name.includes("Wilson")) bg = "bg-[#E6F3FF] text-[#3B82F6] border-[#D1E7FF]";
  else if (name.includes("Chen") || name.includes("Anderson")) bg = "bg-[#F3E8FF] text-[#8B5CF6] border-[#E9D5FF]";
  else if (name.includes("Lee") || name.includes("Kim")) bg = "bg-[#FEF2F2] text-[#EF4444] border-[#FEE2E2]";
  else if (name.includes("Brown") || name.includes("Park")) bg = "bg-[#FFF3E0] text-[#F59E0B] border-[#FFE0B2]";

  return (
    <div className={cn("h-6 w-6 rounded-full border flex items-center justify-center text-[0.65rem] font-bold shrink-0", bg)}>
      {initials}
    </div>
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
  shield: { icon: Shield, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  users: { icon: Users, bg: "bg-[#E6F3FF]", text: "text-[#3B82F6]", border: "border-[#D1E7FF]" },
  lock: { icon: Lock, bg: "bg-[#F3E8FF]", text: "text-[#8B5CF6]", border: "border-[#E9D5FF]" },
  checkCircle: { icon: CheckCircle, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  alertTriangle: { icon: AlertTriangle, bg: "bg-[#FEF2F2]", text: "text-[#EF4444]", border: "border-[#FEE2E2]" },
};

function KPICard({ item }: { item: GovernanceKPI }) {
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

// ─── COMPLIANCE OVERVIEW DONUT CHART ──────────────────────────────────────────
function ComplianceDonutChart() {
  const radius = 70;
  const circumference = 2 * Math.PI * radius; // 439.82

  let accumulatedPercent = 0;
  const sectors = complianceBreakdown.map((item) => {
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
    <div className="flex flex-col items-center justify-center md:flex-row md:gap-6">
      <div className="relative h-36 w-36 shrink-0">
        <svg viewBox="0 0 200 200" className="h-full w-full rotate-[-90deg]">
          {sectors.map((sector, i) => (
            <circle
              key={i}
              cx="100"
              cy="100"
              r={radius}
              fill="transparent"
              stroke={sector.color}
              strokeWidth="20"
              strokeDasharray={sector.dashArray}
              strokeDashoffset={sector.dashOffset}
              className="transition-all duration-500"
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-[1.4rem] font-bold text-[#111827]">98.6%</span>
          <span className="text-[0.62rem] font-bold text-[#6B7280]">Compliant</span>
        </div>
      </div>
      <div className="mt-4 md:mt-0 flex-1 space-y-1.5 w-full">
        {complianceBreakdown.map((c) => (
          <div key={c.status} className="flex items-center justify-between text-[0.74rem] font-semibold">
            <div className="flex items-center gap-2 text-[#374151]">
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
              <span>{c.status}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[#111827] font-bold w-10 text-right">{c.percentage}%</span>
              <span className={cn("text-[0.68rem] font-bold w-12 text-right", c.isPositive ? "text-[#38B88A]" : c.status === "Non-Compliant" ? "text-[#EF4444]" : "text-[#9CA3AF]")}>
                {c.change}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── POLICY VIOLATIONS LINE CHART ─────────────────────────────────────────────
function PolicyViolationsChart({ data }: { data: PolicyViolationData[] }) {
  const W = 400;
  const H = 160;
  const padL = 30;
  const padR = 15;
  const padT = 15;
  const padB = 25;

  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const getX = (idx: number) => padL + (idx / (data.length - 1)) * plotW;
  const getY = (val: number) => padT + plotH - (val / 20) * plotH;

  const points = data.map((d, i) => `${getX(i)},${getY(d.violations)}`);
  const linePath = `M ${points.join(" L ")}`;
  const fillPath = `${linePath} L ${getX(data.length - 1)},${padT + plotH} L ${getX(0)},${padT + plotH} Z`;

  const gridTicks = [0, 5, 10, 15, 20];
  const uid = useMemo(() => "vGrad-" + Math.random().toString(36).slice(2, 7), []);

  return (
    <div className="w-full h-[160px]">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#EF4444" stopOpacity={0.08} />
            <stop offset="100%" stopColor="#EF4444" stopOpacity={0} />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {gridTicks.map((tick, i) => {
          const y = getY(tick);
          return (
            <g key={i}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke="#F1F5F9" strokeWidth="1" strokeDasharray="3 3" />
              <text x={padL - 8} y={y + 4} textAnchor="end" className="text-[9px] font-semibold fill-[#9CA3AF]">{tick}</text>
            </g>
          );
        })}

        {/* Bottom X Labels */}
        {data.map((d, i) => (
          <text key={i} x={getX(i)} y={H - 4} textAnchor="middle" className="text-[9px] font-semibold fill-[#9CA3AF]">{d.date}</text>
        ))}

        {/* Area fill */}
        <path d={fillPath} fill={`url(#${uid})`} />

        {/* Line */}
        <path d={linePath} fill="none" stroke="#EF4444" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />

        {/* Dots */}
        {data.map((d, i) => (
          <circle key={i} cx={getX(i)} cy={getY(d.violations)} r="3" fill="#EF4444" stroke="#FFFFFF" strokeWidth="1.2" />
        ))}
      </svg>
    </div>
  );
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function GovernanceCenter() {
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
              <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827]">Governance Center</h1>
              <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5">
                Manage policies, access, compliance, and AI system governance.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3 py-2 text-[0.76rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
                <FileText className="h-3.5 w-3.5 text-[#9CA3AF]" />
                <span>Reports</span>
              </button>
              <button className="flex items-center gap-1 rounded-[12px] bg-[#38B88A] hover:bg-[#2F9F77] px-3.5 py-2 text-[0.76rem] font-bold text-white transition-colors">
                <Plus className="h-3.5 w-3.5" />
                <span>New Policy</span>
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
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
              {governanceKPIs.map((kpi) => (
                <KPICard key={kpi.title} item={kpi} />
              ))}
            </motion.div>

            {/* Row 2: Policies Table / Compliance Donut & Incidents */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Policies Table */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-8 flex flex-col justify-between">
                <div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Governance Policies</p>
                    <div className="flex items-center gap-2">
                      <label className="relative flex h-8 w-44 items-center">
                        <Search className="pointer-events-none absolute left-2.5 h-3 w-3 text-[#9CA3AF]" />
                        <input type="search" placeholder="Search policies..." className="h-full w-full rounded-[8px] border border-[#E8EDF3] pl-7.5 pr-2.5 text-[0.7rem] text-[#111827] outline-none placeholder:text-[#9CA3AF]" />
                      </label>
                      <button className="flex h-8 items-center gap-1.5 rounded-[8px] border border-[#E8EDF3] px-2.5 text-[0.7rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                        <span>All Categories</span>
                        <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[0.74rem]">
                      <thead>
                        <tr className="border-b border-[#F1F5F9] pb-2 text-[0.66rem] font-bold text-[#9CA3AF] uppercase tracking-wider">
                          <th className="py-2">Policy Name</th>
                          <th className="py-2">Category</th>
                          <th className="py-2">Status</th>
                          <th className="py-2">Last Updated</th>
                          <th className="py-2">Owner</th>
                          <th className="py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F1F5F9]">
                        {governancePolicies.map((policy) => (
                          <tr key={policy.name} className="hover:bg-[#FAFCFB] transition-colors">
                            <td className="py-2.5 pr-2 min-w-[200px]">
                              <div className="flex items-start gap-2.5">
                                <div className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] border",
                                  policy.status === "Active" ? "bg-[#ECFBF4] text-[#38B88A] border-[#D6F0E5]" : "bg-[#F8FAFC] text-[#6B7280] border-[#E5E7EB]"
                                )}>
                                  <Shield className="h-3.5 w-3.5" />
                                </div>
                                <div>
                                  <p className="font-bold text-[#111827]">{policy.name}</p>
                                  <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5 leading-normal">{policy.description}</p>
                                </div>
                              </div>
                            </td>
                            <td className="py-2.5 text-[#374151] font-semibold">{policy.category}</td>
                            <td className="py-2.5">
                              <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.66rem] font-bold ring-1",
                                policy.status === "Active" ? "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]" : "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]"
                              )}>
                                <span className={cn("h-1 w-1 rounded-full", policy.status === "Active" ? "bg-[#38B88A]" : "bg-[#9CA3AF]")} />
                                {policy.status}
                              </span>
                            </td>
                            <td className="py-2.5 text-[#6B7280] font-semibold">{policy.lastUpdated}</td>
                            <td className="py-2.5">
                              <div className="flex items-center gap-2">
                                <UserAvatar name={policy.owner} />
                                <span className="text-[#374151] font-semibold truncate max-w-[80px]">{policy.owner}</span>
                              </div>
                            </td>
                            <td className="py-2.5 text-right">
                              <button className="text-[#9CA3AF] hover:text-[#374151] p-1 rounded-md hover:bg-[#F1F5F9]">
                                <MoreVertical className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Pagination */}
                <div className="mt-4 pt-3 border-t border-[#F1F5F9] flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between text-[0.72rem] font-semibold text-[#6B7280]">
                  <span>Showing 1 to 6 of 48 policies</span>
                  <div className="flex items-center gap-1.5">
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#9CA3AF] disabled:opacity-40" disabled>
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <button className="h-7 w-7 rounded-[6px] bg-[#38B88A] text-white flex items-center justify-center">1</button>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">2</button>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">3</button>
                    <span className="px-1 text-[#9CA3AF]">...</span>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">8</button>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">
                      <ChevronLeft className="h-3.5 w-3.5 rotate-180" />
                    </button>
                    <button className="ml-1.5 flex h-7 items-center gap-1 rounded-[6px] border border-[#E8EDF3] px-2 text-[#374151] hover:bg-[#F8FAFC]">
                      <span>10 / page</span>
                      <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Compliance & Incidents Column */}
              <div className="lg:col-span-4 space-y-5">
                {/* Compliance Overview */}
                <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Compliance Overview</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View Details
                    </button>
                  </div>
                  <ComplianceDonutChart />
                </div>

                {/* Recent Incidents */}
                <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Recent Incidents</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>
                  <div className="space-y-2">
                    {recentIncidents.map((inc, i) => (
                      <div key={i} className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-2 last:border-b-0 last:pb-0">
                        <div className="flex items-start gap-2.5 min-w-0">
                          <div className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] border",
                            inc.risk === "High" ? "bg-[#FEF2F2] text-[#EF4444] border-[#FEE2E2]" :
                            inc.risk === "Medium" ? "bg-[#FFFBEB] text-[#F59E0B] border-[#FDECC8]" :
                            "bg-[#EFF6FF] text-[#3B82F6] border-[#DBEAFE]"
                          )}>
                            <AlertTriangle className="h-3.5 w-3.5" />
                          </div>
                          <div>
                            <p className="text-[#374151] font-bold truncate">{inc.title}</p>
                            <p className="text-[0.64rem] text-[#9CA3AF] mt-0.5 font-medium">{inc.timestamp}</p>
                          </div>
                        </div>
                        <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-[0.6rem] font-extrabold uppercase tracking-wider shrink-0",
                          inc.risk === "High" ? "bg-[#FEF2F2] text-[#EF4444]" :
                          inc.risk === "Medium" ? "bg-[#FFFBEB] text-[#F59E0B]" :
                          "bg-[#EFF6FF] text-[#3B82F6]"
                        )}>
                          {inc.risk}
                        </span>
                      </div>
                    ))}
                  </div>
                  <div className="pt-2 border-t border-[#F1F5F9] mt-3 text-[0.68rem] font-semibold text-[#9CA3AF]">
                    Showing 1 to 3 of 3 incidents
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Row 3: Access Requests / Policy Violations / Top Categories */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Access Requests */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Access Requests</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>
                  <div className="space-y-3">
                    {accessRequests.map((req, i) => (
                      <div key={i} className="flex items-center justify-between text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-2.5 last:border-0 last:pb-0">
                        <div className="flex items-center gap-2.5 min-w-0">
                          <UserAvatar name={req.user} />
                          <div className="min-w-0">
                            <p className="text-[#111827] font-bold truncate">{req.user}</p>
                            <p className="text-[0.66rem] text-[#6B7280] font-medium truncate mt-0.5">{req.request}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1.5 shrink-0 ml-2">
                          <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[0.62rem] font-bold ring-1",
                            req.status === "Approved" ? "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]" :
                            req.status === "Rejected" ? "bg-[#FEF2F2] text-[#EF4444] ring-[#FBD5D5]" :
                            "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]"
                          )}>
                            {req.status}
                          </span>
                          <span className="text-[0.62rem] text-[#9CA3AF] font-semibold">{req.time}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="pt-2 border-t border-[#F1F5F9] mt-3 text-[0.68rem] font-semibold text-[#9CA3AF]">
                  Showing 1 to 4 of 23 requests
                </div>
              </div>

              {/* Policy Violations Over Time */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div className="flex items-center justify-between mb-4">
                  <p className="text-[0.88rem] font-bold text-[#111827]">Policy Violations Over Time</p>
                  <button className="flex items-center gap-1 rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                    <span>Last 7 Days</span>
                    <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                  </button>
                </div>
                <PolicyViolationsChart data={violationSeries} />
              </div>

              {/* Top Policy Categories */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Top Policy Categories</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>
                  <div className="space-y-3">
                    {topPolicyCategories.map((c) => (
                      <div key={c.category} className="space-y-1">
                        <div className="flex items-center justify-between text-[0.74rem] font-semibold">
                          <div className="flex items-center gap-1.5 text-[#374151]">
                            <Shield className="h-3.5 w-3.5 shrink-0" style={{ color: c.color }} />
                            <span>{c.category}</span>
                          </div>
                          <span className="text-[#6B7280] font-bold">
                            {c.count} <span className="text-[0.68rem] font-semibold text-[#9CA3AF]">({c.percentage}%)</span>
                          </span>
                        </div>
                        <div className="h-1.5 w-full rounded-full bg-[#F1F5F9] overflow-hidden">
                          <div className="h-full rounded-full" style={{ width: `${c.percentage}%`, backgroundColor: c.color }} />
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
