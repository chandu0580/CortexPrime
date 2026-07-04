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
  Clock,
  Download,
  Edit3,
  FileText,
  Filter,
  Globe,
  Home,
  ListRestart,
  Mic,
  Monitor,
  MoreVertical,
  Pause,
  Play,
  Plus,
  Puzzle,
  RefreshCw,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  Target,
  Tag,
  Maximize2,
  X,
  Zap,
  Calendar,
  BarChart3,
  Sparkles,
  CheckCircle2,
  Database,
  PlayCircle,
  BookOpen,
  LayoutDashboard,
  Scale,
  Rocket,
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import {
  metrics,
  sessions,
  replayTimeline,
  type ReplayTone,
  type ReplaySession,
} from "@/components/replay-center/data";

// ─── Tone helpers ─────────────────────────────────────────────────────────────
const toneStyles: Record<ReplayTone, string> = {
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  running:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  failed:    "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  warning:   "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  info:      "bg-[#EFF6FF] text-[#2563EB] ring-[#DBEAFE]",
  queued:    "bg-[#FFF7ED] text-[#C2410C] ring-[#FED7AA]",
};

const toneDot: Record<ReplayTone, string> = {
  completed: "bg-[#38B88A]",
  running:   "bg-[#38B88A]",
  failed:    "bg-[#EF4444]",
  warning:   "bg-[#F59E0B]",
  info:      "bg-[#3B82F6]",
  queued:    "bg-[#F97316]",
};

const toneText: Record<ReplayTone, string> = {
  completed: "Completed",
  running:   "Running",
  failed:    "Failed",
  warning:   "Warning",
  info:      "Info",
  queued:    "Queued",
};

function Badge({ tone, label }: { tone: ReplayTone; label?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.72rem] font-semibold ring-1", toneStyles[tone])}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone])} />
      {label ?? toneText[tone]}
    </span>
  );
}

// ─── NAV ─────────────────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",       label: "Dashboard",    icon: Home         },
  { href: "/runtime",       label: "Runtime",      icon: Zap          },
  { href: "/agents",        label: "Agents",       icon: Bot          },
  { href: "/missions",      label: "Missions",     icon: Target       },
  { href: "/voice",         label: "Voice",        icon: Mic          },
  { href: "/memory",        label: "Memory",       icon: Brain        },
  { href: "/workspace",     label: "Research",     icon: Search       },
  { href: "/operator",      label: "Computer Use", icon: Monitor      },
  { href: "/browser",       label: "Browser",      icon: Globe        },
  { href: "/replay",        label: "Replay",       icon: ListRestart  },
  { href: "/enterprise-replay", label: "Enterprise Replay", icon: ListRestart  },
  { href: "/developer-portal", label: "Developer Portal", icon: BookOpen },
  { href: "/operations-center", label: "Ops Center", icon: LayoutDashboard },
  { href: "/scale-reliability", label: "Scale & Reliability", icon: Scale },
  { href: "/pilot-readiness", label: "Pilot Readiness", icon: Rocket },
  { href: "/analytics",     label: "Analytics",    icon: BarChart2    },
  { href: "/governance",    label: "Governance",   icon: ShieldCheck  },
  { href: "/system-status", label: "Monitoring",   icon: Activity     },
  { href: "/integrations",  label: "Integrations", icon: Puzzle       },
  { href: "/settings",      label: "Settings",     icon: Settings     },
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
          const active = label === "Replay";
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
      {/* Hamburger / filter icon on left */}
      <button className="flex h-9 w-9 items-center justify-center rounded-[10px] border border-[#E8EDF3] text-[#6B7280] hover:bg-[#F5F7FA]">
        <Filter className="h-4 w-4" />
      </button>

      <label className="relative flex h-9 w-[200px] items-center">
        <Search className="pointer-events-none absolute left-3 h-3.5 w-3.5 text-[#9CA3AF]" />
        <input type="search" placeholder="Search anything..." className="h-full w-full rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-12 text-[0.8rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3]" />
        <span className="absolute right-2.5 rounded-[6px] border border-[#E5E7EB] bg-white px-1 py-0.5 text-[0.6rem] font-semibold text-[#9CA3AF]">⌘ K</span>
      </label>

      <div className="hidden items-center gap-2 rounded-[12px] border border-[#E8EDF3] bg-[#F5F7FA] px-3 py-1.5 xl:flex">
        <div className="flex h-6 w-6 items-center justify-center rounded-[8px] bg-[#ECFBF4] text-[#38B88A]"><ShieldCheck className="h-3 w-3" /></div>
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
  const W = 100, H = 36;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * W},${H - ((v - min) / range) * (H - 6) - 3}`);
  const linePath = `M ${pts.join(" L ")}`;
  const fillPath = `${linePath} L ${W},${H} L 0,${H} Z`;
  const uid = useMemo(() => Math.random().toString(36).slice(2, 7), []);
  return (
    <div className="h-9 w-full mt-2">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" preserveAspectRatio="none">
        <defs>
          <linearGradient id={uid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.15} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={fillPath} fill={`url(#${uid})`} />
        <path d={linePath} fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ─── SESSION DETAIL PANEL (right side) ────────────────────────────────────────
function SessionDetailPanel({ session, onClose }: { session: ReplaySession; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<"replay" | "summary" | "actions" | "logs" | "artifacts">("replay");
  const [playing, setPlaying] = useState(false);

  const tabs = [
    { key: "replay",    label: "Replay" },
    { key: "summary",   label: "Summary" },
    { key: "actions",   label: "Actions (1,248)" },
    { key: "logs",      label: "Logs" },
    { key: "artifacts", label: "Artifacts (12)" },
  ] as const;

  return (
    <div className="flex flex-col rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      {/* Panel Header */}
      <div className="flex items-start justify-between border-b border-[#E8EDF3] px-5 py-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h2 className="text-[1rem] font-bold text-[#111827]">Session {session.id}</h2>
            <Badge tone={session.status} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[0.74rem] text-[#6B7280] font-medium">
            <span>{session.subtitle}</span>
            <span className="h-3 w-px bg-[#E8EDF3]" />
            <span className="flex items-center gap-1"><Bot className="h-3 w-3 text-[#9CA3AF]" />{session.agent}</span>
          </div>
        </div>
        <button onClick={onClose} className="flex h-7 w-7 items-center justify-center rounded-[8px] text-[#9CA3AF] hover:bg-[#F5F7FA] hover:text-[#374151]">
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Meta row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-b border-[#E8EDF3] px-5 py-2.5 text-[0.72rem] text-[#6B7280] font-medium">
        <span className="flex items-center gap-1.5"><Calendar className="h-3 w-3 text-[#9CA3AF]" />May 12, 2024</span>
        <span className="flex items-center gap-1.5"><Clock className="h-3 w-3 text-[#9CA3AF]" />10:30 AM</span>
        <span className="flex items-center gap-1.5"><RotateCcw className="h-3 w-3 text-[#9CA3AF]" />24m 18s</span>
        <span className="flex items-center gap-1.5"><BarChart3 className="h-3 w-3 text-[#9CA3AF]" />1,248 Actions</span>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-0.5 border-b border-[#E8EDF3] px-5">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "py-2.5 px-3 text-[0.77rem] font-semibold transition-colors border-b-2",
              activeTab === tab.key
                ? "border-[#38B88A] text-[#2F9F77]"
                : "border-transparent text-[#6B7280] hover:text-[#374151]"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Replay tab content */}
      <div className="flex-1 p-4 space-y-4">
        {/* Fake browser preview */}
        <div className="overflow-hidden rounded-[12px] border border-[#E8EDF3] bg-white">
          {/* Browser chrome */}
          <div className="flex items-center gap-2 border-b border-[#E8EDF3] bg-[#F8FAFC] px-3 py-2">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-[#EF4444]" />
              <span className="h-2 w-2 rounded-full bg-[#F59E0B]" />
              <span className="h-2 w-2 rounded-full bg-[#38B88A]" />
            </div>
            <div className="flex-1 rounded-[6px] border border-[#E8EDF3] bg-white px-3 py-1 text-[0.72rem] text-[#6B7280]">
              https://www.bloomberg.com/markets
            </div>
            <div className="flex items-center gap-1.5">
              <button className="flex h-6 w-6 items-center justify-center rounded text-[#9CA3AF] hover:bg-[#E8EDF3]">
                <RotateCcw className="h-3 w-3" />
              </button>
              <button className="flex h-6 w-6 items-center justify-center rounded text-[#9CA3AF] hover:bg-[#E8EDF3]">
                <Maximize2 className="h-3 w-3" />
              </button>
            </div>
          </div>

          {/* "Browser" fake content */}
          <div className="bg-white p-4">
            {/* Bloomberg header */}
            <div className="mb-3 flex items-center gap-3">
              <div>
                <p className="text-[0.6rem] font-bold uppercase tracking-wider text-[#6B7280]">Bloomberg</p>
                <p className="text-[0.82rem] font-bold text-[#111827]">Markets Today</p>
              </div>
              <div className="ml-auto flex flex-col gap-1.5">
                {[
                  { name: "S&P 500 Real", val: "5,221.42", change: "+1.02%", pos: true },
                  { name: "NASDAQ", val: "16,340.87", change: "+1.25%", pos: true },
                  { name: "DOW 30", val: "39,872.99", change: "+0.81%", pos: true },
                ].map((ticker) => (
                  <div key={ticker.name} className="flex items-center gap-2">
                    <p className="text-[0.62rem] font-semibold text-[#6B7280] w-24">{ticker.name}</p>
                    <p className="text-[0.68rem] font-bold text-[#111827]">{ticker.val}</p>
                    <p className={cn("text-[0.62rem] font-bold", ticker.pos ? "text-[#38B88A]" : "text-[#EF4444]")}>{ticker.change}</p>
                  </div>
                ))}
              </div>
            </div>
            {/* Fake line chart */}
            <div className="h-12 w-full">
              <svg viewBox="0 0 300 48" className="h-full w-full" preserveAspectRatio="none">
                <defs>
                  <linearGradient id="bloomberg-grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#38B88A" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#38B88A" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <path d="M 0,38 L 30,32 L 60,36 L 90,28 L 120,22 L 150,25 L 180,18 L 210,14 L 240,8 L 270,12 L 300,6 L 300,48 L 0,48 Z" fill="url(#bloomberg-grad)" />
                <path d="M 0,38 L 30,32 L 60,36 L 90,28 L 120,22 L 150,25 L 180,18 L 210,14 L 240,8 L 270,12 L 300,6" fill="none" stroke="#38B88A" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
          </div>

          {/* Video Controls */}
          <div className="flex items-center gap-3 border-t border-[#E8EDF3] bg-[#F8FAFC] px-4 py-2.5">
            <button
              onClick={() => setPlaying(!playing)}
              className="flex h-7 w-7 items-center justify-center rounded-full bg-[#38B88A] text-white hover:bg-[#2F9F77]"
            >
              {playing ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
            </button>
            <span className="text-[0.7rem] font-semibold text-[#6B7280]">08:42 / 24:18</span>
            <div className="flex-1 relative h-1.5 overflow-hidden rounded-full bg-[#E8EDF3]">
              <div className="h-full rounded-full bg-[#38B88A]" style={{ width: "35%" }} />
            </div>
            <button className="text-[0.7rem] font-semibold text-[#6B7280] hover:text-[#374151]">1.0x</button>
            <button className="flex h-6 w-6 items-center justify-center text-[#9CA3AF] hover:text-[#374151]">
              <Maximize2 className="h-3 w-3" />
            </button>
          </div>
        </div>

        {/* Session Notes */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-[0.84rem] font-bold text-[#111827]">Session Notes</h3>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className="text-[0.74rem] font-semibold text-[#6B7280]">Tags</span>
                <div className="flex items-center gap-1">
                  {["Market Research", "Q2 2024", "Trends"].map((tag) => (
                    <span key={tag} className="rounded-full bg-[#F3F4F6] px-2 py-0.5 text-[0.66rem] font-semibold text-[#6B7280]">{tag}</span>
                  ))}
                </div>
              </div>
              <button className="flex items-center gap-1 text-[0.72rem] font-semibold text-[#38B88A] hover:underline">
                <Edit3 className="h-3 w-3" /> Edit
              </button>
            </div>
          </div>
          <p className="text-[0.8rem] leading-relaxed text-[#6B7280]">
            Researched Q2 market trends, analyzed competitor data, and generated key insights for market intelligence report.
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── SESSIONS TABLE ───────────────────────────────────────────────────────────
function SessionsTable({
  onSelectSession,
  selectedId,
}: {
  onSelectSession: (session: ReplaySession) => void;
  selectedId: string | null;
}) {
  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#E8EDF3] px-5 py-3.5">
        <h2 className="text-[0.95rem] font-bold text-[#111827]">Sessions</h2>
        <div className="relative h-8 w-[180px]">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
          <input placeholder="Search sessions..." className="h-full w-full rounded-[10px] border border-[#E8EDF3] bg-[#F5F7FA] pl-9 pr-3 text-[0.75rem] text-[#111827] outline-none placeholder:text-[#9CA3AF]" />
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] text-left border-collapse">
          <thead>
            <tr className="border-b border-[#E8EDF3] text-[0.72rem] font-semibold text-[#9CA3AF]">
              <th className="px-5 py-3">Session</th>
              <th className="px-4 py-3">Mission</th>
              <th className="px-4 py-3">Agent</th>
              <th className="px-4 py-3">Started At</th>
              <th className="px-4 py-3">Duration</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-5 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((session) => (
              <tr
                key={session.id}
                onClick={() => onSelectSession(session)}
                className={cn(
                  "cursor-pointer border-b border-[#E8EDF3] last:border-0 transition-colors",
                  selectedId === session.id ? "bg-[#F0FBF6]" : "hover:bg-[#F9FAFB]"
                )}
              >
                <td className="px-5 py-3">
                  <div className="flex items-center gap-2.5">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white text-[0.7rem] font-bold" style={{ backgroundColor: session.accent }}>
                      {session.id.replace("#", "").slice(-2)}
                    </span>
                    <div>
                      <p className="text-[0.82rem] font-bold text-[#111827]">Session {session.id}</p>
                      <p className="text-[0.66rem] text-[#9CA3AF]">{session.subtitle}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 text-[0.8rem] text-[#6B7280] font-medium">{session.mission}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1.5 text-[0.8rem] font-semibold text-[#374151]">
                    <span className="flex h-5 w-5 items-center justify-center rounded-[6px] bg-[#F5F3FF] text-[#7C3AED]">
                      <Bot className="h-3 w-3" />
                    </span>
                    {session.agent}
                  </div>
                </td>
                <td className="px-4 py-3 text-[0.78rem] text-[#6B7280] font-medium whitespace-nowrap">{session.startedAt}</td>
                <td className="px-4 py-3 text-[0.8rem] text-[#374151] font-bold">{session.duration}</td>
                <td className="px-4 py-3"><Badge tone={session.status} /></td>
                <td className="px-5 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[0.8rem] font-bold text-[#374151]">{session.actions}</span>
                    <button className="flex h-6 w-6 items-center justify-center rounded-[6px] text-[#9CA3AF] hover:bg-[#F5F7FA] hover:text-[#374151]">
                      <MoreVertical className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="flex flex-col gap-3 border-t border-[#E8EDF3] px-5 py-3 sm:flex-row sm:items-center sm:justify-between text-[0.75rem] text-[#6B7280] font-semibold">
        <p>Showing 1 to 8 of 248 sessions</p>
        <div className="flex items-center gap-1">
          <button className="flex h-7 w-7 items-center justify-center rounded-[6px] border border-[#E8EDF3] hover:bg-[#F5F7FA]"><ChevronLeft className="h-3.5 w-3.5" /></button>
          {[1, 2, 3, 4, 5].map((p) => (
            <button key={p} className={cn(
              "flex h-7 w-7 items-center justify-center rounded-[6px] border text-[0.75rem]",
              p === 1 ? "border-[#38B88A] bg-[#ECFBF4] text-[#2F9F77]" : "border-[#E8EDF3] hover:bg-[#F5F7FA]"
            )}>{p}</button>
          ))}
          <span className="px-1 text-[#9CA3AF]">...</span>
          <button className="flex h-7 w-7 items-center justify-center rounded-[6px] border border-[#E8EDF3] hover:bg-[#F5F7FA]">31</button>
          <button className="flex h-7 w-7 items-center justify-center rounded-[6px] border border-[#E8EDF3] hover:bg-[#F5F7FA]"><ChevronRight className="h-3.5 w-3.5" /></button>
          <button className="ml-1 rounded-[6px] border border-[#E8EDF3] px-2.5 py-1 hover:bg-[#F5F7FA]">10 / page <ChevronDown className="h-3 w-3 inline" /></button>
        </div>
      </div>
    </div>
  );
}

// ─── SESSION TIMELINE ─────────────────────────────────────────────────────────
function SessionTimeline() {
  return (
    <div className="rounded-[18px] border border-[#E8EDF3] bg-white p-5 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
      <h2 className="mb-4 text-[0.95rem] font-bold text-[#111827]">Session Timeline</h2>
      <div className="relative">
        {/* Timestamps row */}
        <div className="mb-4 flex justify-between pl-2 pr-2 text-[0.64rem] font-semibold text-[#9CA3AF]">
          {replayTimeline.map((step) => (
            <span key={step.time} className="text-center w-[12.5%]">{step.time}</span>
          ))}
        </div>

        {/* Horizontal line + circles */}
        <div className="relative flex items-center justify-between mb-4">
          {/* Line behind the circles */}
          <div className="absolute left-0 right-0 top-1/2 h-0.5 -translate-y-1/2 bg-[#38B88A]" />

          {replayTimeline.map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={i} className="relative z-10 flex flex-col items-center" style={{ width: "12.5%" }}>
                <div className="flex h-8 w-8 items-center justify-center rounded-full border-2 border-[#38B88A] bg-white shadow-sm">
                  <Icon className="h-3.5 w-3.5 text-[#38B88A]" />
                </div>
              </div>
            );
          })}
        </div>

        {/* Step labels row */}
        <div className="flex justify-between px-0">
          {replayTimeline.map((step, i) => (
            <div key={i} className="flex flex-col items-center text-center" style={{ width: "12.5%" }}>
              <p className="text-[0.68rem] font-bold text-[#374151] leading-tight">{step.title}</p>
              <p className="mt-0.5 text-[0.6rem] text-[#9CA3AF] leading-tight px-0.5">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── MAIN REPLAY CENTER ───────────────────────────────────────────────────────
export default function ReplayCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? 60 : 152;
  const [selectedSession, setSelectedSession] = useState<ReplaySession | null>(sessions[0]);

  return (
    <div className="min-h-screen bg-[#F4F7FA]">
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />
      <TopBar sidebarWidth={sidebarWidth} />

      <div className="flex min-h-screen flex-col pt-[57px] transition-all duration-300" style={{ paddingLeft: sidebarWidth }}>
        <main className="flex-1 px-5 py-5">
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="mx-auto max-w-[1500px] space-y-5">

            {/* ── Page Header ────────────────────────────────────────────── */}
            <motion.div variants={variants.fadeUp} className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-[1.6rem] font-bold tracking-[-0.02em] text-[#111827]">Replay Center</h1>
                <p className="mt-0.5 text-[0.82rem] text-[#6B7280]">Review, analyze, and learn from past agent sessions and actions.</p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <button className="flex items-center gap-1.5 rounded-[12px] border border-[#E8EDF3] bg-white px-3.5 py-2 text-[0.8rem] font-semibold text-[#374151] hover:bg-[#F5F7FA]">
                  <Filter className="h-3.5 w-3.5 text-[#6B7280]" /> Filter
                </button>
                <button className="flex items-center gap-1.5 rounded-[12px] bg-[#38B88A] px-3.5 py-2 text-[0.8rem] font-semibold text-white shadow-[0_3px_10px_rgba(56,184,138,0.25)] hover:bg-[#2F9F77]">
                  <Plus className="h-3.5 w-3.5" /> Export
                </button>
              </div>
            </motion.div>

            {/* ── 5 KPI Cards ────────────────────────────────────────────── */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {metrics.map((m) => {
                const Icon = m.icon;
                const isError = m.tone === "failed";
                const chartColor = isError ? "#EF4444" : "#38B88A";
                const trendColor = isError ? "text-[#EF4444]" : "text-[#38B88A]";
                const iconBg = isError
                  ? "bg-[#FEF2F2] text-[#EF4444] border-[#FBD5D5]"
                  : "bg-[#ECFBF4] text-[#38B88A] border-[#D6F0E5]";
                return (
                  <div key={m.label} className="rounded-[18px] border border-[#E8EDF3] bg-white p-4 shadow-[0_1px_8px_rgba(148,163,184,0.06)]">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-[0.71rem] font-semibold text-[#9CA3AF]">{m.label}</p>
                      <div className={cn("flex h-7 w-7 items-center justify-center rounded-[9px] border", iconBg)}>
                        <Icon className="h-3.5 w-3.5" />
                      </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                      <span className="text-[1.4rem] font-bold tracking-tight text-[#111827]">{m.value}</span>
                      <span className={cn("text-[0.7rem] font-bold", trendColor)}>{m.trend}</span>
                    </div>
                    <p className="text-[0.64rem] text-[#9CA3AF] font-medium">vs last 7 days</p>
                    <Sparkline data={m.data} color={chartColor} />
                  </div>
                );
              })}
            </motion.div>

            {/* ── Middle: Sessions Table + Detail Panel ─────────────────── */}
            <motion.div variants={stagger(0.04)} className={cn(
              "grid gap-5",
              selectedSession ? "lg:grid-cols-[minmax(0,1fr)_420px]" : "lg:grid-cols-1"
            )}>
              <SessionsTable onSelectSession={setSelectedSession} selectedId={selectedSession?.id ?? null} />
              {selectedSession && (
                <SessionDetailPanel session={selectedSession} onClose={() => setSelectedSession(null)} />
              )}
            </motion.div>

            {/* ── Session Timeline ────────────────────────────────────────── */}
            <motion.div variants={variants.fadeUp}>
              <SessionTimeline />
            </motion.div>

          </motion.div>
        </main>

        <footer className="border-t border-[#E8EDF3] px-5 py-4">
          <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 text-[0.76rem] font-semibold text-[#9CA3AF]">
            <p className="flex items-center gap-1.5"><ShieldCheck className="h-4 w-4 text-[#38B88A]" /> Enterprise Secure</p>
            <p>&copy; 2026 CortexPrime. All rights reserved.</p>
          </div>
        </footer>
      </div>
    </div>
  );
}
