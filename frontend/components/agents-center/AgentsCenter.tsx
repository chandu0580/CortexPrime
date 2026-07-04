"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
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
  CheckCircle,
  AlertTriangle,
  Play,
  Clock,
  Check,
  FileSearch,
  Database,
  Library,
  Code2,
  Menu,
  X,
  PlayCircle
} from "lucide-react";

import { cn } from "@/utils/cn";
import { stagger, variants } from "@/lib/motion-tokens";
import { agents, sidebarItems, type AgentRecord, type AgentTone } from "@/components/agents-center/data";

// ─── Tones & Styles ───────────────────────────────────────────────────────────
const toneStyles: Record<string, string> = {
  running:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  healthy:   "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  completed: "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]",
  idle:      "bg-[#FFF7ED] text-[#C2410C] ring-[#FED7AA]",
  warning:   "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  degraded:  "bg-[#FFFBEB] text-[#B45309] ring-[#FDECC8]",
  error:     "bg-[#FEF2F2] text-[#B91C1C] ring-[#FBD5D5]",
  queued:    "bg-[#F8FAFC] text-[#6B7280] ring-[#E5E7EB]",
  info:      "bg-[#EFF6FF] text-[#2563EB] ring-[#DBEAFE]",
};

const toneDot: Record<string, string> = {
  running:   "bg-[#38B88A]",
  healthy:   "bg-[#38B88A]",
  completed: "bg-[#38B88A]",
  idle:      "bg-[#F97316]",
  warning:   "bg-[#F59E0B]",
  degraded:  "bg-[#F59E0B]",
  error:     "bg-[#EF4444]",
  queued:    "bg-[#9CA3AF]",
  info:      "bg-[#3B82F6]",
};

const categoryBadgeStyles: Record<string, string> = {
  Research: "text-[#6366F1] bg-[#EEF2FF] border-[#E0E7FF]",
  Voice: "text-[#2563EB] bg-[#EFF6FF] border-[#DBEAFE]",
  Browser: "text-[#3B82F6] bg-[#EFF6FF] border-[#DBEAFE]",
  "Computer Use": "text-[#0D9488] bg-[#F0FDFA] border-[#CCFBF1]",
  Memory: "text-[#4F46E5] bg-[#EEF2FF] border-[#E0E7FF]",
  Analytics: "text-[#D97706] bg-[#FFFBEB] border-[#FEF3C7]",
  Productivity: "text-[#059669] bg-[#ECFDF5] border-[#D1FAE5]",
  Developer: "text-[#E11D48] bg-[#FFF1F2] border-[#FFE4E6]",
  System: "text-[#475569] bg-[#F1F5F9] border-[#E2E8F0]",
};

// ─── Status Badge ────────────────────────────────────────────────────────────
function StatusBadge({ tone, text }: { tone: string; text: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-[3px] text-[0.73rem] font-semibold ring-1", toneStyles[tone] ?? toneStyles.info)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", toneDot[tone] ?? "bg-[#6B7280]")} />
      {text}
    </span>
  );
}

// ─── Animated Number ──────────────────────────────────────────────────────────
function AnimatedNum({ value }: { value: string }) {
  const num = Number(value.replace(/[^0-9.]/g, ""));
  const count = useMotionValue(0);
  const spring = useSpring(count, { stiffness: 80, damping: 22 });
  const display = useTransform(spring, (v) => {
    if (!Number.isFinite(num) || num === 0) return value;
    const n = num >= 100 ? Math.round(v) : Math.round(v * 10) / 10;
    return value.replace(/[0-9.]+/, String(n));
  });

  useEffect(() => {
    if (Number.isFinite(num) && num > 0) count.set(num);
  }, [count, num]);

  if (!Number.isFinite(num) || num === 0) return <span>{value}</span>;
  return <motion.span>{display}</motion.span>;
}

// ─── Custom SVG Sparkline ──────────────────────────────────────────────────────
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length === 0) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const height = 28;
  const width = 140;
  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * (height - 6) - 3;
    return `${x},${y}`;
  });
  const pathData = `M ${points.join(" L ")}`;
  const fillPathData = `${pathData} L ${width},${height} L 0,${height} Z`;
  const gradId = `grad-${color.replace("#", "")}`;

  return (
    <div className="h-7 w-full mt-3 overflow-hidden">
      <svg className="w-full h-full" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.18} />
            <stop offset="100%" stopColor={color} stopOpacity={0.0} />
          </linearGradient>
        </defs>
        <path d={fillPathData} fill={`url(#${gradId})`} />
        <path d={pathData} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ─── Sidebar Navigation ────────────────────────────────────────────────────────
const NAV = [
  { href: "/command",          label: "Dashboard",    icon: Home    },
  { href: "/runtime",          label: "Runtime",      icon: Zap     },
  { href: "/agents",           label: "Agents",       icon: Bot     },
  { href: "/command#missions", label: "Missions",     icon: Target  },
  { href: "/voice",            label: "Voice",        icon: Mic     },
  { href: "/memory",           label: "Memory",       icon: Brain   },
  { href: "/workspace",        label: "Research",     icon: Search  },
  { href: "/operator",         label: "Computer Use", icon: Monitor },
  { href: "/operator",         label: "Browser",      icon: Globe   },
  { href: "/replay",           label: "Replay",       icon: Archive },
  { href: "/analytics",        label: "Analytics",    icon: BarChart2 },
  { href: "/governance",       label: "Governance",   icon: Shield  },
  { href: "/system-status",    label: "Monitoring",   icon: Activity },
  { href: "/integrations",     label: "Integrations", icon: Puzzle  },
  { href: "/settings",         label: "Settings",     icon: Settings },
];

function Sidebar({ collapsed, onCollapse }: { collapsed: boolean; onCollapse: () => void }) {
  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#EAEFF5] bg-white transition-all duration-300",
        collapsed ? "w-[68px]" : "w-[220px]",
      )}
    >
      {/* Logo */}
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

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const isActive = label === "Agents";
          return (
            <Link
              key={label}
              href={href}
              className={cn(
                "flex w-full items-center gap-3 rounded-[14px] px-3 py-2.5 text-left transition-all",
                isActive
                  ? "bg-[#ECFBF4] text-[#2F9F77]"
                  : "text-[#6B7280] hover:bg-[#F8FAFC] hover:text-[#111827]",
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

      {/* Bottom status + collapse */}
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
          className={cn(
            "flex w-full items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-3 py-2 text-[0.82rem] font-semibold text-[#6B7280] transition hover:bg-[#F8FAFC]",
            collapsed && "justify-center",
          )}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronLeft className="h-4 w-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  );
}

// ─── Header ──────────────────────────────────────────────────────────────────
function Header({ collapsed }: { collapsed: boolean }) {
  const avatar = useMemo(() =>
    `data:image/svg+xml;utf8,${encodeURIComponent(
      `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80"><rect width="80" height="80" rx="20" fill="#ECFBF4"/><circle cx="40" cy="30" r="14" fill="#38B88A"/><path d="M18 70c4-15 14-22 22-22s18 7 22 22" fill="#2F9F77"/></svg>`,
    )}`, []);

  return (
    <header
      className={cn(
        "sticky top-0 z-30 flex items-center gap-3 border-b border-[#EAEFF5] bg-white/96 px-5 py-3 backdrop-blur transition-all duration-300",
        collapsed ? "pl-[80px]" : "pl-[232px]",
      )}
    >
      {/* Search */}
      <label className="relative flex h-10 w-[240px] shrink-0 items-center">
        <Search className="pointer-events-none absolute left-3.5 h-4 w-4 text-[#9CA3AF]" />
        <input
          type="search"
          placeholder="Search anything..."
          className="h-full w-full rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] pl-10 pr-14 text-[0.86rem] text-[#111827] outline-none placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"
        />
        <span className="absolute right-3 rounded-[7px] border border-[#E5E7EB] bg-white px-1.5 py-0.5 text-[0.66rem] font-semibold text-[#9CA3AF]">⌘K</span>
      </label>

      {/* Current Mission */}
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 xl:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
          <Target className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Current Mission</p>
          <div className="flex items-center gap-2">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Q2 Market Intelligence</p>
            <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-1.5 py-0.5 text-[0.6rem] font-bold text-[#2F9F77]">
              <span className="h-1 w-1 rounded-full bg-[#38B88A]" />
              Running
            </span>
          </div>
        </div>
        <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] ml-1" />
      </div>

      {/* Voice Status */}
      <div className="hidden items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] px-3 py-1.5 lg:flex">
        <div className="flex h-7 w-7 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
          <Mic className="h-3.5 w-3.5" />
        </div>
        <div>
          <p className="text-[0.66rem] font-medium text-[#9CA3AF]">Voice Status</p>
          <div className="flex items-center gap-2">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Listening...</p>
            <div className="flex items-center gap-[2px] h-2.5">
              <span className="w-[2px] h-2 bg-[#38B88A]/80 rounded-full animate-pulse" />
              <span className="w-[2px] h-3 bg-[#38B88A] rounded-full" />
              <span className="w-[2px] h-1.5 bg-[#38B88A]/60 rounded-full" />
              <span className="w-[2px] h-2.5 bg-[#38B88A] rounded-full animate-pulse" />
            </div>
          </div>
        </div>
      </div>

      {/* Profile & Notifications */}
      <div className="ml-auto flex items-center gap-3">
        <button className="relative flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#EAEFF5] bg-white text-[#374151] hover:bg-[#F8FAFC]">
          <Bell className="h-4.5 w-4.5" />
          <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-[#EF4444] text-[0.68rem] font-bold text-white ring-2 ring-white">
            3
          </span>
        </button>

        <div className="flex items-center gap-2.5 rounded-[14px] border border-[#EAEFF5] bg-white p-1 pr-3 hover:bg-[#F8FAFC] cursor-pointer">
          <Image src={avatar} alt="Alex Morgan profile" width={32} height={32} className="rounded-[10px]" />
          <div className="leading-tight text-left hidden sm:block">
            <p className="text-[0.8rem] font-semibold text-[#111827]">Alex Morgan</p>
            <p className="text-[0.68rem] font-medium text-[#9CA3AF]">Enterprise Admin</p>
          </div>
          <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF] hidden sm:block" />
        </div>
      </div>
    </header>
  );
}

// ─── KPI METRICS DATA ──────────────────────────────────────────────────────────
const kpiCards = [
  {
    label: "Total Agents",
    value: "36",
    trend: "↑ 8",
    subtext: "vs last 7 days",
    icon: Bot,
    color: "#38B88A",
    sparklineData: [24, 26, 28, 27, 31, 32, 34, 35, 36],
  },
  {
    label: "Active Agents",
    value: "24",
    trend: "",
    subtext: "66.7% of total",
    icon: PlayCircle,
    color: "#38B88A",
    sparklineData: [16, 18, 20, 19, 22, 21, 23, 24, 24],
  },
  {
    label: "Idle Agents",
    value: "6",
    trend: "",
    subtext: "16.7% of total",
    icon: Clock,
    color: "#38B88A",
    sparklineData: [8, 7, 7, 6, 7, 6, 6, 5, 6],
  },
  {
    label: "Error Agents",
    value: "2",
    trend: "",
    subtext: "5.6% of total",
    icon: AlertTriangle,
    color: "#EF4444",
    sparklineData: [1, 2, 1, 3, 2, 4, 3, 2, 2],
  },
  {
    label: "Success Rate",
    value: "98.7%",
    trend: "↑ 1.6%",
    subtext: "vs last 7 days",
    icon: CheckCircle,
    color: "#38B88A",
    sparklineData: [94, 95, 96, 95, 97, 98, 97, 99, 98.7],
  },
];

// ─── DYNAMIC RECENT TASKS ──────────────────────────────────────────────────────
const agentTasksMap: Record<string, Array<{ name: string; status: string; tone: string; time: string }>> = {
  "Research Agent": [
    { name: "Market research on AI trends", status: "Completed", tone: "healthy", time: "2m ago" },
    { name: "Competitor analysis - OpenAI", status: "Completed", tone: "healthy", time: "8m ago" },
    { name: "Search latest funding news", status: "Completed", tone: "healthy", time: "15m ago" },
    { name: "Industry report collection", status: "Running", tone: "info", time: "1m ago" },
    { name: "Data extraction from sources", status: "Queued", tone: "warning", time: "3m ago" },
  ],
  "Voice Agent": [
    { name: "Real-time speech-to-text conversion", status: "Completed", tone: "healthy", time: "3m ago" },
    { name: "Audio streaming latency optimization", status: "Completed", tone: "healthy", time: "10m ago" },
    { name: "Voice activity detection calibration", status: "Completed", tone: "healthy", time: "25m ago" },
    { name: "Sales conversation transcription", status: "Running", tone: "info", time: "40s ago" },
    { name: "Synthesized audio voice generation", status: "Queued", tone: "warning", time: "5m ago" },
  ],
  "Browser Agent": [
    { name: "Automated sign-in flow validation", status: "Completed", tone: "healthy", time: "5m ago" },
    { name: "Price scraping from competitor websites", status: "Completed", tone: "healthy", time: "12m ago" },
    { name: "Cookie session verification checks", status: "Completed", tone: "healthy", time: "19m ago" },
    { name: "CortexPrime UI audit execution", status: "Running", tone: "info", time: "10s ago" },
    { name: "Full page screenshot capture tasks", status: "Queued", tone: "warning", time: "2m ago" },
  ],
  "Computer Agent": [
    { name: "Excel report generator macro execution", status: "Completed", tone: "healthy", time: "4m ago" },
    { name: "Local file structure cleanup script", status: "Completed", tone: "healthy", time: "15m ago" },
    { name: "Network connection driver diagnostics", status: "Completed", tone: "healthy", time: "30m ago" },
    { name: "Desktop window layout adjustments", status: "Running", tone: "info", time: "2m ago" },
    { name: "Background worker thread allocation", status: "Queued", tone: "warning", time: "4m ago" },
  ],
  "Memory Agent": [
    { name: "Knowledge graph node optimization", status: "Completed", tone: "healthy", time: "1m ago" },
    { name: "Vector database indexing pipeline", status: "Completed", tone: "healthy", time: "6m ago" },
    { name: "Unused cache memory cleanups", status: "Completed", tone: "healthy", time: "20m ago" },
    { name: "Semantic query embedding matches", status: "Running", tone: "info", time: "30s ago" },
    { name: "Long-term archive cold storage backups", status: "Queued", tone: "warning", time: "8m ago" },
  ],
  "Data Analyst Agent": [
    { name: "Revenue statistics trend analysis", status: "Completed", tone: "healthy", time: "9m ago" },
    { name: "Anomalous transaction data filters", status: "Completed", tone: "healthy", time: "18m ago" },
    { name: "Data correlation matrix mappings", status: "Completed", tone: "healthy", time: "35m ago" },
    { name: "Interactive chart layout renderings", status: "Completed", tone: "healthy", time: "45m ago" },
    { name: "Dashboard metric summary exports", status: "Completed", tone: "healthy", time: "1h ago" },
  ],
  "Report Generation Agent": [
    { name: "Weekly operations executive summaries", status: "Completed", tone: "healthy", time: "7m ago" },
    { name: "Q2 market performance report builds", status: "Completed", tone: "healthy", time: "14m ago" },
    { name: "Client feedback presentation generation", status: "Completed", tone: "healthy", time: "28m ago" },
    { name: "Automated alert history log compiler", status: "Running", tone: "info", time: "2m ago" },
    { name: "PDF document export formatting", status: "Queued", tone: "warning", time: "5m ago" },
  ],
  "Code Assistant Agent": [
    { name: "Unit test coverage optimization plan", status: "Completed", tone: "healthy", time: "1h ago" },
    { name: "Legacy class refactoring checks", status: "Completed", tone: "healthy", time: "2h ago" },
    { name: "API endpoints integration test runs", status: "Completed", tone: "healthy", time: "3h ago" },
    { name: "Critical hotfix bundle validation", status: "Running", tone: "info", time: "50s ago" },
    { name: "Pull request code reviews", status: "Queued", tone: "warning", time: "10m ago" },
  ],
  "Scheduler Agent": [
    { name: "Hourly microservice health pings", status: "Completed", tone: "healthy", time: "1m ago" },
    { name: "Database cron backup task dispatch", status: "Completed", tone: "healthy", time: "11m ago" },
    { name: "Garbage collector cycle trigger pings", status: "Completed", tone: "healthy", time: "21m ago" },
    { name: "Agent activity logging cron run", status: "Running", tone: "info", time: "45s ago" },
    { name: "Queue listener pooling frequency checks", status: "Queued", tone: "warning", time: "3m ago" },
  ],
  "Notification Agent": [
    { name: "Critical error SMS alerts dispatcher", status: "Completed", tone: "healthy", time: "2m ago" },
    { name: "Weekly summary email newsletter sends", status: "Completed", tone: "healthy", time: "12m ago" },
    { name: "Slack webhooks notification pings", status: "Completed", tone: "healthy", time: "22m ago" },
    { name: "Microsoft Teams connector alerts broadcast", status: "Running", tone: "info", time: "1m ago" },
    { name: "Push notifications delivery retries", status: "Queued", tone: "warning", time: "3m ago" },
  ],
};

// ─── Main Component ───────────────────────────────────────────────────────────
export default function AgentsCenter() {
  const [collapsed, setCollapsed] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentRecord>(agents[0]);
  const [selectedTab, setSelectedTab] = useState("Overview");

  // Filter agents locally if search is input
  const [searchQuery, setSearchQuery] = useState("");
  const filteredAgents = useMemo(() => {
    if (!searchQuery) return agents;
    return agents.filter(
      (a) =>
        a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.description.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery]);

  // Tasks for selected agent
  const currentTasks = useMemo(() => {
    return agentTasksMap[selectedAgent.name] || agentTasksMap["Research Agent"];
  }, [selectedAgent.name]);

  return (
    <div className="min-h-screen bg-[#F4F7FA] text-[#111827]">
      {/* Sidebar */}
      <Sidebar collapsed={collapsed} onCollapse={() => setCollapsed((v) => !v)} />

      {/* Main Container */}
      <div className={cn("flex min-h-screen flex-col transition-all duration-300", collapsed ? "pl-[68px]" : "pl-[220px]")}>
        {/* Header */}
        <Header collapsed={collapsed} />

        <main className="flex-1 px-5 py-5 lg:px-6">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={stagger(0.04, 0.02)}
            className="mx-auto max-w-[1500px] space-y-5"
          >
            {/* Title & Actions */}
            <motion.div variants={variants.fadeUp} className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <div className="flex items-center gap-3">
                  <h1 className="text-[1.8rem] font-bold tracking-[-0.03em] text-[#111827]">AI Agents</h1>
                  <span className="inline-flex items-center rounded-full bg-[#ECFBF4] px-2.5 py-0.5 text-[0.76rem] font-semibold text-[#2F9F77] ring-1 ring-[#D6F0E5]">
                    36 Agents
                  </span>
                </div>
                <p className="mt-1 text-[0.88rem] text-[#6B7280]">
                  Deploy, monitor, and manage your AI workforce.
                </p>
              </div>

              <div className="flex shrink-0 items-center gap-2.5">
                <button className="flex items-center gap-2 rounded-[14px] border border-[#EAEFF5] bg-white px-4 py-2.5 text-[0.86rem] font-semibold text-[#374151] transition hover:bg-[#F8FAFC]">
                  All Categories <ChevronDown className="h-4 w-4 text-[#9CA3AF]" />
                </button>
                <button className="flex h-10 w-10 items-center justify-center rounded-[14px] border border-[#EAEFF5] bg-white text-[#374151] transition hover:bg-[#F8FAFC]" aria-label="Filters">
                  <Filter className="h-4 w-4 text-[#6B7280]" />
                </button>
                <button className="flex items-center gap-2 rounded-[14px] bg-[#38B88A] px-4 py-2.5 text-[0.86rem] font-semibold text-white shadow-[0_4px_12px_rgba(56,184,138,0.24)] transition hover:bg-[#2F9F77]">
                  <Plus className="h-4 w-4" /> Create Agent
                </button>
              </div>
            </motion.div>

            {/* KPI Cards Grid */}
            <motion.div variants={stagger(0.04)} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
              {kpiCards.map((card) => {
                const Icon = card.icon;
                const isError = card.label === "Error Agents";
                const iconColor = isError ? "text-[#EF4444]" : "text-[#38B88A]";
                const circleBg = isError ? "bg-[#FEF2F2] border-[#FBD5D5]" : "bg-[#ECFBF4] border-[#D6F0E5]";

                return (
                  <div
                    key={card.label}
                    className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)]"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-[0.82rem] font-semibold text-[#9CA3AF]">{card.label}</p>
                      <div className={cn("flex h-8 w-8 items-center justify-center rounded-full border", circleBg, iconColor)}>
                        <Icon className="h-4.5 w-4.5" />
                      </div>
                    </div>

                    <div className="mt-3 flex items-baseline">
                      <p className="text-[1.8rem] font-bold tracking-tight text-[#111827]">
                        <AnimatedNum value={card.value} />
                      </p>
                      {card.trend && (
                        <span className="ml-2 text-[0.82rem] font-bold text-[#38B88A]">{card.trend}</span>
                      )}
                    </div>
                    <p className="text-[0.73rem] font-semibold text-[#9CA3AF] mt-0.5">{card.subtext}</p>

                    <Sparkline data={card.sparklineData} color={card.color} />
                  </div>
                );
              })}
            </motion.div>

            {/* Core Split Screen Layout: Directory & Details */}
            <motion.div variants={stagger(0.05)} className="grid gap-5 lg:grid-cols-12">
              
              {/* Left Column: Agent Directory Table */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-8">
                <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <h2 className="text-[0.98rem] font-bold text-[#111827]">Agent Directory</h2>
                  <div className="relative h-9 w-full max-w-[260px]">
                    <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#9CA3AF]" />
                    <input
                      type="search"
                      placeholder="Search agents..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="h-full w-full rounded-[10px] border border-[#EAEFF5] bg-[#F8FAFC] pl-9 pr-3 text-[0.82rem] outline-none transition placeholder:text-[#9CA3AF] focus:border-[#B7E5D3] focus:ring-2 focus:ring-[#EAF8F1]"
                    />
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full border-separate border-spacing-y-[6px]">
                    <thead>
                      <tr className="text-left text-[0.7rem] font-bold uppercase tracking-wider text-[#9CA3AF]">
                        <th className="px-3 py-1.5">Agent</th>
                        <th className="px-3 py-1.5">Category</th>
                        <th className="px-3 py-1.5">Status</th>
                        <th className="px-3 py-1.5">Health</th>
                        <th className="px-3 py-1.5">Tasks</th>
                        <th className="px-3 py-1.5">Success Rate</th>
                        <th className="px-3 py-1.5">Last Activity</th>
                        <th className="px-3 py-1.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAgents.map((agent) => {
                        const isSelected = selectedAgent.name === agent.name;
                        const AgentIcon = agent.icon || Bot;

                        return (
                          <tr
                            key={agent.name}
                            onClick={() => setSelectedAgent(agent)}
                            className={cn(
                              "cursor-pointer text-[0.82rem] transition-all",
                              isSelected
                                ? "bg-[#ECFBF4]/30 shadow-[inset_0_0_0_1px_rgba(56,184,138,0.25)] rounded-[12px]"
                                : "bg-[#F8FAFC] hover:bg-[#F1F5F9]/60"
                            )}
                          >
                            <td className="rounded-l-[12px] px-3 py-2.5">
                              <div className="flex items-center gap-3">
                                <div className="flex h-9 w-9 items-center justify-center rounded-[10px] bg-[#ECFBF4] text-[#38B88A]">
                                  <AgentIcon className="h-4.5 w-4.5" />
                                </div>
                                <div className="leading-tight">
                                  <div className="flex items-center gap-1.5">
                                    <p className="font-bold text-[#111827]">{agent.name}</p>
                                    <span className="text-[0.68rem] font-semibold text-[#9CA3AF]">{agent.version}</span>
                                  </div>
                                  <p className="text-[0.73rem] text-[#6B7280] mt-0.5 max-w-[160px] truncate">{agent.description}</p>
                                </div>
                              </div>
                            </td>
                            <td className="px-3 py-2.5">
                              <span className={cn(
                                "inline-flex items-center rounded-full border px-2 py-0.5 text-[0.7rem] font-bold",
                                categoryBadgeStyles[agent.category] ?? categoryBadgeStyles.System
                              )}>
                                {agent.category}
                              </span>
                            </td>
                            <td className="px-3 py-2.5">
                              <StatusBadge tone={agent.status} text={agent.status === "running" ? "Running" : agent.status === "error" ? "Error" : "Idle"} />
                            </td>
                            <td className="px-3 py-2.5">
                              <StatusBadge tone={agent.healthTone} text={agent.healthTone === "healthy" ? "Healthy" : "Degraded"} />
                            </td>
                            <td className="px-3 py-2.5 font-bold text-[#111827]">{agent.tasks}</td>
                            <td className="px-3 py-2.5 font-bold text-[#111827]">{agent.successRate}</td>
                            <td className="px-3 py-2.5 text-[#6B7280] font-medium">{agent.lastActivity}</td>
                            <td className="rounded-r-[12px] px-3 py-2.5 text-right">
                              <button className="h-7 w-7 items-center justify-center rounded-[8px] text-[#9CA3AF] hover:bg-white hover:text-[#111827] inline-flex">
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
                <div className="mt-4 flex flex-col gap-3 text-[0.8rem] font-semibold text-[#9CA3AF] sm:flex-row sm:items-center sm:justify-between border-t border-[#F1F5F9] pt-4">
                  <span>Showing 1 to 10 of 36 results</span>
                  <div className="flex items-center gap-5">
                    <div className="flex items-center gap-1.5">
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#9CA3AF] hover:bg-[#F8FAFC]">
                        <ChevronLeft className="h-3.5 w-3.5" />
                      </button>
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] bg-[#38B88A] text-white font-bold">1</button>
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#6B7280] hover:bg-[#F8FAFC]">2</button>
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#6B7280] hover:bg-[#F8FAFC]">3</button>
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#6B7280] hover:bg-[#F8FAFC]">4</button>
                      <button className="flex h-7 w-7 items-center justify-center rounded-[8px] border border-[#EAEFF5] bg-white text-[#9CA3AF] hover:bg-[#F8FAFC]">
                        <ChevronRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <button className="flex items-center gap-1.5 rounded-[8px] border border-[#EAEFF5] bg-white px-2.5 py-1 text-[0.76rem] text-[#6B7280]">
                      10 / page <ChevronDown className="h-3.5 w-3.5 text-[#9CA3AF]" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Agent Details */}
              <div className="rounded-[20px] border border-[#EAEFF5] bg-white p-5 shadow-[0_2px_12px_rgba(148,163,184,0.04)] lg:col-span-4 flex flex-col">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-[0.98rem] font-bold text-[#111827]">Agent Details</h2>
                  <span className="inline-flex items-center gap-1 rounded-full bg-[#ECFBF4] px-2 py-0.5 text-[0.7rem] font-bold text-[#2F9F77] ring-1 ring-[#D6F0E5]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#38B88A]" />
                    Live
                  </span>
                </div>

                {/* Profile Overview Box */}
                <div className="rounded-[16px] border border-[#EAEFF5] bg-[#F8FAFC] p-4 flex flex-col gap-3">
                  <div className="flex items-start gap-4">
                    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-[16px] bg-[#ECFBF4] text-[#38B88A] border border-[#D6F0E5]">
                      {(() => {
                        const DetailIcon = selectedAgent.icon || Bot;
                        return <DetailIcon className="h-7 w-7" />;
                      })()}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-[1.1rem] font-bold text-[#111827]">{selectedAgent.name}</h3>
                        <span className="text-[0.74rem] font-bold text-[#9CA3AF]">{selectedAgent.version}</span>
                      </div>
                      <div className="mt-1">
                        <StatusBadge tone={selectedAgent.status} text={selectedAgent.status === "running" ? "Running" : selectedAgent.status === "error" ? "Error" : "Idle"} />
                      </div>
                    </div>
                  </div>
                  <p className="text-[0.78rem] leading-relaxed text-[#6B7280]">
                    {selectedAgent.description}. Performs advanced web research, data collection, and insight generation.
                  </p>
                  <div className="flex items-center gap-2 border-t border-[#EAEFF5] pt-2.5">
                    <div className="h-6 w-6 rounded-full bg-[#38B88A] flex items-center justify-center text-white font-bold text-[0.66rem]">
                      AM
                    </div>
                    <p className="text-[0.74rem] font-bold text-[#6B7280]">
                      Owner: <span className="text-[#111827]">{selectedAgent.owner}</span>
                    </p>
                  </div>
                </div>

                {/* Tab Navigation */}
                <div className="mt-4 flex gap-4 border-b border-[#EAEFF5] text-[0.8rem] font-bold text-[#9CA3AF]">
                  {["Overview", "Performance", "Tasks", "Configuration", "Logs"].map((tab) => {
                    const isActive = selectedTab === tab;
                    return (
                      <button
                        key={tab}
                        onClick={() => setSelectedTab(tab)}
                        className={cn(
                          "pb-2.5 relative transition-colors",
                          isActive ? "text-[#2F9F77]" : "hover:text-[#111827]"
                        )}
                      >
                        {tab}
                        {isActive && (
                          <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#38B88A]" />
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Tab Content */}
                <div className="mt-4 flex-1 space-y-4">
                  {selectedTab === "Overview" ? (
                    <>
                      {/* Health Score Subcard */}
                      <div className="rounded-[16px] border border-[#EAEFF5] p-4">
                        <p className="text-[0.82rem] font-bold text-[#111827]">Health Score</p>
                        <div className="mt-3 flex flex-col items-center gap-5 sm:flex-row sm:items-stretch">
                          {/* Circle radial progress */}
                          <div className="relative flex items-center justify-center h-20 w-20 shrink-0">
                            <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                              <circle cx="50" cy="50" r="40" stroke="#F1F5F9" strokeWidth="8" fill="transparent" />
                              <circle
                                cx="50"
                                cy="50"
                                r="40"
                                stroke="#38B88A"
                                strokeWidth="8"
                                fill="transparent"
                                strokeDasharray={251.2}
                                strokeDashoffset={251.2 - (251.2 * selectedAgent.health) / 100}
                                strokeLinecap="round"
                              />
                            </svg>
                            <div className="absolute flex flex-col items-center justify-center">
                              <span className="text-[1.35rem] font-bold text-[#111827] leading-none">{selectedAgent.health}</span>
                              <span className="text-[0.6rem] text-[#9CA3AF] mt-0.5">/100</span>
                            </div>
                          </div>

                          {/* Stats Checklist */}
                          <div className="flex-1 space-y-2 text-[0.76rem]">
                            <div className="flex items-center justify-between pb-1.5 border-b border-[#F8FAFC]">
                              <span className="text-[#6B7280] flex items-center gap-1.5 font-semibold">
                                <Check className="h-3.5 w-3.5 text-[#38B88A] stroke-[3]" /> Uptime
                              </span>
                              <span className="font-bold text-[#111827]">7d 14h 32m</span>
                            </div>
                            <div className="flex items-center justify-between pb-1.5 border-b border-[#F8FAFC]">
                              <span className="text-[#6B7280] flex items-center gap-1.5 font-semibold">
                                <Check className="h-3.5 w-3.5 text-[#38B88A] stroke-[3]" /> Response Time
                              </span>
                              <span className="font-bold text-[#111827]">{selectedAgent.latency}</span>
                            </div>
                            <div className="flex items-center justify-between pb-1.5 border-b border-[#F8FAFC]">
                              <span className="text-[#6B7280] flex items-center gap-1.5 font-semibold">
                                <Check className="h-3.5 w-3.5 text-[#38B88A] stroke-[3]" /> Error Rate
                              </span>
                              <span className="font-bold text-[#111827]">
                                {selectedAgent.status === "error" ? "3.8%" : "0.3%"}
                              </span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-[#6B7280] flex items-center gap-1.5 font-semibold">
                                <Check className="h-3.5 w-3.5 text-[#38B88A] stroke-[3]" /> Success Rate
                              </span>
                              <span className="font-bold text-[#111827]">{selectedAgent.successRate}</span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Resource Usage Sparklines */}
                      <div>
                        <p className="text-[0.82rem] font-bold text-[#111827] mb-2.5">Resource Usage (Last 1 Hour)</p>
                        <div className="grid grid-cols-3 gap-3">
                          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] p-3 text-left">
                            <p className="text-[0.7rem] font-bold text-[#9CA3AF]">CPU</p>
                            <p className="text-[1.1rem] font-bold text-[#111827] mt-0.5">{selectedAgent.cpu}</p>
                            <Sparkline data={[20, 24, 22, 31, 27, 35, 31, 34, 32]} color="#38B88A" />
                          </div>
                          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] p-3 text-left">
                            <p className="text-[0.7rem] font-bold text-[#9CA3AF]">Memory</p>
                            <p className="text-[1.1rem] font-bold text-[#111827] mt-0.5">{selectedAgent.memory}</p>
                            <Sparkline data={[50, 55, 53, 58, 60, 62, 59, 61, 61]} color="#3B82F6" />
                          </div>
                          <div className="rounded-[14px] border border-[#EAEFF5] bg-[#F8FAFC] p-3 text-left">
                            <p className="text-[0.7rem] font-bold text-[#9CA3AF]">Tokens / min</p>
                            <p className="text-[1.1rem] font-bold text-[#111827] mt-0.5">2.45K</p>
                            <Sparkline data={[15, 18, 16, 22, 20, 24, 21, 23, 24]} color="#8B5CF6" />
                          </div>
                        </div>
                      </div>

                      {/* Recent Tasks List */}
                      <div>
                        <div className="mb-2.5 flex items-center justify-between">
                          <p className="text-[0.82rem] font-bold text-[#111827]">Recent Tasks</p>
                          <span className="text-[0.72rem] font-bold text-[#38B88A] hover:underline cursor-pointer">View All</span>
                        </div>
                        <div className="space-y-2">
                          {currentTasks.map((task, idx) => {
                            const isCompleted = task.status === "Completed";
                            const isRunning = task.status === "Running";
                            const TaskIcon = isCompleted ? CheckCircle : isRunning ? PlayCircle : Clock;
                            const iconColor = isCompleted ? "text-[#38B88A]" : isRunning ? "text-[#3B82F6]" : "text-[#9CA3AF]";

                            return (
                              <div
                                key={`${task.name}-${idx}`}
                                className="flex items-center justify-between rounded-[12px] border border-[#F1F5F9] bg-[#FCFDFC] p-2.5 text-[0.76rem] transition-colors hover:bg-[#F8FAFC]"
                              >
                                <div className="flex min-w-0 items-center gap-2.5">
                                  <TaskIcon className={cn("h-4.5 w-4.5 shrink-0", iconColor)} />
                                  <p className="truncate font-bold text-[#111827]">{task.name}</p>
                                </div>
                                <div className="flex shrink-0 items-center gap-2">
                                  <span className={cn(
                                    "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[0.66rem] font-bold ring-1",
                                    task.tone === "healthy" ? "bg-[#ECFBF4] text-[#2F9F77] ring-[#D6F0E5]" :
                                    task.tone === "info" ? "bg-[#EFF6FF] text-[#2563EB] ring-[#DBEAFE]" :
                                    "bg-[#FFF7ED] text-[#C2410C] ring-[#FED7AA]"
                                  )}>
                                    {task.status}
                                  </span>
                                  <span className="text-[0.68rem] font-medium text-[#9CA3AF]">{task.time}</span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-10 text-center text-[#9CA3AF]">
                      <Bot className="h-10 w-10 text-[#D1D5DB] animate-bounce mb-2" />
                      <p className="text-[0.8rem] font-bold">Details tab data loading...</p>
                      <p className="text-[0.72rem] text-[#D1D5DB] mt-0.5">Subsystem metrics compiling</p>
                    </div>
                  )}
                </div>
              </div>

            </motion.div>

            {/* Footer */}
            <motion.footer
              variants={variants.fadeUp}
              className="flex flex-col gap-2 border-t border-[#EAEFF5] pt-5 pb-2 text-[0.78rem] text-[#9CA3AF] md:flex-row md:items-center md:justify-between"
            >
              <div className="flex flex-wrap items-center gap-2">
                <ShieldCheck className="h-3.5 w-3.5 text-[#38B88A]" />
                <span>Enterprise Secure</span>
                <span>•</span>
                <span>SOC 2 Type II</span>
                <span>•</span>
                <span>GDPR Compliant</span>
                <span>•</span>
                <span>ISO 27001</span>
              </div>
              <p>© 2026 CortexPrime. All rights reserved.</p>
            </motion.footer>
          </motion.div>
        </main>
      </div>
    </div>
  );
}
