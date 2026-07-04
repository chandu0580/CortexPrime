"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, useRef } from "react";
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
  Filter,
  Globe,
  Home,
  Mic,
  Monitor,
  Phone,
  PhoneCall,
  PhoneIncoming,
  PhoneMissed,
  PhoneOff,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  Shield,
  ShieldCheck,
  Target,
  Zap,
  CheckCircle2,
  Headphones,
  Radio,
  Users,
  AlertCircle,
  Volume2,
  X,
  MoreVertical,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";

// ─── NAV ──────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home     },
  { href: "/runtime",       label: "Runtime",      icon: Zap      },
  { href: "/agents",        label: "Agents",       icon: Bot      },
  { href: "/missions",      label: "Missions",     icon: Target   },
  { href: "/voice",         label: "Voice",        icon: Mic      },
  { href: "/memory",        label: "Memory",       icon: Brain    },
  { href: "/workspace",     label: "Research",     icon: Search   },
  { href: "/operator",      label: "Computer Use", icon: Monitor  },
  { href: "/operator",      label: "Browser",      icon: Globe    },
  { href: "/replay",        label: "Replay",       icon: Archive  },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2 },
  { href: "/governance",    label: "Governance",   icon: Shield   },
  { href: "/system-status", label: "Monitoring",   icon: Activity },
  { href: "/integrations",  label: "Integrations", icon: Puzzle   },
  { href: "/settings",      label: "Settings",     icon: Settings },
];

// ─── Sidebar ──────────────────────────────────────────────────────────────────
function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside className={cn(
      "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#EAEFF5] bg-white transition-all duration-300",
      collapsed ? "w-[68px]" : "w-[220px]"
    )}>
      <div className={cn("flex items-center gap-2.5 px-4 py-5", collapsed && "justify-center px-0")}>
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-[12px] bg-[#38B88A]">
          <svg viewBox="0 0 48 48" className="h-5 w-5 text-white" fill="none">
            <path d="M24 4.5 39 13v22L24 43.5 9 35V13L24 4.5Z" stroke="currentColor" strokeWidth="3.5" strokeLinejoin="round"/>
            <path d="M24 13 31 17v14l-7 4-7-4V17l7-4Z" fill="currentColor" fillOpacity=".3" stroke="currentColor" strokeWidth="2.8" strokeLinejoin="round"/>
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
          const isActive = label === "Voice";
          return (
            <Link key={label} href={href} className={cn(
              "flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 transition-all",
              isActive ? "bg-[#ECFBF4] text-[#2F9F77]" : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]",
              collapsed && "justify-center px-0"
            )}>
              <Icon className="h-4 w-4 shrink-0"/>
              {!collapsed && <span className="text-[0.875rem] font-semibold">{label}</span>}
              {!collapsed && isActive && <div className="ml-auto h-1.5 w-1.5 rounded-full bg-[#38B88A]"/>}
            </Link>
          );
        })}
      </nav>
      <div className={cn("px-2 pb-4 space-y-2", collapsed && "px-1")}>
        {!collapsed && (
          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-2.5">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[#38B88A]"/>
              <div className="flex-1 min-w-0">
                <p className="text-[0.72rem] font-semibold text-[#2F9F77]">System Status</p>
                <p className="text-[0.7rem] font-bold text-[#38B88A]">Healthy</p>
                <p className="text-[0.66rem] text-[#9CA3AF]">All systems operational</p>
              </div>
              <RefreshCw className="h-3.5 w-3.5 text-[#D1D5DB] cursor-pointer hover:text-[#38B88A]"/>
            </div>
          </div>
        )}
        <button onClick={onCollapse} className={cn(
          "flex w-full items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.82rem] font-semibold text-[#6B7280] transition hover:bg-[#F8FAFC]",
          collapsed && "justify-center"
        )}>
          {collapsed ? <ChevronRight className="h-4 w-4"/> : <><ChevronLeft className="h-4 w-4"/><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}

// ─── Header ───────────────────────────────────────────────────────────────────
function Header({ collapsed }: { collapsed: boolean }) {
  const avatar = useMemo(() => `data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`
  )}`, []);
  return (
    <header className={cn(
      "sticky top-0 z-30 flex items-center gap-3 border-b border-[#EAEFF5] bg-white/96 px-5 py-3 backdrop-blur transition-all duration-300",
      collapsed ? "pl-[80px]" : "pl-[232px]"
    )}>
      <label className="relative flex h-10 w-[240px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#9CA3AF]"/>
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] pl-10 pr-14 text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"/>
        <span className="absolute right-3 rounded-[7px] border border-[#E5E7EB] bg-white px-1.5 py-0.5 text-[0.66rem] font-semibold text-[#9CA3AF]">⌘K</span>
      </label>
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 xl:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Target className="h-3.5 w-3.5"/></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-2">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.6rem] font-bold text-[#2F9F77]"><span className="h-1 w-1 rounded-full bg-[#38B88A]"/>Running</span>
          </div>
        </div>
        <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] ml-1"/>
      </div>
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 lg:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]"><Mic className="h-3.5 w-3.5"/></div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <div className="flex items-center gap-2">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Listening...</p>
            <div className="flex items-center gap-[2px] h-2.5">
              <span className="w-[2px] h-2 bg-[#38B88A]/80 rounded-full animate-pulse"/>
              <span className="w-[2px] h-3 bg-[#38B88A] rounded-full"/>
              <span className="w-[2px] h-1.5 bg-[#38B88A]/60 rounded-full"/>
              <span className="w-[2px] h-2.5 bg-[#38B88A] rounded-full animate-pulse"/>
            </div>
          </div>
        </div>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <button className="relative flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
          <Bell className="h-4 w-4"/>
          <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#EF4444] text-[0.68rem] font-bold text-white ring-2 ring-white">3</span>
        </button>
        <div className="flex items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-white p-1 pr-3 hover:bg-[#F8FAFC] cursor-pointer">
          <Image src={avatar} alt="Alex Morgan" width={32} height={32} className="rounded-[10px]"/>
          <div className="leading-tight text-left hidden sm:block">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.68rem] font-medium text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] hidden sm:block"/>
        </div>
      </div>
    </header>
  );
}

// ─── Animated Waveform ────────────────────────────────────────────────────────
function Waveform({ active, color = "#38B88A" }: { active?: boolean; color?: string }) {
  const bars = 28;
  return (
    <div className="flex items-center gap-[2px] h-8">
      {Array.from({ length: bars }).map((_, i) => {
        const height = active
          ? Math.random() * 24 + 6
          : Math.sin((i / bars) * Math.PI) * 16 + 6;
        return (
          <motion.div
            key={i}
            className="w-[3px] rounded-full"
            style={{ backgroundColor: color }}
            animate={active ? { height: [6, height, 6] } : { height }}
            transition={active ? { repeat: Infinity, duration: 0.4 + i * 0.03, ease: "easeInOut" } : { duration: 0 }}
          />
        );
      })}
    </div>
  );
}

// ─── Sparkline SVG ────────────────────────────────────────────────────────────
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const min = Math.min(...data), max = Math.max(...data), range = max - min || 1;
  const h = 28, w = 120;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 6) - 3}`);
  const path = `M ${pts.join(" L ")}`;
  const fill = `${path} L ${w},${h} L 0,${h} Z`;
  const id = `sg-${color.replace("#", "")}`;
  return (
    <div className="h-7 w-full mt-2">
      <svg className="w-full h-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.18}/>
            <stop offset="100%" stopColor={color} stopOpacity={0}/>
          </linearGradient>
        </defs>
        <path d={fill} fill={`url(#${id})`}/>
        <path d={path} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  );
}

// ─── KPI Cards data ───────────────────────────────────────────────────────────
const kpis = [
  { label: "Active Calls", value: "12", trend: "↑ 20%", sub: "vs last hour", icon: PhoneCall, color: "#38B88A", data: [6,7,8,9,10,11,12,11,12] },
  { label: "Active Listeners", value: "8", trend: "", sub: "vs last hour", icon: Headphones, color: "#38B88A", data: [4,5,6,5,7,8,7,8,8] },
  { label: "Total Calls Today", value: "246", trend: "↑ 16%", sub: "vs yesterday", icon: Phone, color: "#38B88A", data: [140,160,175,190,200,215,225,238,246] },
  { label: "Avg. Call Duration", value: "08:42", trend: "↑ 9%", sub: "vs yesterday", icon: Activity, color: "#38B88A", data: [6.2,6.8,7.1,7.5,7.9,8.1,8.3,8.5,8.7] },
  { label: "Success Rate", value: "98.6%", trend: "↑ 2.1%", sub: "vs yesterday", icon: CheckCircle2, color: "#38B88A", data: [94,95,96,96,97,97,98,98,98.6] },
  { label: "Tokens Used", value: "1.24M", trend: "↑ 12%", sub: "vs yesterday", icon: Zap, color: "#38B88A", data: [0.7,0.8,0.9,0.95,1.0,1.08,1.15,1.2,1.24] },
];

// ─── Live calls data ──────────────────────────────────────────────────────────
const liveCalls = [
  { name: "Sarah Johnson", phone: "+1 (555) 234-5678", duration: "00:07:34", status: "live", statusColor: "bg-[#38B88A]", waveColor: "#38B88A" },
  { name: "Enterprise Support", phone: "+1 (555) 987-6541", duration: "00:05:42", status: "live", statusColor: "bg-[#38B88A]", waveColor: "#38B88A" },
  { name: "Michael Brown", phone: "+1 (555) 456-7890", duration: "00:01:08", status: "live", statusColor: "bg-[#38B88A]", waveColor: "#38B88A" },
  { name: "Sales Inquiry", phone: "+1 (555) 321-0987", duration: "00:07:38", status: "live", statusColor: "bg-[#38B88A]", waveColor: "#38B88A" },
  { name: "Emily Davis", phone: "+1 (555) 654-3210", duration: "00:03:48", status: "ringing", statusColor: "bg-[#F59E0B]", waveColor: "#F59E0B" },
  { name: "Technical Support", phone: "+1 (555) 876-6432", duration: "00:01:21", status: "on hold", statusColor: "bg-[#EF4444]", waveColor: "#EF4444" },
];

// ─── Voice channels ───────────────────────────────────────────────────────────
const voiceChannels = [
  { name: "Customer Support Line", active: 4, badge: "+Live", badgeColor: "text-[#38B88A] bg-[#ECFBF4]", status: "live" },
  { name: "Sales Line", active: 3, badge: "+Live", badgeColor: "text-[#38B88A] bg-[#ECFBF4]", status: "live" },
  { name: "Technical Support", active: 2, badge: "+Live", badgeColor: "text-[#38B88A] bg-[#ECFBF4]", status: "live" },
  { name: "General Inquiries", active: 1, badge: "", badgeColor: "", status: "normal" },
  { name: "Emergency Line", active: 1, badge: "On Hold", badgeColor: "text-[#EF4444] bg-[#FEF2F2]", status: "hold" },
  { name: "Callback Queue", active: 12, badge: "Holding", badgeColor: "text-[#F59E0B] bg-[#FFFBEB]", status: "hold" },
];

// ─── Top Voice Agents ─────────────────────────────────────────────────────────
const topAgents = [
  { name: "Voice Agent 1", calls: 112, rate: "98.7%", duration: "08:12" },
  { name: "Voice Agent 2", calls: 98, rate: "97%", duration: "07:45" },
  { name: "Voice Agent 3", calls: 72, rate: "99.2%", duration: "09:18" },
  { name: "Voice Agent 4", calls: 54, rate: "96.2%", duration: "06:09" },
];

// ─── Call analytics ───────────────────────────────────────────────────────────
const callAnalytics = [
  { label: "Inbound", value: 150, pct: "61%", color: "#38B88A" },
  { label: "Outbound", value: 84, pct: "22%", color: "#3B82F6" },
  { label: "Internal", value: 24, pct: "10%", color: "#8B5CF6" },
  { label: "Missed", value: 12, pct: "5%", color: "#F59E0B" },
];

// ─── Call duration trend data ─────────────────────────────────────────────────
const durationTrend = [
  { time: "12 AM", val: 4 },
  { time: "4 AM", val: 2 },
  { time: "8 AM", val: 8 },
  { time: "12 PM", val: 18 },
  { time: "4 PM", val: 22 },
  { time: "8 PM", val: 14 },
];

// ─── Selected call details ────────────────────────────────────────────────────
const selectedCallDetails = {
  name: "Sarah Johnson",
  phone: "+1 (566) 123-4567",
  sentiment: "Positive",
  confidence: "92%",
  language: "English",
  interruptions: 2,
};

// ─── Main Component ───────────────────────────────────────────────────────────
export default function VoiceRuntime() {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedCall, setSelectedCall] = useState(liveCalls[0]);
  const [tick, setTick] = useState(0);

  // Animate waveform
  useEffect(() => {
    const interval = setInterval(() => setTick(t => t + 1), 500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed(v => !v)}/>
      <div className={cn("flex min-h-screen flex-col transition-all duration-300", collapsed ? "pl-[68px]" : "pl-[220px]")}>
        <Header collapsed={collapsed}/>
        <main className="flex-1 px-5 py-5 lg:px-6">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.02)} className="mx-auto max-w-[1500px] space-y-5">

            {/* Page title */}
            <motion.div variants={variants.fadeUp} className="flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-[1.8rem] font-bold tracking-[-0.03em] text-[#111827]">Voice Runtime</h1>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2.5 py-0.5 text-[0.73rem] font-semibold text-[#2F9F77] ring-1 ring-[#D6F0E5]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]"/>• Live
                  </span>
                </div>
                <p className="mt-1 text-[0.88rem] text-[#6B7280]">Real-time voice interactions, calls, and AI conversations.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2.5">
                <button className="flex items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-4 py-2.5 text-[0.86rem] font-semibold text-[#374151] hover:bg-[#F8FAFC]">
                  All Channels <ChevronDown className="h-4 w-4 text-[#9CA3AF]"/>
                </button>
                <button className="flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
                  <Filter className="h-4 w-4 text-[#6B7280]"/>
                </button>
                <button className="flex items-center gap-2 rounded-[14px] bg-[#38B88A] px-4 py-2.5 text-[0.86rem] font-semibold text-white shadow-[0_4px_12px_rgba(56,184,138,0.24)] hover:bg-[#2F9F77]">
                  <Plus className="h-4 w-4"/> Start Voice Session
                </button>
              </div>
            </motion.div>

            {/* KPI Cards */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6">
              {kpis.map(card => {
                const Icon = card.icon;
                return (
                  <div key={card.label} className="rounded-[20px] border border-[#EAEFF5] bg-white p-4 shadow-[0_2px_12px_rgba(148,163,184,0.04)]">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.76rem] font-semibold text-[#9CA3AF]">{card.label}</p>
                      <div className="flex h-7 w-7 items-center justify-center rounded-full border border-[#D6F0E5] bg-[#ECFBF4] text-[#38B88A]">
                        <Icon className="h-3.5 w-3.5"/>
                      </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-1.5">
                      <p className="text-[1.55rem] font-bold text-[#111827]">{card.value}</p>
                      {card.trend && <span className="text-[0.75rem] font-bold text-[#38B88A]">{card.trend}</span>}
                    </div>
                    <p className="text-[0.68rem] font-semibold text-[#9CA3AF]">{card.sub}</p>
                    <Sparkline data={card.data} color={card.color}/>
                  </div>
                );
              })}
            </motion.div>

            {/* Main 3-column grid */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-12">

              {/* Live Calls panel */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-3">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-[0.95rem] font-bold text-[#111827]">Live Calls</h2>
                </div>
                <div className="space-y-3">
                  {liveCalls.map((call, idx) => (
                    <div
                      key={idx}
                      onClick={() => setSelectedCall(call)}
                      className={cn(
                        "flex items-center gap-3 rounded-[12px] p-2.5 cursor-pointer transition-all",
                        selectedCall.name === call.name ? "bg-[#ECFBF4]/40 ring-1 ring-[#38B88A]/20" : "hover:bg-[#F8FAFC]"
                      )}
                    >
                      {/* Avatar */}
                      <div className="h-8 w-8 rounded-full bg-[#ECFBF4] flex items-center justify-center text-[0.66rem] font-bold text-[#38B88A] shrink-0">
                        {call.name.split(" ").map(n => n[0]).join("").slice(0, 2)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[0.8rem] font-bold text-[#111827] truncate">{call.name}</p>
                        <p className="text-[0.68rem] text-[#9CA3AF]">{call.phone}</p>
                      </div>
                      <div className="flex flex-col items-end gap-1 shrink-0">
                        <span className="text-[0.68rem] font-mono font-semibold text-[#374151]">{call.duration}</span>
                        <span className={cn(
                          "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[0.6rem] font-bold",
                          call.status === "live" ? "bg-[#ECFBF4] text-[#2F9F77]" :
                          call.status === "ringing" ? "bg-[#FFFBEB] text-[#B45309]" : "bg-[#FEF2F2] text-[#B91C1C]"
                        )}>
                          <span className={cn("h-1 w-1 rounded-full", call.statusColor)}/>
                          {call.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="mt-4 w-full rounded-[12px] border border-[#EAEFF5] py-2.5 text-[0.78rem] font-bold text-[#38B88A] hover:bg-[#F8FAFC]">
                  View All Calls
                </button>
              </div>

              {/* Voice Activity panel */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-5">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-[0.95rem] font-bold text-[#111827]">Voice Activity</h2>
                </div>

                {/* Waveform visualization */}
                <div className="rounded-[16px] border border-[#EAEFF5] bg-[#F8FAFC] p-4 mb-4">
                  <Waveform active color="#38B88A"/>
                </div>

                {/* Selected call details */}
                <div className="rounded-[16px] border border-[#EAEFF5] bg-[#F8FAFC] p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-full bg-[#ECFBF4] flex items-center justify-center text-[0.8rem] font-bold text-[#38B88A]">
                        {selectedCallDetails.name.split(" ").map(n => n[0]).join("")}
                      </div>
                      <div>
                        <p className="text-[0.85rem] font-bold text-[#111827]">{selectedCallDetails.name}</p>
                        <p className="text-[0.72rem] text-[#9CA3AF]">{selectedCallDetails.phone}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[0.68rem] font-bold text-[#2F9F77]">
                        <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A] animate-pulse"/>• Live
                      </span>
                      <button className="flex items-center gap-1.5 rounded-[10px] bg-[#EF4444] px-2.5 py-1.5 text-[0.72rem] font-bold text-white">
                        <PhoneOff className="h-3 w-3"/> End Call
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3 text-[0.74rem]">
                    <div>
                      <p className="text-[#9CA3AF] font-semibold">Sentiment</p>
                      <p className="font-bold text-[#38B88A] mt-0.5">{selectedCallDetails.sentiment}</p>
                    </div>
                    <div>
                      <p className="text-[#9CA3AF] font-semibold">Confidence</p>
                      <p className="font-bold text-[#111827] mt-0.5">{selectedCallDetails.confidence}</p>
                    </div>
                    <div>
                      <p className="text-[#9CA3AF] font-semibold">Language</p>
                      <p className="font-bold text-[#111827] mt-0.5">{selectedCallDetails.language}</p>
                    </div>
                    <div>
                      <p className="text-[#9CA3AF] font-semibold">Interruptions</p>
                      <p className="font-bold text-[#111827] mt-0.5">{selectedCallDetails.interruptions}</p>
                    </div>
                  </div>

                  {/* Action icons */}
                  <div className="mt-4 flex items-center gap-3">
                    {[
                      { label: "Mute", icon: Mic },
                      { label: "Voice", icon: Volume2 },
                      { label: "Transfer", icon: Phone },
                      { label: "Keypad", icon: Settings },
                      { label: "More", icon: MoreVertical },
                    ].map(({ label, icon: Icon }) => (
                      <button key={label} className="flex flex-col items-center gap-1 text-[0.64rem] font-semibold text-[#9CA3AF] hover:text-[#111827]">
                        <div className="h-7 w-7 rounded-[8px] border border-[#EAEFF5] bg-white flex items-center justify-center">
                          <Icon className="h-3.5 w-3.5"/>
                        </div>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Voice Channels panel */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-[0.95rem] font-bold text-[#111827]">Voice Channels</h2>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[0.7rem] font-bold text-[#2F9F77]">
                    6 Active
                  </span>
                </div>
                <div className="space-y-3">
                  {voiceChannels.map((ch, idx) => (
                    <div key={idx} className="flex items-center justify-between rounded-[12px] border border-[#F1F5F9] bg-[#F8FAFC] p-3">
                      <div className="flex items-center gap-3">
                        <div className={cn(
                          "flex h-8 w-8 items-center justify-center rounded-[10px]",
                          ch.status === "hold" ? "bg-[#FEF2F2] text-[#EF4444]" : "bg-[#ECFBF4] text-[#38B88A]"
                        )}>
                          <Headphones className="h-4 w-4"/>
                        </div>
                        <div>
                          <p className="text-[0.8rem] font-bold text-[#111827]">{ch.name}</p>
                          <p className="text-[0.7rem] text-[#9CA3AF]">{ch.active} active call{ch.active > 1 ? "s" : ""}</p>
                        </div>
                      </div>
                      {ch.badge && (
                        <span className={cn("rounded-full px-2 py-0.5 text-[0.68rem] font-bold", ch.badgeColor)}>
                          {ch.badge}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                <button className="mt-4 w-full rounded-[12px] border border-[#EAEFF5] py-2.5 text-[0.78rem] font-bold text-[#374151] hover:bg-[#F8FAFC]">
                  Manage Channels
                </button>
              </div>

            </motion.div>

            {/* Bottom row: Call Analytics + Duration Trend + Top Voice Agents */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-12">

              {/* Call Analytics Donut */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-3">
                <h2 className="text-[0.95rem] font-bold text-[#111827] mb-4">Call Analytics (Today)</h2>
                <div className="flex flex-col items-center gap-5">
                  {/* Custom SVG donut */}
                  <div className="relative flex items-center justify-center h-32 w-32">
                    <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                      {(() => {
                        const total = callAnalytics.reduce((s, c) => s + c.value, 0);
                        const slices = callAnalytics;
                        let acc = 0;
                        return slices.map((s, i) => {
                          const len = (s.value / total) * 251.2;
                          const offset = acc;
                          acc += s.value;
                          return (
                            <circle key={i} cx="50" cy="50" r="40" stroke={s.color} strokeWidth="9" fill="transparent"
                              strokeDasharray={`${len} ${251.2 - len}`}
                              transform={`rotate(${(offset / total) * 360} 50 50)`}
                            />
                          );
                        });
                      })()}
                    </svg>
                    <div className="absolute flex flex-col items-center">
                      <span className="text-[1.5rem] font-bold text-[#111827]">246</span>
                      <span className="text-[0.66rem] font-bold text-[#9CA3AF]">Total Calls</span>
                    </div>
                  </div>
                  {/* Legend */}
                  <div className="w-full space-y-2">
                    {callAnalytics.map(c => (
                      <div key={c.label} className="flex items-center justify-between text-[0.76rem]">
                        <span className="flex items-center gap-2 font-semibold text-[#6B7280]">
                          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: c.color }}/>
                          {c.label}
                        </span>
                        <span className="font-bold text-[#111827]">{c.value} ({c.pct})</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Call Duration Trend */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-5">
                <h2 className="text-[0.95rem] font-bold text-[#111827] mb-4">Call Duration Trend</h2>
                <div className="relative h-40">
                  {/* Y-axis labels */}
                  <div className="absolute left-0 inset-y-0 flex flex-col justify-between text-[0.62rem] font-semibold text-[#9CA3AF] pb-5">
                    {["30m", "20m", "10m", "0m"].map(v => <span key={v}>{v}</span>)}
                  </div>
                  {/* Chart area */}
                  <div className="absolute left-6 right-0 inset-y-0 pb-5">
                    <svg className="w-full h-full" viewBox="0 0 400 120" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="dur-grad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#38B88A" stopOpacity={0.2}/>
                          <stop offset="100%" stopColor="#38B88A" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      {(() => {
                        const pts = durationTrend.map((d, i) => {
                          const x = (i / (durationTrend.length - 1)) * 380 + 10;
                          const y = 110 - (d.val / 25) * 100;
                          return `${x},${y}`;
                        });
                        const linePath = `M ${pts.join(" L ")}`;
                        const fillPath = `${linePath} L 390,110 L 10,110 Z`;
                        return (
                          <>
                            {/* Grid lines */}
                            {[0, 40, 80, 120].map(y => (
                              <line key={y} x1="0" y1={y} x2="400" y2={y} stroke="#EAEFF5" strokeWidth="1" strokeDasharray="4 4"/>
                            ))}
                            <path d={fillPath} fill="url(#dur-grad)"/>
                            <path d={linePath} fill="none" stroke="#38B88A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            {durationTrend.map((d, i) => {
                              const x = (i / (durationTrend.length - 1)) * 380 + 10;
                              const y = 110 - (d.val / 25) * 100;
                              return <circle key={i} cx={x} cy={y} r="4" fill="#38B88A" stroke="white" strokeWidth="2"/>;
                            })}
                          </>
                        );
                      })()}
                    </svg>
                    {/* X-axis labels */}
                    <div className="flex justify-between text-[0.62rem] font-semibold text-[#9CA3AF]">
                      {durationTrend.map(d => <span key={d.time}>{d.time}</span>)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Top Voice Agents */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-[0.95rem] font-bold text-[#111827]">Top Voice Agents</h2>
                  <span className="text-[0.72rem] font-bold text-[#38B88A] cursor-pointer hover:underline">View All</span>
                </div>
                <table className="w-full text-[0.76rem]">
                  <thead>
                    <tr className="text-[0.68rem] font-bold uppercase text-[#9CA3AF]">
                      <th className="text-left py-1.5">Agent</th>
                      <th className="text-right py-1.5">Calls Handled</th>
                      <th className="text-right py-1.5">Success Rate</th>
                      <th className="text-right py-1.5">Avg. Duration</th>
                    </tr>
                  </thead>
                  <tbody className="space-y-2">
                    {topAgents.map((a, idx) => (
                      <tr key={idx} className="border-t border-[#F1F5F9]">
                        <td className="py-2.5">
                          <div className="flex items-center gap-2">
                            <div className="h-7 w-7 rounded-full bg-[#ECFBF4] flex items-center justify-center text-[0.62rem] font-bold text-[#38B88A]">
                              {a.name.split(" ").map(n => n[0]).join("")}
                            </div>
                            <span className="font-semibold text-[#111827]">{a.name}</span>
                          </div>
                        </td>
                        <td className="py-2.5 text-right font-bold text-[#111827]">{a.calls}</td>
                        <td className="py-2.5 text-right font-bold text-[#38B88A]">{a.rate}</td>
                        <td className="py-2.5 text-right font-bold text-[#111827]">{a.duration}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

            </motion.div>

            {/* Footer */}
            <motion.footer variants={variants.fadeUp} className="flex flex-col gap-2 border-t border-[#EAEFF5] pt-5 pb-2 text-[0.78rem] text-[#9CA3AF] md:flex-row md:items-center md:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]"/>
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
