import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  Bot,
  Brain,
  ClipboardCheck,
  Cpu,
  Database,
  Gauge,
  Globe,
  Home,
  Layers,
  Library,
  MemoryStick,
  Mic,
  Monitor,
  PlayCircle,
  Puzzle,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Terminal,
  Zap,
} from "lucide-react";

export type StatusTone = "running" | "healthy" | "warning" | "critical" | "idle" | "info" | "completed";

export type SidebarItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  active?: boolean;
};

export type KpiMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: StatusTone;
  icon: LucideIcon;
  data: number[];
};

export type Mission = {
  name: string;
  agent: string;
  status: StatusTone;
  startTime: string;
  progress: number;
};

export type Agent = {
  name: string;
  version: string;
  runtime: string;
  status: StatusTone;
  health: number;
  icon: LucideIcon;
};

export type SystemMetric = {
  label: string;
  value: string;
  detail: string;
  tone: StatusTone;
  data: number[];
};

export type Alert = {
  message: string;
  time: string;
  severity: StatusTone;
};

export type QuickAction = {
  label: string;
  description: string;
  href: string;
  icon: LucideIcon;
};

export type HealthSignal = {
  label: string;
  value: number;
  status: string;
};

export type ActivityItem = {
  title: string;
  detail: string;
  time: string;
  icon: LucideIcon;
  tone: StatusTone;
};

export const sidebarItems: SidebarItem[] = [
  { label: "Dashboard", href: "/command", icon: Home, active: true },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Missions", href: "/command#missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain },
  { label: "Research", href: "/workspace", icon: Search },
  { label: "Computer Use", href: "/operator", icon: Monitor },
  { label: "Browser", href: "/operator", icon: Globe },
  { label: "Replay", href: "/replay", icon: Archive },
  { label: "Analytics", href: "/analytics", icon: Activity },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Gauge },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const kpiMetrics: KpiMetric[] = [
  {
    label: "Active Agents",
    value: "24",
    trend: "+4 vs yesterday",
    status: "Live",
    tone: "running",
    icon: Bot,
    data: [18, 19, 22, 20, 24, 25, 23, 24, 27, 24],
  },
  {
    label: "Running Missions",
    value: "7",
    trend: "+2 vs yesterday",
    status: "Running",
    tone: "running",
    icon: Target,
    data: [4, 5, 4, 6, 5, 7, 6, 6, 8, 7],
  },
  {
    label: "System Health",
    value: "Excellent",
    trend: "All systems operational",
    status: "Healthy",
    tone: "healthy",
    icon: ShieldCheck,
    data: [92, 93, 94, 94, 95, 96, 96, 97, 97, 98],
  },
  {
    label: "Success Rate",
    value: "98.7%",
    trend: "+1.3% vs yesterday",
    status: "Stable",
    tone: "healthy",
    icon: ClipboardCheck,
    data: [93, 94, 95, 94, 96, 97, 96, 98, 97, 99],
  },
];

export const missions: Mission[] = [
  { name: "Q2 Market Intelligence", agent: "Research Agent", status: "running", startTime: "09:24", progress: 76 },
  { name: "Data Collection", agent: "Browser Agent", status: "running", startTime: "09:41", progress: 63 },
  { name: "Processing & Reasoning", agent: "Computer Agent", status: "running", startTime: "10:03", progress: 48 },
  { name: "Report Generation", agent: "Writing Agent", status: "completed", startTime: "10:18", progress: 100 },
  { name: "Governance Review", agent: "Policy Agent", status: "healthy", startTime: "10:27", progress: 91 },
];

export const agents: Agent[] = [
  { name: "Research Agent", version: "v2.1.4", runtime: "GPT-4o", status: "running", health: 98, icon: Search },
  { name: "Voice Agent", version: "v1.3.1", runtime: "Whisper", status: "running", health: 96, icon: Mic },
  { name: "Browser Agent", version: "v1.1.8", runtime: "Chromium", status: "running", health: 94, icon: Globe },
  { name: "Computer Agent", version: "v1.0.9", runtime: "OS Executor", status: "idle", health: 89, icon: Monitor },
  { name: "Memory Agent", version: "v1.2.2", runtime: "VectorDB", status: "running", health: 97, icon: Database },
];

export const systemMetrics: SystemMetric[] = [
  { label: "CPU", value: "32%", detail: "Cluster load", tone: "healthy", data: [22, 25, 24, 31, 28, 35, 31, 34, 32] },
  { label: "Memory", value: "61%", detail: "Runtime pool", tone: "warning", data: [52, 54, 58, 56, 60, 63, 62, 61, 61] },
  { label: "Latency", value: "92ms", detail: "P95 voice", tone: "healthy", data: [118, 110, 104, 102, 99, 94, 96, 92, 92] },
  { label: "Token Usage", value: "2.4M", detail: "Today", tone: "info", data: [1.6, 1.7, 1.9, 2.0, 2.1, 2.25, 2.3, 2.36, 2.4] },
  { label: "Queue Length", value: "12", detail: "Pending jobs", tone: "healthy", data: [18, 16, 15, 17, 14, 13, 12, 13, 12] },
  { label: "Cost Today", value: "$842", detail: "Projected", tone: "info", data: [420, 488, 530, 612, 680, 721, 780, 810, 842] },
];

export const alerts: Alert[] = [
  { message: "Memory usage reached 61% on runtime pool", time: "2m ago", severity: "warning" },
  { message: "Voice service reconnected to low-latency channel", time: "7m ago", severity: "info" },
  { message: "Mission retry threshold exceeded for data sync", time: "16m ago", severity: "critical" },
  { message: "Governance policy pack updated successfully", time: "28m ago", severity: "healthy" },
];

export const quickActions: QuickAction[] = [
  { label: "Launch Mission", description: "Start a guided enterprise objective.", href: "/command#missions", icon: PlayCircle },
  { label: "Create Agent", description: "Provision a specialist runtime.", href: "/agents", icon: Bot },
  { label: "Open Voice", description: "Connect the voice operator.", href: "/voice", icon: Mic },
  { label: "Search Memory", description: "Inspect semantic knowledge.", href: "/memory-explorer", icon: MemoryStick },
  { label: "Start Research", description: "Run web and document analysis.", href: "/workspace", icon: Library },
  { label: "Open Governance", description: "Review policy decisions.", href: "/governance", icon: ShieldCheck },
];

export const insights =
  "Today's AI workforce completed 94 missions with a 98.7% success rate. Voice latency improved by 14%. No governance violations detected.";

export const healthSignals: HealthSignal[] = [
  { label: "Voice Runtime", value: 96, status: "Healthy" },
  { label: "Memory", value: 98, status: "Healthy" },
  { label: "Research", value: 94, status: "Healthy" },
  { label: "Browser", value: 91, status: "Stable" },
  { label: "Infrastructure", value: 99, status: "Healthy" },
  { label: "Overall Health", value: 98, status: "Excellent" },
];

export const activityFeed: ActivityItem[] = [
  { title: "Mission started", detail: "Q2 Market Intelligence", time: "2m ago", icon: Target, tone: "running" },
  { title: "Mission completed", detail: "Research Agent completed data collection", time: "5m ago", icon: ClipboardCheck, tone: "completed" },
  { title: "Voice connected", detail: "Sales team voice bridge completed", time: "15m ago", icon: Mic, tone: "info" },
  { title: "Memory indexed", detail: "New knowledge added to vector store", time: "18m ago", icon: Layers, tone: "healthy" },
  { title: "Research finished", detail: "Competitor brief ready for review", time: "32m ago", icon: Search, tone: "completed" },
  { title: "Governance approved", detail: "Policy sandbox cleared runtime request", time: "41m ago", icon: ShieldCheck, tone: "healthy" },
];

export const resourceUsage = [
  { label: "CPU", value: "32%", color: "#38B88A", icon: Cpu, data: [18, 22, 21, 29, 27, 32, 30, 35, 32] },
  { label: "Memory", value: "61%", color: "#3B82F6", icon: MemoryStick, data: [48, 54, 53, 58, 60, 62, 59, 61, 61] },
  { label: "GPU", value: "24%", color: "#8B5CF6", icon: Sparkles, data: [22, 24, 23, 26, 21, 24, 25, 23, 24] },
  { label: "Disk I/O", value: "18%", color: "#F59E0B", icon: Terminal, data: [12, 14, 13, 19, 18, 21, 17, 18, 18] },
];


