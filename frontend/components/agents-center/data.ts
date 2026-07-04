import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Code2,
  Cpu,
  Database,
  FileSearch,
  Gauge,
  Globe,
  Home,
  Library,
  MemoryStick,
  Mic,
  Monitor,
  PauseCircle,
  PlayCircle,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Terminal,
  Workflow,
  Zap,
} from "lucide-react";

export type AgentTone = "running" | "idle" | "error" | "healthy" | "warning" | "degraded" | "completed" | "queued" | "info";

export type AgentMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: AgentTone;
  icon: LucideIcon;
  data: number[];
};

export type AgentRecord = {
  name: string;
  version: string;
  description: string;
  category: string;
  status: AgentTone;
  healthTone: AgentTone;
  health: number;
  tasks: number;
  successRate: string;
  lastActivity: string;
  currentMission: string;
  cpu: string;
  memory: string;
  latency: string;
  owner: string;
  icon: LucideIcon;
};

export type PerformanceRecord = {
  agent: string;
  completedTasks: number;
  successRate: string;
  averageRuntime: string;
  latency: string;
  resourceUsage: string;
  health: number;
  status: AgentTone;
};

export type Capability = {
  label: string;
  supportingAgents: string;
  usageCount: string;
  icon: LucideIcon;
};

export type ActivityRecord = {
  label: string;
  detail: string;
  time: string;
  tone: AgentTone;
  icon: LucideIcon;
};

export type HealthMetric = {
  label: string;
  value: string;
  status: string;
  tone: AgentTone;
  data: number[];
  icon: LucideIcon;
};

export type Distribution = {
  label: string;
  value: number;
  tone: AgentTone;
};

export type DeploymentEvent = {
  label: string;
  detail: string;
  time: string;
  tone: AgentTone;
  icon: LucideIcon;
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot, active: true },
  { label: "Missions", href: "/command#missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain },
  { label: "Research", href: "/workspace", icon: Search },
  { label: "Computer Use", href: "/operator", icon: Monitor },
  { label: "Browser", href: "/operator", icon: Globe },
  { label: "Replay", href: "/replay", icon: Archive },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Activity },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const agentMetrics: AgentMetric[] = [
  { label: "Total Agents", value: "36", trend: "+8", status: "Ready", tone: "healthy", icon: Bot, data: [24, 26, 28, 27, 31, 32, 34, 35, 36] },
  { label: "Active Agents", value: "24", trend: "66.7% of total", status: "Running", tone: "running", icon: PlayCircle, data: [16, 18, 20, 19, 22, 21, 23, 24, 24] },
  { label: "Idle Agents", value: "6", trend: "16.7% of total", status: "Idle", tone: "idle", icon: Clock, data: [8, 7, 7, 6, 7, 6, 6, 5, 6] },
  { label: "Running Missions", value: "18", trend: "+12%", status: "Live", tone: "running", icon: Target, data: [11, 12, 14, 13, 15, 17, 16, 18, 18] },
  { label: "Average Health", value: "96%", trend: "+2.4%", status: "Healthy", tone: "healthy", icon: Gauge, data: [91, 92, 94, 93, 95, 96, 95, 96, 96] },
  { label: "Success Rate", value: "98.7%", trend: "+1.6%", status: "Stable", tone: "healthy", icon: CheckCircle2, data: [94, 95, 96, 95, 97, 98, 97, 99, 98.7] },
];

export const agents: AgentRecord[] = [
  { name: "Research Agent", version: "v2.1.4", description: "Web research and analysis", category: "Research", status: "running", healthTone: "healthy", health: 99, tasks: 128, successRate: "99.2%", lastActivity: "2m ago", currentMission: "Q2 Market Intelligence", cpu: "32%", memory: "61%", latency: "842ms", owner: "Alex Morgan", icon: FileSearch },
  { name: "Voice Agent", version: "v1.3.1", description: "Voice conversation and STT", category: "Voice", status: "running", healthTone: "healthy", health: 98, tasks: 96, successRate: "98.7%", lastActivity: "1m ago", currentMission: "Voice Insights Summary", cpu: "18%", memory: "42%", latency: "76ms", owner: "Alex Morgan", icon: Mic },
  { name: "Browser Agent", version: "v1.1.8", description: "Web browsing and automation", category: "Browser", status: "running", healthTone: "healthy", health: 97, tasks: 74, successRate: "97.3%", lastActivity: "30s ago", currentMission: "Competitor Data Crawl", cpu: "45%", memory: "55%", latency: "110ms", owner: "Nina Patel", icon: Globe },
  { name: "Computer Agent", version: "v1.0.9", description: "Desktop automation", category: "Computer Use", status: "running", healthTone: "healthy", health: 96, tasks: 58, successRate: "96.5%", lastActivity: "1m ago", currentMission: "Data Consolidation", cpu: "51%", memory: "63%", latency: "128ms", owner: "Alex Morgan", icon: Monitor },
  { name: "Memory Agent", version: "v1.2.2", description: "Memory indexing and retrieval", category: "Memory", status: "running", healthTone: "healthy", health: 99, tasks: 212, successRate: "99.1%", lastActivity: "10s ago", currentMission: "Knowledge Graph Update", cpu: "28%", memory: "57%", latency: "74ms", owner: "Priya Shah", icon: Database },
  { name: "Data Analyst Agent", version: "v1.0.5", description: "Data analysis and visualization", category: "Analytics", status: "idle", healthTone: "healthy", health: 100, tasks: 13, successRate: "100%", lastActivity: "5m ago", currentMission: "Standby", cpu: "8%", memory: "22%", latency: "64ms", owner: "Alex Morgan", icon: BarChart3 },
  { name: "Report Generation Agent", version: "v1.1.2", description: "Generate reports and docs", category: "Productivity", status: "running", healthTone: "healthy", health: 98, tasks: 47, successRate: "98.0%", lastActivity: "2m ago", currentMission: "Executive Brief Generation", cpu: "34%", memory: "46%", latency: "96ms", owner: "Nina Patel", icon: Library },
  { name: "Code Assistant Agent", version: "v1.0.3", description: "Code generation and review", category: "Developer", status: "error", healthTone: "degraded", health: 73, tasks: 5, successRate: "73.4%", lastActivity: "8m ago", currentMission: "Patch Review", cpu: "12%", memory: "31%", latency: "1.2s", owner: "Dev Platform", icon: Code2 },
  { name: "Scheduler Agent", version: "v1.0.1", description: "Task scheduling and triggers", category: "System", status: "running", healthTone: "healthy", health: 100, tasks: 32, successRate: "100%", lastActivity: "1m ago", currentMission: "Runtime Scheduling", cpu: "10%", memory: "18%", latency: "58ms", owner: "System", icon: Clock },
  { name: "Notification Agent", version: "v1.0.2", description: "Send notifications and alerts", category: "System", status: "running", healthTone: "healthy", health: 99, tasks: 81, successRate: "99.6%", lastActivity: "3m ago", currentMission: "Alert Delivery", cpu: "9%", memory: "19%", latency: "62ms", owner: "System", icon: Sparkles },
];


export const performance: PerformanceRecord[] = [
  { agent: "Memory Agent", completedTasks: 212, successRate: "99.1%", averageRuntime: "42s", latency: "74ms", resourceUsage: "42%", health: 99, status: "running" },
  { agent: "Research Agent", completedTasks: 128, successRate: "99.2%", averageRuntime: "2m 14s", latency: "842ms", resourceUsage: "46%", health: 99, status: "running" },
  { agent: "Voice Agent", completedTasks: 96, successRate: "98.7%", averageRuntime: "51s", latency: "76ms", resourceUsage: "30%", health: 98, status: "running" },
  { agent: "Browser Agent", completedTasks: 74, successRate: "97.3%", averageRuntime: "1m 32s", latency: "110ms", resourceUsage: "50%", health: 97, status: "running" },
  { agent: "Computer Agent", completedTasks: 58, successRate: "96.5%", averageRuntime: "2m 05s", latency: "128ms", resourceUsage: "57%", health: 96, status: "running" },
];

export const capabilities: Capability[] = [
  { label: "Research", supportingAgents: "4 agents", usageCount: "1.2K", icon: Search },
  { label: "Voice", supportingAgents: "2 agents", usageCount: "842", icon: Mic },
  { label: "Reasoning", supportingAgents: "8 agents", usageCount: "2.4K", icon: Brain },
  { label: "Planning", supportingAgents: "5 agents", usageCount: "928", icon: Workflow },
  { label: "Browser Automation", supportingAgents: "3 agents", usageCount: "612", icon: Globe },
  { label: "Computer Control", supportingAgents: "2 agents", usageCount: "438", icon: Monitor },
  { label: "Memory Retrieval", supportingAgents: "4 agents", usageCount: "3.1K", icon: Database },
  { label: "Code Generation", supportingAgents: "2 agents", usageCount: "326", icon: Code2 },
  { label: "Knowledge Search", supportingAgents: "6 agents", usageCount: "1.8K", icon: FileSearch },
  { label: "Document Analysis", supportingAgents: "5 agents", usageCount: "724", icon: Library },
];

export const liveActivity: ActivityRecord[] = [
  { label: "Research Agent started report generation", detail: "Executive Brief Generation", time: "2m ago", tone: "running", icon: FileSearch },
  { label: "Voice Agent accepted new session", detail: "Sales call transcript connected", time: "4m ago", tone: "info", icon: Mic },
  { label: "Browser Agent completed automation", detail: "Competitor crawl completed", time: "7m ago", tone: "completed", icon: Globe },
  { label: "Memory Agent indexed new documents", detail: "2.4K records added to vector store", time: "10m ago", tone: "healthy", icon: Database },
  { label: "Supervisor assigned mission", detail: "Q2 Market Intelligence routed", time: "12m ago", tone: "running", icon: Target },
];

export const healthMetrics: HealthMetric[] = [
  { label: "CPU", value: "32%", status: "Healthy", tone: "healthy", data: [20, 24, 22, 31, 27, 35, 31, 34, 32], icon: Cpu },
  { label: "Memory", value: "61%", status: "Warning", tone: "warning", data: [50, 55, 53, 58, 60, 62, 59, 61, 61], icon: MemoryStick },
  { label: "GPU", value: "24%", status: "Healthy", tone: "healthy", data: [24, 21, 20, 24, 22, 26, 23, 22, 24], icon: Sparkles },
  { label: "Network", value: "18%", status: "Healthy", tone: "healthy", data: [12, 14, 13, 19, 18, 21, 17, 18, 18], icon: Globe },
  { label: "Latency", value: "842ms", status: "Warning", tone: "warning", data: [760, 790, 810, 830, 815, 850, 842, 840, 842], icon: Gauge },
  { label: "Token Usage", value: "2.45K", status: "Healthy", tone: "healthy", data: [1.2, 1.4, 1.7, 1.9, 2.0, 2.2, 2.3, 2.4, 2.45], icon: Database },
];

export const typeDistribution: Distribution[] = [
  { label: "Research", value: 8, tone: "running" },
  { label: "Voice", value: 4, tone: "info" },
  { label: "Browser", value: 5, tone: "running" },
  { label: "Memory", value: 6, tone: "healthy" },
  { label: "System", value: 7, tone: "idle" },
  { label: "Governance", value: 6, tone: "warning" },
];

export const statusDistribution: Distribution[] = [
  { label: "Running", value: 24, tone: "running" },
  { label: "Idle", value: 6, tone: "idle" },
  { label: "Error", value: 2, tone: "error" },
  { label: "Updating", value: 4, tone: "warning" },
];

export const missionAllocation: Distribution[] = [
  { label: "Research", value: 34, tone: "running" },
  { label: "Voice", value: 18, tone: "info" },
  { label: "Browser", value: 22, tone: "running" },
  { label: "Computer", value: 16, tone: "healthy" },
  { label: "Governance", value: 10, tone: "warning" },
];

export const deploymentTimeline: DeploymentEvent[] = [
  { label: "Agent Created", detail: "Analytics Agent provisioned", time: "Today 09:12", tone: "completed", icon: Bot },
  { label: "Version Updated", detail: "Research Agent updated to v2.1.4", time: "Today 08:44", tone: "healthy", icon: RefreshCw },
  { label: "Configuration Changed", detail: "Voice Agent low-latency profile applied", time: "Yesterday", tone: "info", icon: Settings },
  { label: "Restarted", detail: "Computer Agent restarted worker pool", time: "Yesterday", tone: "warning", icon: PauseCircle },
  { label: "Scaled", detail: "Memory Agent replicas increased to 4", time: "Mon", tone: "running", icon: Terminal },
  { label: "Deployment Successful", detail: "Governance Agent deployed to production", time: "Mon", tone: "completed", icon: ShieldCheck },
];

