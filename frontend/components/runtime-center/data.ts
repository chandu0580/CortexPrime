import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Gauge,
  Globe,
  Home,
  Layers,
  MemoryStick,
  Mic,
  Monitor,
  PauseCircle,
  Puzzle,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Terminal,
  Zap,
} from "lucide-react";

export type RuntimeTone =
  | "running"
  | "queued"
  | "waiting"
  | "completed"
  | "failed"
  | "searching"
  | "thinking"
  | "executing"
  | "healthy"
  | "warning"
  | "idle"
  | "info";

export type RuntimeMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: RuntimeTone;
  icon: LucideIcon;
  data: number[];
};

export type RuntimeMission = {
  name: string;
  id: string;
  agent: string;
  priority: "High" | "Medium" | "Low";
  step: string;
  progress: number;
  runtime: string;
  status: RuntimeTone;
};

export type RuntimeAgent = {
  name: string;
  mission: string;
  cpu: string;
  memory: string;
  latency: string;
  health: number;
  status: RuntimeTone;
  icon: LucideIcon;
};

export type TimelineEvent = {
  label: string;
  timestamp: string;
  description: string;
  icon: LucideIcon;
  tone: RuntimeTone;
};

export type RuntimeHealth = {
  label: string;
  status: string;
  latency: string;
  health: number;
  tone: RuntimeTone;
};

export type QueueItem = {
  label: string;
  value: number;
  tone: RuntimeTone;
};

export type ResourceMetric = {
  label: string;
  value: string;
  color: string;
  icon: LucideIcon;
  data: number[];
};

export type RuntimeEvent = {
  label: string;
  detail: string;
  time: string;
  icon: LucideIcon;
  tone: RuntimeTone;
};

export type ModelUsage = {
  label: string;
  value: string;
  share: number;
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap, active: true },
  { label: "Agents", href: "/agents", icon: Bot },
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

export const runtimeMetrics: RuntimeMetric[] = [
  { label: "Running Missions", value: "24", trend: "+14%", status: "Live", tone: "running", icon: Zap, data: [18, 21, 20, 24, 22, 27, 25, 29, 24] },
  { label: "Queued Missions", value: "12", trend: "+5.2%", status: "Queued", tone: "queued", icon: Clock, data: [10, 11, 14, 13, 12, 15, 12, 13, 12] },
  { label: "Completed Today", value: "94", trend: "+8.1%", status: "Complete", tone: "completed", icon: CheckCircle2, data: [55, 62, 66, 71, 78, 84, 88, 91, 94] },
  { label: "Failed Tasks", value: "3", trend: "-2.4%", status: "Watch", tone: "warning", icon: PauseCircle, data: [8, 7, 6, 5, 6, 4, 4, 3, 3] },
  { label: "Average Runtime", value: "3m 42s", trend: "-6.8%", status: "Improved", tone: "healthy", icon: Gauge, data: [260, 252, 246, 239, 231, 225, 222, 220, 222] },
  { label: "Success Rate", value: "98.7%", trend: "+1.6%", status: "Healthy", tone: "healthy", icon: ShieldCheck, data: [94, 95, 96, 95, 97, 98, 97, 99, 98.7] },
];

export const runtimeMissions: RuntimeMission[] = [
  { name: "Market Research Analysis", id: "MIS-2401", agent: "Research Agent", priority: "High", step: "Synthesizing sources", progress: 67, runtime: "2m 34s", status: "running" },
  { name: "Competitor Data Crawl", id: "MIS-2402", agent: "Browser Agent", priority: "Medium", step: "Crawling webpages", progress: 42, runtime: "1m 12s", status: "searching" },
  { name: "Financial Report Analysis", id: "MIS-2403", agent: "Research Agent", priority: "High", step: "Extracting tables", progress: 78, runtime: "3m 45s", status: "executing" },
  { name: "Customer Sentiment Scan", id: "MIS-2404", agent: "Research Agent", priority: "Medium", step: "Classifying feedback", progress: 55, runtime: "1m 58s", status: "thinking" },
  { name: "Voice Insights Summary", id: "MIS-2405", agent: "Voice Agent", priority: "Low", step: "Transcribing audio", progress: 30, runtime: "45s", status: "running" },
  { name: "Data Consolidation", id: "MIS-2406", agent: "Computer Use Agent", priority: "Medium", step: "Merging datasets", progress: 65, runtime: "2m 10s", status: "executing" },
  { name: "Knowledge Graph Update", id: "MIS-2407", agent: "Memory Agent", priority: "Medium", step: "Indexing entities", progress: 40, runtime: "1m 05s", status: "waiting" },
  { name: "Executive Brief Generation", id: "MIS-2408", agent: "Analytics Agent", priority: "High", step: "Finalizing brief", progress: 90, runtime: "3m 22s", status: "running" },
  { name: "Data Visualization Build", id: "MIS-2409", agent: "Computer Use Agent", priority: "Low", step: "Queued for worker", progress: 0, runtime: "-", status: "queued" },
  { name: "Mission Orchestration", id: "MIS-2410", agent: "Supervisor", priority: "High", step: "Supervisor handoff", progress: 0, runtime: "-", status: "queued" },
];

export const pipelineStages = [
  { label: "Queued", tone: "completed" as RuntimeTone },
  { label: "Planning", tone: "completed" as RuntimeTone },
  { label: "Reasoning", tone: "running" as RuntimeTone },
  { label: "Tool Execution", tone: "executing" as RuntimeTone },
  { label: "Validation", tone: "waiting" as RuntimeTone },
  { label: "Completed", tone: "queued" as RuntimeTone },
];

export const runningAgents: RuntimeAgent[] = [
  { name: "Research Agent", mission: "Market Research Analysis", cpu: "32%", memory: "48%", latency: "91ms", health: 98, status: "running", icon: Search },
  { name: "Voice Agent", mission: "Voice Insights Summary", cpu: "18%", memory: "41%", latency: "82ms", health: 96, status: "running", icon: Mic },
  { name: "Browser Agent", mission: "Competitor Data Crawl", cpu: "45%", memory: "55%", latency: "110ms", health: 94, status: "searching", icon: Globe },
  { name: "Computer Use Agent", mission: "Data Consolidation", cpu: "51%", memory: "63%", latency: "128ms", health: 91, status: "executing", icon: Monitor },
  { name: "Memory Agent", mission: "Knowledge Graph Update", cpu: "28%", memory: "57%", latency: "74ms", health: 97, status: "waiting", icon: Database },
  { name: "Analytics Agent", mission: "Executive Brief Generation", cpu: "37%", memory: "46%", latency: "96ms", health: 95, status: "thinking", icon: BarChart3 },
];

export const executionTimeline: TimelineEvent[] = [
  { label: "Mission Created", timestamp: "10:30:15 AM", description: "Market Research Analysis opened by Supervisor", icon: Target, tone: "completed" },
  { label: "Planning Started", timestamp: "10:30:21 AM", description: "Research plan generated and approved", icon: Layers, tone: "completed" },
  { label: "Research Running", timestamp: "10:30:44 AM", description: "Research Agent gathering market signals", icon: Search, tone: "running" },
  { label: "Browser Opened", timestamp: "10:31:02 AM", description: "Browser Agent completed webpage crawl", icon: Globe, tone: "searching" },
  { label: "Memory Retrieved", timestamp: "10:31:27 AM", description: "Memory Agent retrieved 2.4K relevant records", icon: Database, tone: "healthy" },
  { label: "Response Generated", timestamp: "10:32:04 AM", description: "Supervisor generated executive response draft", icon: Sparkles, tone: "thinking" },
  { label: "Mission Completed", timestamp: "Pending", description: "Waiting for validation stage to complete", icon: CheckCircle2, tone: "waiting" },
];

export const runtimeHealth: RuntimeHealth[] = [
  { label: "Voice Runtime", status: "Healthy", latency: "82ms", health: 96, tone: "healthy" },
  { label: "Memory Runtime", status: "Healthy", latency: "74ms", health: 98, tone: "healthy" },
  { label: "Browser Runtime", status: "Stable", latency: "110ms", health: 94, tone: "running" },
  { label: "Research Runtime", status: "Healthy", latency: "91ms", health: 97, tone: "healthy" },
  { label: "Queue", status: "Watching", latency: "12 jobs", health: 88, tone: "warning" },
  { label: "Worker Pool", status: "Healthy", latency: "24 active", health: 95, tone: "healthy" },
];

export const queueOverview: QueueItem[] = [
  { label: "Waiting", value: 18, tone: "waiting" },
  { label: "Running", value: 24, tone: "running" },
  { label: "Completed", value: 94, tone: "completed" },
  { label: "Failed", value: 3, tone: "failed" },
  { label: "Retry", value: 6, tone: "warning" },
];

export const resources: ResourceMetric[] = [
  { label: "CPU", value: "32%", color: "#38B88A", icon: Cpu, data: [20, 24, 22, 31, 27, 35, 31, 34, 32] },
  { label: "Memory", value: "61%", color: "#3B82F6", icon: MemoryStick, data: [50, 55, 53, 58, 60, 62, 59, 61, 61] },
  { label: "GPU", value: "24%", color: "#8B5CF6", icon: Sparkles, data: [24, 21, 20, 24, 22, 26, 23, 22, 24] },
  { label: "Token Usage", value: "2.45M", color: "#38B88A", icon: Database, data: [1.2, 1.4, 1.7, 1.9, 2.0, 2.2, 2.3, 2.4, 2.45] },
  { label: "Requests", value: "18K", color: "#F59E0B", icon: Terminal, data: [11, 13, 12, 16, 15, 19, 17, 18, 18] },
  { label: "Worker Load", value: "72%", color: "#38B88A", icon: Gauge, data: [58, 61, 64, 67, 70, 69, 73, 71, 72] },
];

export const runtimeEvents: RuntimeEvent[] = [
  { label: "Mission Started", detail: "Research Agent started Market Research Analysis", time: "10:30:15 AM", icon: Search, tone: "running" },
  { label: "Mission Completed", detail: "Browser Agent completed webpage crawl", time: "10:30:02 AM", icon: CheckCircle2, tone: "completed" },
  { label: "Agent Restarted", detail: "Computer Use Agent refreshed worker session", time: "10:29:51 AM", icon: Monitor, tone: "warning" },
  { label: "Voice Session Connected", detail: "Voice Agent transcribed new conversation", time: "10:29:33 AM", icon: Mic, tone: "info" },
  { label: "Memory Indexed", detail: "Memory Agent indexed 2.4K new documents", time: "10:29:21 AM", icon: Database, tone: "healthy" },
  { label: "Browser Opened", detail: "Browser runtime opened competitor source", time: "10:28:58 AM", icon: Globe, tone: "searching" },
  { label: "Research Finished", detail: "Research Agent summarized source pack", time: "10:28:41 AM", icon: Brain, tone: "completed" },
];

export const modelUsage: ModelUsage[] = [
  { label: "GPT-4o", value: "1.25M", share: 50 },
  { label: "Claude 3.5 Sonnet", value: "620K", share: 25 },
  { label: "Gemini 1.5 Pro", value: "320K", share: 13 },
  { label: "Llama 3 70B", value: "180K", share: 7 },
  { label: "Mistral Large", value: "100K", share: 5 },
];

export const runtimeFlowNodes = [
  { label: "Trigger", detail: "Schedule", x: 8, y: 48 },
  { label: "Supervisor", detail: "Cortex Supervisor", x: 31, y: 48 },
  { label: "Research Agent", detail: "Running", x: 54, y: 20 },
  { label: "Browser Agent", detail: "Running", x: 54, y: 39 },
  { label: "Memory Agent", detail: "Running", x: 54, y: 58 },
  { label: "Computer Agent", detail: "Running", x: 54, y: 77 },
  { label: "Output", detail: "Generating", x: 81, y: 48 },
];
