import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BadgeCheck,
  Cloud,
  Database,
  Handshake,
  Lock,
  Mic,
  Orbit,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
};

export type FeatureItem = {
  title: string;
  description: string;
  icon: LucideIcon;
};

export type TrustItem = {
  label: string;
  icon: LucideIcon;
};

export type OverviewMetric = {
  label: string;
  value: string;
  delta: string;
  footer: string;
  trend: number[];
};

export type MissionItem = {
  title: string;
  agent: string;
  status: "Running" | "Completed";
  time: string;
};

export type AgentItem = {
  title: string;
  version: string;
  status: "Running" | "Listening" | "Executing" | "Idle";
};

export type SystemMetric = {
  label: string;
  value: string;
  trend: number[];
};

export type AlertItem = {
  title: string;
  tone: "warning" | "info" | "danger";
  time: string;
};

export type StatItem = {
  value: string;
  label: string;
};

export const navItems: NavItem[] = [
  { label: "Platform", href: "#platform" },
  { label: "Solutions", href: "#solutions" },
  { label: "Resources", href: "#resources" },
  { label: "Pricing", href: "#enterprise" },
  { label: "Docs", href: "#resources" },
  { label: "Enterprise", href: "#enterprise" },
];

export const trustItems: TrustItem[] = [
  { label: "SOC 2 Ready", icon: ShieldCheck },
  { label: "Enterprise Security", icon: Lock },
  { label: "99.99% Uptime", icon: Activity },
  { label: "On-Prem or Cloud", icon: Cloud },
];

export const featureItems: FeatureItem[] = [
  {
    title: "Multi-Agent Orchestration",
    description: "Coordinate specialist agents with shared mission context.",
    icon: Orbit,
  },
  {
    title: "Real-time Voice AI",
    description: "Operators can guide, approve, and intervene instantly.",
    icon: Mic,
  },
  {
    title: "Memory & Knowledge",
    description: "Persistent memory layers keep missions grounded.",
    icon: Database,
  },
  {
    title: "Governance & Guardrails",
    description: "Policy-aware execution for regulated environments.",
    icon: Handshake,
  },
  {
    title: "Observability & Monitoring",
    description: "Live insight into autonomy, cost, and runtime health.",
    icon: Activity,
  },
  {
    title: "Replay & Audit Trails",
    description: "Trace every decision, event, and tool invocation.",
    icon: RotateCcw,
  },
  {
    title: "Secure by Design",
    description: "Identity, access, and isolation built into the runtime.",
    icon: ShieldCheck,
  },
  {
    title: "Enterprise Ready",
    description: "Deploy into internal networks, cloud, or hybrid stacks.",
    icon: BadgeCheck,
  },
];

export const overviewMetrics: OverviewMetric[] = [
  {
    label: "Active Agents",
    value: "24",
    delta: "+4",
    footer: "vs last 24h",
    trend: [30, 34, 33, 38, 35, 51, 43, 49, 46, 54],
  },
  {
    label: "Missions Running",
    value: "7",
    delta: "+2",
    footer: "vs last 24h",
    trend: [18, 21, 20, 26, 24, 31, 27, 36, 29, 38],
  },
  {
    label: "Success Rate",
    value: "98.7%",
    delta: "+1.3%",
    footer: "vs last 24h",
    trend: [83, 84, 83, 88, 86, 92, 89, 94, 91, 97],
  },
  {
    label: "System Health",
    value: "Excellent",
    delta: "",
    footer: "All systems operational",
    trend: [94, 96, 95, 97, 98, 97, 98, 99, 99, 100],
  },
];

export const missionItems: MissionItem[] = [
  {
    title: "Research Report Generation",
    agent: "Research Agent",
    status: "Running",
    time: "2m ago",
  },
  {
    title: "Competitor Analysis",
    agent: "Browser Agent",
    status: "Running",
    time: "5m ago",
  },
  {
    title: "Data Extraction",
    agent: "Computer Agent",
    status: "Completed",
    time: "8m ago",
  },
  {
    title: "Memory Optimization",
    agent: "Memory Agent",
    status: "Completed",
    time: "12m ago",
  },
];

export const agentItems: AgentItem[] = [
  { title: "Research Agent", version: "v1.2.4", status: "Running" },
  { title: "Voice Agent", version: "v1.3.1", status: "Listening" },
  { title: "Browser Agent", version: "v1.1.8", status: "Executing" },
  { title: "Computer Agent", version: "v1.0.9", status: "Idle" },
];

export const systemMetrics: SystemMetric[] = [
  { label: "CPU Usage", value: "32%", trend: [24, 28, 27, 38, 35, 49, 42, 36] },
  { label: "Memory Usage", value: "61%", trend: [43, 47, 45, 58, 51, 62, 56, 53] },
  { label: "Token Usage", value: "2.4M", trend: [21, 24, 23, 29, 28, 35, 33, 40] },
  { label: "Latency (p95)", value: "92ms", trend: [30, 34, 33, 47, 45, 61, 50, 54] },
];

export const alertItems: AlertItem[] = [
  { title: "High memory usage detected", tone: "warning", time: "2m ago" },
  { title: "Voice service reconnecting", tone: "info", time: "5m ago" },
  { title: "Mission failure: Data sync", tone: "danger", time: "16m ago" },
];

export const statItems: StatItem[] = [
  { value: "10K+", label: "Active Users" },
  { value: "5M+", label: "Missions Executed" },
  { value: "99.99%", label: "Uptime SLA" },
  { value: "<100ms", label: "P95 Latency" },
  { value: "24/7", label: "Enterprise Support" },
  { value: "150+", label: "Integrations" },
];

