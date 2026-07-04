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
  Plug,
  MessageSquare,
  Folder,
  Clipboard,
  User,
  Code,
  Calendar,
  Megaphone,
  DollarSign,
  Globe,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  integrationKPIs,
  integrationsList,
  donutSummary,
  recentActivityStream,
  activeCategories,
  popularIntegrationsList,
  type IntegrationKPI,
  type IntegrationItem,
  type DonutSummarySector,
  type RecentActivityItem,
  type CategoryCardData,
  type PopularIntegration,
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
          const active = label === "Integrations";
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
  plug: { icon: Plug, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  zap: { icon: Zap, bg: "bg-[#E6F3FF]", text: "text-[#3B82F6]", border: "border-[#D1E7FF]" },
  warning: { icon: AlertTriangle, bg: "bg-[#FEF2F2]", text: "text-[#EF4444]", border: "border-[#FEE2E2]" },
  api: { icon: Zap, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
  success: { icon: CheckCircle, bg: "bg-[#ECFBF4]", text: "text-[#38B88A]", border: "border-[#D6F0E5]" },
};

function KPICard({ item }: { item: IntegrationKPI }) {
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

// ─── BRAND LOGO ICONS ─────────────────────────────────────────────────────────
function BrandLogo({ type }: { type: string }) {
  if (type === "slack") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <path d="M5 10.5C5 9.7 5.7 9 6.5 9s1.5.7 1.5 1.5V13c0 .8-.7 1.5-1.5 1.5S5 13.8 5 13v-2.5zm0 4.5c0-.8.7-1.5 1.5-1.5s1.5.7 1.5 1.5v1.5c0 .8-.7 1.5-1.5 1.5S5 17.3 5 16.5V15z" fill="#E01E5A"/>
        <path d="M10.5 5c-.8 0-1.5.7-1.5 1.5s.7 1.5 1.5 1.5H13c.8 0 1.5-.7 1.5-1.5S13.8 5 13 5h-2.5zm4.5 0c-.8 0-1.5.7-1.5 1.5s.7 1.5 1.5 1.5h1.5c.8 0 1.5-.7 1.5-1.5S17.3 5 16.5 5H15z" fill="#36C5F0"/>
        <path d="M19 13.5c0 .8-.7 1.5-1.5 1.5s-1.5-.7-1.5-1.5V11c0-.8.7-1.5 1.5-1.5s1.5.7 1.5 1.5v2.5zm0-4.5c0 .8-.7 1.5-1.5 1.5s-1.5-.7-1.5-1.5V7.5c0-.8.7-1.5 1.5-1.5s1.5.7 1.5 1.5V9z" fill="#2EB67D"/>
        <path d="M13.5 19c.8 0 1.5-.7 1.5-1.5s-.7-1.5-1.5-1.5H11c-.8 0-1.5.7-1.5 1.5s.7 1.5 1.5 1.5h2.5zm-4.5 0c.8 0 1.5-.7 1.5-1.5s-.7-1.5-1.5-1.5H7.5c-.8 0-1.5.7-1.5 1.5s.7 1.5 1.5 1.5H9z" fill="#ECB22E"/>
      </svg>
    );
  }
  if (type === "gdrive") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <path d="M2.5 17L6.5 10H17.5L13.5 17H2.5Z" fill="#FFC107" />
        <path d="M17.5 10L13.5 3H6.5L10.5 10H17.5Z" fill="#00796B" />
        <path d="M13.5 17L10.5 10L6.5 17H13.5Z" fill="#3F51B5" />
      </svg>
    );
  }
  if (type === "m365") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="2" width="9" height="9" fill="#F25022" />
        <rect x="13" y="2" width="9" height="9" fill="#7FBA00" />
        <rect x="2" y="13" width="9" height="9" fill="#00A4EF" />
        <rect x="13" y="13" width="9" height="9" fill="#FFB900" />
      </svg>
    );
  }
  if (type === "salesforce") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <path d="M19.2 11.2c-.3-1.8-1.9-3.2-3.8-3.2-.8 0-1.5.3-2.1.7C12.4 6.8 10.3 5.5 8 5.5c-3.1 0-5.7 2.3-6 5.4C.8 11.5 0 12.7 0 14c0 2 1.6 3.6 3.6 3.6h15.2c2 0 3.6-1.6 3.6-3.6 0-1.4-.8-2.6-2.2-2.8z" fill="#00A1E0" />
      </svg>
    );
  }
  if (type === "github") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="#000000">
        <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482C19.137 20.197 22 16.44 22 12.017 22 6.484 17.522 2 12 2z" />
      </svg>
    );
  }
  if (type === "jira") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <path d="M11.5 3L7.5 7H11.5V3Z" fill="#0052CC" />
        <path d="M11.5 7L7.5 11H11.5V7Z" fill="#2684FF" />
        <path d="M11.5 11L3.5 19H11.5V11Z" fill="#0052CC" />
        <path d="M20.5 11L12.5 19H20.5V11Z" fill="#2684FF" />
      </svg>
    );
  }
  if (type === "twilio") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="10" fill="#F22F46" />
        <circle cx="9" cy="9" r="2" fill="#FFFFFF" />
        <circle cx="15" cy="9" r="2" fill="#FFFFFF" />
        <circle cx="9" cy="15" r="2" fill="#FFFFFF" />
        <circle cx="15" cy="15" r="2" fill="#FFFFFF" />
      </svg>
    );
  }
  if (type === "notion") {
    return (
      <svg className="h-5.5 w-5.5 shrink-0" viewBox="0 0 24 24" fill="#000000">
        <path d="M4 3h16a2 2 0 012 2v14a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2zm2 4v10h2.5V9.5L14 17h3.5V7H15v7.5L9.5 7H6z" />
      </svg>
    );
  }
  return <Puzzle className="h-5.5 w-5.5 text-[#9CA3AF] shrink-0" />;
}

// ─── INTEGRATION SUMMARY DONUT CHART ──────────────────────────────────────────
function IntegrationSummaryDonut() {
  const radius = 70;
  const circumference = 2 * Math.PI * radius; // 439.82

  let accumulatedPercent = 0;
  const sectors = donutSummary.map((item) => {
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
          <span className="text-[1.4rem] font-bold text-[#111827]">24</span>
          <span className="text-[0.62rem] font-bold text-[#6B7280]">Total</span>
        </div>
      </div>
      <div className="mt-4 flex flex-col gap-1.5 w-full">
        {donutSummary.map((c) => (
          <div key={c.status} className="flex items-center justify-between text-[0.74rem] font-semibold">
            <div className="flex items-center gap-2 text-[#374151]">
              <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ backgroundColor: c.color }} />
              <span>{c.status}</span>
            </div>
            <div className="flex items-center gap-1.5 text-[#6B7280]">
              <span className="text-[#111827] font-bold">{c.count}</span>
              <span>({c.percentage}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── CATEGORY CARD ICON HELPER ────────────────────────────────────────────────
function CategoryIcon({ type }: { type: string }) {
  const c = "h-4.5 w-4.5 text-[#6B7280]";
  if (type === "messageSquare") return <MessageSquare className={c} />;
  if (type === "folder") return <Folder className={c} />;
  if (type === "clipboard") return <Clipboard className={c} />;
  if (type === "user") return <User className={c} />;
  if (type === "code") return <Code className={c} />;
  if (type === "calendar") return <Calendar className={c} />;
  if (type === "megaphone") return <Megaphone className={c} />;
  if (type === "dollarSign") return <DollarSign className={c} />;
  return <Puzzle className={c} />;
}

// ─── MAIN COMPONENT ───────────────────────────────────────────────────────────
export default function IntegrationCenter() {
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
              <h1 className="text-[1.5rem] font-extrabold tracking-tight text-[#111827]">Integration Center</h1>
              <p className="text-[0.82rem] font-medium text-[#6B7280] mt-0.5">
                Connect, manage, and monitor integrations with external apps and services.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.76rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                <Filter className="h-3.5 w-3.5 text-[#9CA3AF]" />
                <span>Filters</span>
              </button>
              <button className="flex items-center gap-1 rounded-[12px] bg-[#38B88A] hover:bg-[#2F9F77] px-3.5 py-2 text-[0.76rem] font-bold text-white transition-colors">
                <Plus className="h-3.5 w-3.5" />
                <span>Add Integration</span>
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
              {integrationKPIs.map((kpi) => (
                <KPICard key={kpi.title} item={kpi} />
              ))}
            </motion.div>

            {/* Row 2: All Integrations Table / Donut Summary & Activity */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Integrations Table */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-8 flex flex-col justify-between">
                <div>
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">All Integrations</p>
                    <div className="flex items-center gap-2">
                      <label className="relative flex h-8 w-44 items-center">
                        <Search className="pointer-events-none absolute left-2.5 h-3 w-3 text-[#9CA3AF]" />
                        <input type="search" placeholder="Search integrations..." className="h-full w-full rounded-[8px] border border-[#E8EDF3] pl-7.5 pr-2.5 text-[0.7rem] text-[#111827] outline-none placeholder:text-[#9CA3AF]" />
                      </label>
                      <button className="flex h-8 items-center gap-1.5 rounded-[8px] border border-[#E8EDF3] px-2.5 text-[0.7rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                        <span>All Status</span>
                        <ChevronDown className="h-3 w-3 text-[#9CA3AF]" />
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[0.74rem]">
                      <thead>
                        <tr className="border-b border-[#F1F5F9] pb-2 text-[0.66rem] font-bold text-[#9CA3AF] uppercase tracking-wider">
                          <th className="py-2">Integration</th>
                          <th className="py-2">Category</th>
                          <th className="py-2">Status</th>
                          <th className="py-2">Last Synced</th>
                          <th className="py-2">Usage (24h)</th>
                          <th className="py-2">Success Rate</th>
                          <th className="py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F1F5F9]">
                        {integrationsList.map((integration) => (
                          <tr key={integration.name} className="hover:bg-[#FAFCFB] transition-colors">
                            <td className="py-2.5 pr-2 min-w-[200px]">
                              <div className="flex items-start gap-2.5">
                                <div className="mt-0.5 flex h-7.5 w-7.5 shrink-0 items-center justify-center rounded-[8px] border border-[#F1F5F9] bg-[#F8FAF9]">
                                  <BrandLogo type={integration.logo} />
                                </div>
                                <div>
                                  <p className="font-bold text-[#111827]">{integration.name}</p>
                                  <p className="text-[0.66rem] text-[#9CA3AF] mt-0.5 leading-normal">{integration.description}</p>
                                </div>
                              </div>
                            </td>
                            <td className="py-2.5 text-[#374151] font-semibold">{integration.category}</td>
                            <td className="py-2.5">
                              <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.66rem] font-bold ring-1",
                                integration.status === "Connected" ? "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]" :
                                integration.status === "Warning" ? "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]" :
                                "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]"
                              )}>
                                <span className={cn("h-1.5 w-1.5 rounded-full",
                                  integration.status === "Connected" ? "bg-[#38B88A]" :
                                  integration.status === "Warning" ? "bg-[#F59E0B]" :
                                  "bg-[#EF4444]"
                                )} />
                                {integration.status}
                              </span>
                            </td>
                            <td className="py-2.5 text-[#6B7280] font-semibold">{integration.lastSynced}</td>
                            <td className="py-2.5">
                              <div className="flex items-center gap-2">
                                {/* Visual loading-bar style bar matching count proportion */}
                                <div className="hidden sm:block w-12 h-1 rounded-full bg-[#F1F5F9] overflow-hidden shrink-0">
                                  <div className="h-full bg-[#38B88A] rounded-full" style={{ width: `${(integration.usage / 1842) * 100}%` }} />
                                </div>
                                <span className="text-[#111827] font-bold">{integration.usage.toLocaleString()}</span>
                              </div>
                            </td>
                            <td className="py-2.5 text-[#374151] font-bold">{integration.successRate}</td>
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
                  <span>Showing 1 to 8 of 24 Integrations</span>
                  <div className="flex items-center gap-1.5">
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#9CA3AF] disabled:opacity-40" disabled>
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <button className="h-7 w-7 rounded-[6px] bg-[#38B88A] text-white flex items-center justify-center">1</button>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">2</button>
                    <button className="h-7 w-7 rounded-[6px] border border-[#E8EDF3] flex items-center justify-center hover:bg-[#F8FAFC] text-[#374151]">3</button>
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

              {/* Summary / Activity Column */}
              <div className="lg:col-span-4 space-y-5">
                {/* Integration Summary */}
                <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm">
                  <p className="text-[0.88rem] font-bold text-[#111827] mb-4">Integration Summary</p>
                  <IntegrationSummaryDonut />
                  <div className="border-t border-[#F1F5F9] pt-3 mt-4 text-center">
                    <button className="text-[0.74rem] font-bold text-[#38B88A] hover:text-[#2F9F77]">
                      View All Integrations
                    </button>
                  </div>
                </div>

                {/* Recent Activity */}
                <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-3.5">
                      <p className="text-[0.88rem] font-bold text-[#111827]">Recent Activity</p>
                      <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                        View All
                      </button>
                    </div>
                    <div className="space-y-3">
                      {recentActivityStream.map((act, i) => (
                        <div key={i} className="flex items-start justify-between gap-3 text-[0.74rem] font-semibold border-b border-[#F1F5F9] pb-2.5 last:border-b-0 last:pb-0">
                          <div className="min-w-0">
                            <p className="text-[#374151] font-bold leading-normal">{act.message}</p>
                            <p className="text-[0.64rem] text-[#9CA3AF] mt-0.5 font-medium">{act.time}</p>
                          </div>
                          <span className={cn("h-2.5 w-2.5 rounded-full shrink-0 mt-1",
                            act.status === "success" ? "bg-[#38B88A]" :
                            act.status === "warning" ? "bg-[#F59E0B]" :
                            "bg-[#EF4444]"
                          )} />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>

            {/* Row 3: Categories Grid & Popular integrations Connect deck */}
            <motion.div variants={variants.fadeUp} className="grid grid-cols-1 gap-5 lg:grid-cols-12">
              {/* Integration Categories */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-8 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Integration Categories</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {activeCategories.map((cat) => (
                      <div key={cat.name} className="rounded-[12px] border border-[#E8EDF3] bg-[#FAFCFB] p-3 flex flex-col justify-between hover:bg-[#F1FAF6] transition-colors cursor-pointer group">
                        <div className="flex h-8.5 w-8.5 items-center justify-center rounded-[10px] border border-[#E8EDF3] bg-white shadow-sm shrink-0">
                          <CategoryIcon type={cat.icon} />
                        </div>
                        <div className="mt-4 leading-tight">
                          <p className="text-[0.76rem] font-bold text-[#111827] group-hover:text-[#2F9F77] transition-colors">{cat.name}</p>
                          <p className="text-[0.62rem] text-[#9CA3AF] mt-0.5 font-bold">{cat.count}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Popular Integrations Connect deck */}
              <div className="rounded-[16px] border border-[#E8EDF3] bg-white p-4 shadow-sm lg:col-span-4 flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <p className="text-[0.88rem] font-bold text-[#111827]">Popular Integrations</p>
                    <button className="rounded-[8px] border border-[#E8EDF3] px-2 py-1 text-[0.66rem] font-semibold text-[#6B7280] hover:bg-[#F8FAFC]">
                      View All
                    </button>
                  </div>

                  <div className="grid grid-cols-5 gap-1 pt-2">
                    {popularIntegrationsList.map((pop) => (
                      <div key={pop.name} className="flex flex-col items-center text-center">
                        <div className="flex h-11 w-11 items-center justify-center rounded-[12px] border border-[#E8EDF3] bg-[#FAFCFB] shadow-sm mb-2 shrink-0">
                          <BrandLogo type={pop.logo} />
                        </div>
                        <span className="text-[0.66rem] font-bold text-[#6B7280] truncate max-w-[60px]">{pop.name}</span>
                        <button className="mt-2 text-[0.62rem] font-extrabold text-white bg-[#38B88A] hover:bg-[#2F9F77] rounded-full px-2.5 py-1 leading-none shadow-sm transition-colors">
                          Connect
                        </button>
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
