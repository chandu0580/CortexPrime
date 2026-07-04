import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileText,
  Filter,
  Globe,
  Home,
  ListRestart,
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
  TrendingUp,
  TriangleAlert,
  Workflow,
  Wrench,
  Zap,
} from "lucide-react";

export type ReplayTone =
  | "completed"
  | "running"
  | "failed"
  | "warning"
  | "info"
  | "queued";

export type ReplayMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: ReplayTone;
  icon: LucideIcon;
  data: number[];
};

export type ReplaySession = {
  id: string;
  subtitle: string;
  mission: string;
  agent: string;
  startedAt: string;
  duration: string;
  status: ReplayTone;
  actions: string;
  accent: string;
};

export type TimelineStep = {
  time: string;
  title: string;
  detail: string;
  tone: ReplayTone;
  icon: LucideIcon;
};

export type ExecutionEvent = {
  label: string;
  agent: string;
  time: string;
  duration: string;
  tone: ReplayTone;
  icon: LucideIcon;
};

export type ToolExecution = {
  tool: string;
  input: string;
  output: string;
  duration: string;
  status: ReplayTone;
};

export type InsightCard = {
  title: string;
  summary: string;
  tone: ReplayTone;
};

export type SystemEvent = {
  label: string;
  time: string;
  tone: ReplayTone;
  icon: LucideIcon;
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Missions", href: "/missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain },
  { label: "Research", href: "/workspace", icon: Search },
  { label: "Computer Use", href: "/operator", icon: Monitor },
  { label: "Browser", href: "/browser", icon: Globe },
  { label: "Replay", href: "/replay", icon: ListRestart, active: true },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Activity },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const metrics: ReplayMetric[] = [
  { label: "Total Sessions", value: "248", trend: "+18.6%", status: "Recorded", tone: "completed", icon: Archive, data: [182, 188, 194, 201, 214, 221, 232, 241, 248] },
  { label: "Total Actions", value: "12,842", trend: "+22.4%", status: "Tracked", tone: "completed", icon: Workflow, data: [8800, 9310, 9720, 10140, 10810, 11390, 11870, 12320, 12842] },
  { label: "Avg. Session Duration", value: "18m 42s", trend: "+9.3%", status: "Stable", tone: "info", icon: Clock3, data: [12, 13, 14.5, 15.2, 16.1, 16.8, 17.4, 18.0, 18.7] },
  { label: "Success Rate", value: "96.3%", trend: "+3.7%", status: "Trusted", tone: "completed", icon: TrendingUp, data: [88, 89, 91, 92, 93.1, 94.2, 95.1, 95.8, 96.3] },
  { label: "Errors", value: "52", trend: "-12.1%", status: "Lower", tone: "failed", icon: TriangleAlert, data: [86, 81, 77, 71, 68, 63, 59, 55, 52] },
];

export const sessions: ReplaySession[] = [
  { id: "#7821", subtitle: "Q2 Market Intelligence", mission: "Market Research", agent: "Research Agent", startedAt: "May 12, 2024 10:30 AM", duration: "24m 18s", status: "completed", actions: "1,248", accent: "#38B88A" },
  { id: "#7819", subtitle: "Competitor Analysis", mission: "Competitor Landscape", agent: "Data Analyst", startedAt: "May 12, 2024 09:45 AM", duration: "18m 32s", status: "completed", actions: "842", accent: "#3B82F6" },
  { id: "#7818", subtitle: "Industry Report", mission: "Industry Research", agent: "Insight Agent", startedAt: "May 12, 2024 08:20 AM", duration: "32m 11s", status: "completed", actions: "1,632", accent: "#8B5CF6" },
  { id: "#7817", subtitle: "Pricing Strategy", mission: "Pricing Analysis", agent: "Finance Agent", startedAt: "May 11, 2024 04:15 PM", duration: "15m 04s", status: "failed", actions: "512", accent: "#EF4444" },
  { id: "#7816", subtitle: "Customer Insights", mission: "Customer Research", agent: "Data Analyst", startedAt: "May 11, 2024 02:10 PM", duration: "21m 47s", status: "completed", actions: "1,103", accent: "#38B88A" },
  { id: "#7815", subtitle: "Market Trends", mission: "Market Research", agent: "Research Agent", startedAt: "May 11, 2024 11:05 AM", duration: "27m 36s", status: "completed", actions: "1,478", accent: "#38B88A" },
  { id: "#7814", subtitle: "Report Generation", mission: "Report Generation", agent: "Report Agent", startedAt: "May 10, 2024 05:40 PM", duration: "10m 22s", status: "completed", actions: "432", accent: "#3B82F6" },
  { id: "#7813", subtitle: "Data Collection", mission: "Data Collection", agent: "Browser Agent", startedAt: "May 10, 2024 03:00 PM", duration: "12m 09s", status: "completed", actions: "635", accent: "#38B88A" },
];

export const replayTimeline: TimelineStep[] = [
  { time: "10:30 AM", title: "Session Started", detail: "Research Agent initialized session", tone: "completed", icon: PlayCircle },
  { time: "10:31 AM", title: "Browse Website", detail: "Visited bloomberg.com", tone: "completed", icon: Globe },
  { time: "10:34 AM", title: "Extract Data", detail: "Extracted market indices data", tone: "completed", icon: Database },
  { time: "10:37 AM", title: "Search Competitors", detail: "Searched for competitor financial data", tone: "completed", icon: Search },
  { time: "10:42 AM", title: "Analyze Data", detail: "Analyzed market trends", tone: "completed", icon: BarChart3 },
  { time: "10:48 AM", title: "Generate Insight", detail: "Generated key insights", tone: "completed", icon: Sparkles },
  { time: "10:52 AM", title: "Create Report", detail: "Generated report draft", tone: "completed", icon: FileText },
  { time: "10:54 AM", title: "Session Completed", detail: "Session completed successfully", tone: "completed", icon: CheckCircle2 },
];

export const executionEvents: ExecutionEvent[] = [
  { label: "Mission Created", agent: "Supervisor", time: "10:30:02", duration: "1.2s", tone: "completed", icon: PlayCircle },
  { label: "Planner Started", agent: "Research Agent", time: "10:30:04", duration: "2.9s", tone: "completed", icon: Workflow },
  { label: "Memory Retrieved", agent: "Memory Agent", time: "10:30:09", duration: "1.6s", tone: "completed", icon: MemoryStick },
  { label: "Browser Opened", agent: "Browser Agent", time: "10:31:12", duration: "3.4s", tone: "completed", icon: Globe },
  { label: "Research Completed", agent: "Research Agent", time: "10:41:16", duration: "6.8s", tone: "completed", icon: Search },
  { label: "Voice Generated", agent: "Voice Agent", time: "10:47:42", duration: "2.7s", tone: "completed", icon: Mic },
  { label: "Final Response", agent: "Supervisor", time: "10:53:55", duration: "4.1s", tone: "completed", icon: Sparkles },
  { label: "Mission Finished", agent: "Supervisor", time: "10:54:18", duration: "0.8s", tone: "completed", icon: CheckCircle2 },
];

export const toolExecutions: ToolExecution[] = [
  { tool: "Browser", input: "Open bloomberg.com/markets", output: "Loaded markets dashboard", duration: "2.3s", status: "completed" },
  { tool: "Memory Search", input: "Q2 market trends", output: "18 relevant memory items", duration: "1.1s", status: "completed" },
  { tool: "Research", input: "Competitor financial movement", output: "Structured market summary", duration: "6.8s", status: "completed" },
  { tool: "Voice", input: "Generate spoken summary", output: "Audio clip synthesized", duration: "2.7s", status: "completed" },
  { tool: "Computer Use", input: "Export chart screenshot", output: "Saved replay artifact", duration: "3.4s", status: "completed" },
  { tool: "Analytics", input: "Aggregate market metrics", output: "Charts rendered", duration: "1.9s", status: "completed" },
  { tool: "Governance", input: "Validate source policy", output: "No violations found", duration: "0.9s", status: "completed" },
];

export const insights: InsightCard[] = [
  { title: "Execution Summary", summary: "Replay completed 1,248 actions across browser, memory, and analytics tooling without intervention.", tone: "completed" },
  { title: "Slowest Step", summary: "Competitor search synthesis consumed the highest latency at 6.8 seconds.", tone: "warning" },
  { title: "Most Expensive Tool", summary: "Browser extraction contributed the highest token and compute usage in this replay.", tone: "info" },
  { title: "Failure Point", summary: "No hard failure detected in this replay session.", tone: "completed" },
  { title: "Optimization Suggestion", summary: "Cache market context and prefetch top competitor filings to reduce startup latency.", tone: "info" },
  { title: "Overall Confidence", summary: "Replay quality remains high with grounded outputs and clean tool sequencing.", tone: "completed" },
];

export const analyticsCards = [
  { label: "Mission Duration", value: "24m 18s", trend: "-6.2%", data: [33, 31, 30, 28, 27, 26, 25, 24.5, 24.3] },
  { label: "Tool Usage", value: "7 tools", trend: "+2", data: [3, 4, 4, 5, 5, 6, 6, 7, 7] },
  { label: "Latency", value: "184ms", trend: "-14ms", data: [260, 248, 236, 224, 213, 205, 197, 190, 184] },
  { label: "Success Rate", value: "96.3%", trend: "+3.7%", data: [88, 89, 90, 92, 93, 94, 95, 95.6, 96.3] },
];

export const systemEvents: SystemEvent[] = [
  { label: "Mission Started", time: "10:30:02", tone: "completed", icon: PlayCircle },
  { label: "Browser Opened", time: "10:31:12", tone: "completed", icon: Globe },
  { label: "Memory Retrieved", time: "10:30:09", tone: "completed", icon: MemoryStick },
  { label: "Tool Executed", time: "10:41:16", tone: "completed", icon: Wrench },
  { label: "Voice Response", time: "10:47:42", tone: "completed", icon: Mic },
  { label: "Agent Finished", time: "10:53:55", tone: "completed", icon: Bot },
  { label: "Mission Archived", time: "10:54:20", tone: "info", icon: Archive },
];

export const comparison = [
  { label: "Execution Time", left: "24m 18s", right: "18m 32s", delta: "+5m 46s" },
  { label: "Token Usage", left: "182K", right: "141K", delta: "+41K" },
  { label: "Latency", left: "184ms", right: "166ms", delta: "+18ms" },
  { label: "Tools Used", left: "7", right: "6", delta: "+1" },
  { label: "Mission Outcome", left: "Completed", right: "Completed", delta: "Same" },
  { label: "Success Rate", left: "96.3%", right: "98.1%", delta: "-1.8%" },
];

export const replayInsight =
  "Today, CortexPrime replayed 248 mission sessions, traced 12,842 actions, and maintained a 96.3% replay success rate. Most investigations focused on browser research flows, memory retrieval behavior, and final-response latency.";
