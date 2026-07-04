import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  CheckCircle2,
  Clock,
  Database,
  FileText,
  Gauge,
  Globe,
  HardDrive,
  Home,
  Inbox,
  Layers3,
  Mail,
  MemoryStick,
  Mic,
  Monitor,
  Network,
  Puzzle,
  RefreshCw,
  Search,
  Server,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  Zap,
} from "lucide-react";

export type MemoryTone = "active" | "indexed" | "processing" | "updating" | "archived" | "healthy" | "warning" | "info";

export type MemoryMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: MemoryTone;
  icon: LucideIcon;
  data: number[];
};

export type KnowledgeSource = {
  label: string;
  records: string;
  updated: string;
  health: string;
  icon: LucideIcon;
  tone: MemoryTone;
};

export type MemoryRecord = {
  title: string;
  description: string;
  type: string;
  source: string;
  category: string;
  indexed: string;
  size: string;
  lastAccessed: string;
  confidence: number;
  status: MemoryTone;
  icon: LucideIcon;
};

export type MemoryActivity = {
  label: string;
  detail: string;
  time: string;
  tone: MemoryTone;
  icon: LucideIcon;
};

export type UsageSlice = {
  label: string;
  value: number;
  amount: string;
  color: string;
};

export type PerformanceMetric = {
  label: string;
  value: string;
  trend: string;
  color: string;
  icon: LucideIcon;
  data: number[];
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Missions", href: "/missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain, active: true },
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

export const memoryMetrics: MemoryMetric[] = [
  { label: "Total Memories", value: "542,318", trend: "+12.4%", status: "Indexed", tone: "indexed", icon: Database, data: [420, 434, 448, 462, 471, 493, 511, 526, 542] },
  { label: "Total Size", value: "4.62 GB", trend: "+8.7%", status: "Healthy", tone: "healthy", icon: HardDrive, data: [3.1, 3.4, 3.6, 3.9, 4.1, 4.24, 4.4, 4.52, 4.62] },
  { label: "Embeddings", value: "8.91M", trend: "+15.3%", status: "Synced", tone: "indexed", icon: Network, data: [6.8, 7.1, 7.4, 7.8, 8.1, 8.3, 8.55, 8.7, 8.91] },
  { label: "Active Memories", value: "32,421", trend: "+9.1%", status: "Active", tone: "active", icon: CheckCircle2, data: [22, 24, 25, 26, 28, 29, 30, 31, 32] },
  { label: "Retrieval Accuracy", value: "98.9%", trend: "+2.1%", status: "Excellent", tone: "healthy", icon: Gauge, data: [94, 95, 96, 97, 97.2, 98, 98.4, 98.7, 98.9] },
  { label: "Today's Queries", value: "18,492", trend: "+6.8%", status: "Live", tone: "active", icon: Search, data: [9, 10, 11, 12, 12.5, 14, 15, 17, 18.4] },
];

export const knowledgeSources: KnowledgeSource[] = [
  { label: "Documents", records: "214K", updated: "2m ago", health: "99%", icon: FileText, tone: "healthy" },
  { label: "Conversations", records: "86K", updated: "8m ago", health: "98%", icon: Mic, tone: "active" },
  { label: "Web Research", records: "128K", updated: "15m ago", health: "97%", icon: Globe, tone: "indexed" },
  { label: "Internal Wiki", records: "42K", updated: "24m ago", health: "99%", icon: BookOpen, tone: "healthy" },
  { label: "Databases", records: "31K", updated: "32m ago", health: "96%", icon: Server, tone: "updating" },
  { label: "Policies", records: "9.8K", updated: "1h ago", health: "100%", icon: ShieldCheck, tone: "healthy" },
  { label: "Emails", records: "74K", updated: "2h ago", health: "94%", icon: Mail, tone: "warning" },
  { label: "Reports", records: "18K", updated: "3h ago", health: "98%", icon: Inbox, tone: "indexed" },
];

export const memoryRecords: MemoryRecord[] = [
  { title: "Q2 Market Intelligence Report", description: "Market analysis and key insights", type: "Document", source: "Research Agent", category: "Market Intel", indexed: "May 12, 10:30 AM", size: "2.4 MB", lastAccessed: "2m ago", confidence: 98, status: "active", icon: FileText },
  { title: "Competitor Pricing Strategy", description: "Pricing models and positioning", type: "Web Page", source: "Browser Agent", category: "Competitive", indexed: "May 12, 09:15 AM", size: "842 KB", lastAccessed: "15m ago", confidence: 92, status: "active", icon: Globe },
  { title: "Customer Feedback Summary", description: "User feedback and sentiment", type: "Document", source: "Memory Agent", category: "Voice of Customer", indexed: "May 11, 04:22 PM", size: "1.1 MB", lastAccessed: "1h ago", confidence: 89, status: "active", icon: FileText },
  { title: "Sales Call Transcript - ACME", description: "Call with ACME Corp stakeholders", type: "Transcript", source: "Voice Agent", category: "Sales", indexed: "May 11, 02:10 PM", size: "580 KB", lastAccessed: "2h ago", confidence: 86, status: "active", icon: Mic },
  { title: "Product Roadmap Q2", description: "Product roadmap and timeline", type: "Document", source: "Research Agent", category: "Product", indexed: "May 10, 11:45 AM", size: "3.2 MB", lastAccessed: "5h ago", confidence: 78, status: "archived", icon: FileText },
  { title: "Industry Trends 2024", description: "Latest industry trends and analysis", type: "Web Page", source: "Browser Agent", category: "Research", indexed: "May 10, 09:30 AM", size: "912 KB", lastAccessed: "1d ago", confidence: 75, status: "active", icon: Globe },
  { title: "Technical Architecture", description: "System architecture documentation", type: "Document", source: "Computer Agent", category: "Engineering", indexed: "May 9, 04:15 PM", size: "4.8 MB", lastAccessed: "2d ago", confidence: 71, status: "archived", icon: Layers3 },
  { title: "Meeting Notes - Product Team", description: "Weekly product team meeting", type: "Document", source: "Memory Agent", category: "Operations", indexed: "May 9, 11:20 AM", size: "420 KB", lastAccessed: "2d ago", confidence: 68, status: "active", icon: FileText },
];

export const usageData: UsageSlice[] = [
  { label: "Documents", value: 46, amount: "2.14 GB", color: "#38B88A" },
  { label: "Web Pages", value: 28, amount: "1.28 GB", color: "#72D1A9" },
  { label: "Transcripts", value: 19, amount: "0.86 GB", color: "#3B82F6" },
  { label: "Others", value: 7, amount: "0.34 GB", color: "#CBD5E1" },
];

export const recentActivity: MemoryActivity[] = [
  { label: "Market Intelligence Report", detail: "Added by Research Agent", time: "2m ago", tone: "indexed", icon: FileText },
  { label: "Competitor Analysis Data", detail: "Added by Browser Agent", time: "15m ago", tone: "active", icon: Database },
  { label: "Voice Call Transcript", detail: "Added by Voice Agent", time: "1h ago", tone: "info", icon: Mic },
  { label: "Customer Survey Results", detail: "Added by Memory Agent", time: "2h ago", tone: "processing", icon: RefreshCw },
  { label: "Product Specs Document", detail: "Added by Computer Agent", time: "5h ago", tone: "indexed", icon: FileText },
];

export const retrievalTimeline: MemoryActivity[] = [
  { label: "Query Received", detail: "Market intelligence context requested", time: "10:30:11 AM", tone: "active", icon: Search },
  { label: "Embedding Generated", detail: "Vector generated with 1,536 dimensions", time: "10:30:12 AM", tone: "indexed", icon: Network },
  { label: "Knowledge Retrieved", detail: "18 relevant memory objects found", time: "10:30:12 AM", tone: "healthy", icon: Database },
  { label: "Context Built", detail: "Sources ranked and deduplicated", time: "10:30:13 AM", tone: "processing", icon: Layers3 },
  { label: "Response Generated", detail: "Executive answer grounded with citations", time: "10:30:14 AM", tone: "active", icon: Sparkles },
  { label: "Memory Updated", detail: "Interaction stored for future retrieval", time: "10:30:16 AM", tone: "indexed", icon: CheckCircle2 },
];

export const performanceMetrics: PerformanceMetric[] = [
  { label: "Retrieval Accuracy", value: "98.9%", trend: "+2.1%", color: "#38B88A", icon: Gauge, data: [93, 94, 95, 96, 96.8, 97.4, 98.2, 98.7, 98.9] },
  { label: "Avg Retrieval Time", value: "84ms", trend: "-12ms", color: "#3B82F6", icon: Clock, data: [130, 122, 116, 108, 101, 96, 91, 87, 84] },
  { label: "Embedding Latency", value: "41ms", trend: "-8ms", color: "#8B5CF6", icon: Network, data: [64, 58, 55, 51, 48, 45, 43, 42, 41] },
  { label: "Memory Growth", value: "12.4%", trend: "+1.9%", color: "#38B88A", icon: MemoryStick, data: [4, 5, 6, 6.4, 7.2, 8.9, 9.8, 11.2, 12.4] },
  { label: "Search Volume", value: "18.4K", trend: "+6.8%", color: "#F59E0B", icon: Search, data: [10, 11, 11.8, 12.2, 13.7, 14.8, 16.1, 17.3, 18.4] },
  { label: "Knowledge Coverage", value: "94%", trend: "+3.4%", color: "#38B88A", icon: ShieldCheck, data: [82, 85, 87, 88, 90, 91, 92, 93, 94] },
];

export const relationshipNodes = [
  { label: "Documents", x: 48, y: 18, icon: FileText },
  { label: "Entities", x: 25, y: 42, icon: Network },
  { label: "People", x: 72, y: 42, icon: Bot },
  { label: "Projects", x: 48, y: 62, icon: Layers3 },
  { label: "Policies", x: 27, y: 78, icon: ShieldCheck },
  { label: "Departments", x: 70, y: 78, icon: Server },
];

export const recentSearches = ["Q2 market risks", "enterprise security policy", "browser automation costs"];
export const suggestedQueries = ["Summarize Q2 competitor insights", "Find governance-approved pricing sources", "Show memory used by Research Agent"];
export const popularKnowledge = ["Technical architecture", "SOC 2 controls", "Product roadmap Q2"];

export const memoryInsight =
  "CortexPrime indexed 2,846 new knowledge objects today. Retrieval accuracy improved to 98.9%, while document indexing latency decreased by 12%. Most requested knowledge came from internal engineering documentation.";
