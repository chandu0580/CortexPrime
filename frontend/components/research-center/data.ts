import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  BookOpen,
  Bot,
  Brain,
  Briefcase,
  CheckCircle2,
  Compass,
  Database,
  Eye,
  FileSearch,
  FileText,
  Filter,
  FlaskConical,
  Globe,
  Home,
  LayoutTemplate,
  Lightbulb,
  Mic,
  Monitor,
  Newspaper,
  Puzzle,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
  Upload,
  Workflow,
  Zap,
} from "lucide-react";

export type ResearchTone =
  | "planning"
  | "running"
  | "searching"
  | "reading"
  | "analyzing"
  | "summarizing"
  | "reviewing"
  | "completed"
  | "queued"
  | "warning"
  | "info";

export type ResearchMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: ResearchTone;
  icon: LucideIcon;
  data: number[];
};

export type ResearchProject = {
  title: string;
  summary: string;
  goal: string;
  agent: string;
  status: ResearchTone;
  progress: number;
  updated: string;
  icon: LucideIcon;
  accent: string;
};

export type ResearchAgent = {
  name: string;
  specialty: string;
  tasks: number;
  status: ResearchTone;
  icon: LucideIcon;
  accent: string;
};

export type ResearchActivity = {
  label: string;
  detail: string;
  time: string;
  tone: ResearchTone;
  icon: LucideIcon;
};

export type MissionCard = {
  title: string;
  agent: string;
  phase: string;
  eta: string;
  confidence: string;
  progress: number;
  status: ResearchTone;
};

export type SourceRecord = {
  source: string;
  type: string;
  domain: string;
  credibility: string;
  published: string;
  status: ResearchTone;
  icon: LucideIcon;
};

export type InsightCard = {
  title: string;
  summary: string;
  confidence: string;
  sources: string;
  icon: LucideIcon;
};

export type TopicMetric = {
  label: string;
  value: number;
  color: string;
};

export const sidebarItems = [
  { label: "Dashboard", href: "/command", icon: Home },
  { label: "Runtime", href: "/runtime", icon: Zap },
  { label: "Agents", href: "/agents", icon: Bot },
  { label: "Missions", href: "/missions", icon: Target },
  { label: "Voice", href: "/voice", icon: Mic },
  { label: "Memory", href: "/memory", icon: Brain },
  { label: "Research", href: "/workspace", icon: Search, active: true },
  { label: "Computer Use", href: "/operator", icon: Monitor },
  { label: "Browser", href: "/operator", icon: Globe },
  { label: "Replay", href: "/replay", icon: Archive },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Activity },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const researchMetrics: ResearchMetric[] = [
  { label: "Active Research", value: "18", trend: "+12.5%", status: "Running", tone: "running", icon: Search, data: [8, 9, 10, 9, 12, 13, 14, 15, 18] },
  { label: "Completed Reports", value: "126", trend: "+18.3%", status: "Completed", tone: "completed", icon: CheckCircle2, data: [84, 92, 96, 101, 109, 113, 118, 122, 126] },
  { label: "Sources Indexed", value: "24.6K", trend: "+23.1%", status: "Healthy", tone: "running", icon: Database, data: [12, 13, 14.5, 16, 18, 20, 21.8, 23.2, 24.6] },
  { label: "Insights Generated", value: "312", trend: "+15.8%", status: "Live", tone: "running", icon: Lightbulb, data: [180, 196, 211, 224, 246, 263, 281, 299, 312] },
  { label: "Avg. Confidence", value: "87%", trend: "+6.2%", status: "Trusted", tone: "reviewing", icon: Compass, data: [72, 74, 76, 79, 81, 83, 84, 86, 87] },
  { label: "Today's Tasks", value: "64", trend: "+9.4%", status: "Queued", tone: "queued", icon: Briefcase, data: [32, 36, 38, 41, 46, 51, 55, 59, 64] },
];

export const suggestedTopics = [
  "Analyze Q2 semiconductor supplier risks",
  "Compare enterprise agent platforms in regulated industries",
  "Summarize new AI governance rules for financial services",
];

export const recentResearch = ["Q2 Market Intelligence", "AI Industry Report 2024", "Customer Sentiment Study"];
export const pinnedResearch = ["Regulatory Updates", "Technology Radar", "Competitor Landscape"];
export const quickTemplates = ["Market Map", "Executive Brief", "Policy Watch", "Trend Scan"];

export const researchProjects: ResearchProject[] = [
  { title: "Q2 Market Intelligence", summary: "Market overview and key trends", goal: "Analyze market trends and competitor movements", agent: "Research Agent", status: "running", progress: 65, updated: "2m ago", icon: FileSearch, accent: "#38B88A" },
  { title: "Competitor Landscape", summary: "Competitor analysis and positioning", goal: "Compare product features, pricing and positioning", agent: "Analyzer Agent", status: "running", progress: 45, updated: "15m ago", icon: Compass, accent: "#8B5CF6" },
  { title: "AI Industry Report 2024", summary: "AI industry trends and outlook", goal: "Identify key AI trends and opportunities", agent: "Insight Agent", status: "completed", progress: 100, updated: "1h ago", icon: Newspaper, accent: "#3B82F6" },
  { title: "Customer Sentiment Study", summary: "Customer feedback analysis", goal: "Analyze customer sentiment across channels", agent: "Sentiment Agent", status: "completed", progress: 100, updated: "3h ago", icon: Mic, accent: "#38B88A" },
  { title: "Investment Opportunities", summary: "High potential investment areas", goal: "Find emerging startups and investment signals", agent: "Research Agent", status: "reading", progress: 30, updated: "4h ago", icon: TrendingUp, accent: "#8B5CF6" },
  { title: "Regulatory Updates", summary: "Track regulatory and compliance", goal: "Monitor regulatory changes and updates", agent: "Monitor Agent", status: "queued", progress: 0, updated: "-", icon: ShieldCheck, accent: "#F59E0B" },
  { title: "Technology Radar", summary: "Emerging technologies watch", goal: "Track emerging technologies and innovations", agent: "Insight Agent", status: "searching", progress: 20, updated: "6h ago", icon: Sparkles, accent: "#3B82F6" },
];

export const researchAgents: ResearchAgent[] = [
  { name: "Research Agent", specialty: "Web and data discovery", tasks: 8, status: "running", icon: Search, accent: "#38B88A" },
  { name: "Analyzer Agent", specialty: "Data extraction and analysis", tasks: 6, status: "running", icon: FlaskConical, accent: "#8B5CF6" },
  { name: "Insight Agent", specialty: "Insight generation", tasks: 7, status: "running", icon: Lightbulb, accent: "#3B82F6" },
  { name: "Monitor Agent", specialty: "Continuous monitoring", tasks: 4, status: "running", icon: Eye, accent: "#F59E0B" },
  { name: "Sentiment Agent", specialty: "Sentiment analysis", tasks: 3, status: "running", icon: Mic, accent: "#38B88A" },
];

export const recentActivity: ResearchActivity[] = [
  { label: "Q2 Market Intelligence research started", detail: "Research Agent initialized mission scope", time: "2m ago", tone: "running", icon: Search },
  { label: "25 new sources discovered", detail: "Source discovery completed across 12 domains", time: "8m ago", tone: "searching", icon: Globe },
  { label: "Competitor data analysis completed", detail: "Analyzer Agent finished comparison pass", time: "15m ago", tone: "completed", icon: CheckCircle2 },
  { label: "AI Industry Report 2024 completed", detail: "Executive brief generated and stored", time: "1h ago", tone: "completed", icon: FileText },
  { label: "New insight generated: Market Growth", detail: "Trend confidence crossed 92 percent", time: "2h ago", tone: "reviewing", icon: Lightbulb },
];

export const missionCards: MissionCard[] = [
  { title: "Market Expansion Signals", agent: "Research Agent", phase: "Analyzing", eta: "12 min", confidence: "91%", progress: 72, status: "analyzing" },
  { title: "Healthcare AI Compliance Watch", agent: "Monitor Agent", phase: "Reading", eta: "18 min", confidence: "88%", progress: 54, status: "reading" },
  { title: "Cloud Vendor Pricing Review", agent: "Analyzer Agent", phase: "Summarizing", eta: "7 min", confidence: "94%", progress: 83, status: "summarizing" },
];

export const pipelineStages = [
  { label: "Planning", tone: "completed" as ResearchTone },
  { label: "Source Discovery", tone: "completed" as ResearchTone },
  { label: "Web Search", tone: "running" as ResearchTone },
  { label: "Knowledge Retrieval", tone: "running" as ResearchTone },
  { label: "Analysis", tone: "reading" as ResearchTone },
  { label: "Citation Verification", tone: "reviewing" as ResearchTone },
  { label: "Executive Summary", tone: "queued" as ResearchTone },
  { label: "Completed", tone: "queued" as ResearchTone },
];

export const sourceRecords: SourceRecord[] = [
  { source: "IDC Enterprise AI Outlook", type: "Research Paper", domain: "idc.com", credibility: "High", published: "May 2026", status: "completed", icon: BookOpen },
  { source: "Q2 Earnings Transcript", type: "PDF", domain: "investor.example.com", credibility: "High", published: "Jun 2026", status: "reviewing", icon: FileText },
  { source: "Internal GTM Notes", type: "Internal Docs", domain: "cortexprime.local", credibility: "Verified", published: "Jun 2026", status: "completed", icon: ShieldCheck },
  { source: "Policy Tracking API", type: "API", domain: "policywatch.io", credibility: "Trusted", published: "Live", status: "running", icon: Globe },
  { source: "Market Signals DB", type: "Database", domain: "warehouse.internal", credibility: "Trusted", published: "Live", status: "completed", icon: Database },
  { source: "AI Regulation Daily", type: "News", domain: "regdaily.com", credibility: "Medium", published: "Today", status: "searching", icon: Newspaper },
];

export const insightCards: InsightCard[] = [
  { title: "Top Findings", summary: "Enterprise demand is shifting toward governed multi-agent platforms with strong auditability.", confidence: "96%", sources: "18 sources", icon: CheckCircle2 },
  { title: "Key Trends", summary: "Pricing pressure is increasing in browser automation, while governance remains a premium differentiator.", confidence: "91%", sources: "12 sources", icon: TrendingUp },
  { title: "Risk Indicators", summary: "Compliance-heavy buyers are delaying rollout timelines until vendor policy controls are clearer.", confidence: "84%", sources: "9 sources", icon: TriangleAlert },
  { title: "Opportunities", summary: "Mid-market financial services teams show strong interest in voice-enabled research operations.", confidence: "89%", sources: "11 sources", icon: Sparkles },
];

export const progressDistribution = [
  { label: "Running", value: 10, color: "#38B88A" },
  { label: "Completed", value: 6, color: "#3B82F6" },
  { label: "Queued", value: 1, color: "#F59E0B" },
  { label: "Failed", value: 1, color: "#CBD5E1" },
];

export const categoryInsights: TopicMetric[] = [
  { label: "Market", value: 128, color: "#F43F5E" },
  { label: "Competitors", value: 86, color: "#3B82F6" },
  { label: "Technology", value: 54, color: "#38B88A" },
  { label: "Customer", value: 32, color: "#F59E0B" },
  { label: "Regulatory", value: 12, color: "#8B5CF6" },
];

export const topTopics = [
  { label: "Market Trends", count: 28 },
  { label: "AI and ML", count: 24 },
  { label: "Competitor Analysis", count: 18 },
  { label: "Customer Insights", count: 16 },
  { label: "Product Strategy", count: 14 },
  { label: "Pricing Strategy", count: 12 },
  { label: "Industry Outlook", count: 11 },
  { label: "Investment", count: 9 },
];

export const reportPreview = {
  summary:
    "CortexPrime research indicates the strongest near-term market expansion will come from regulated enterprises seeking AI operating systems with auditable governance, rapid deployment, and integrated memory. Pricing sensitivity is rising, but teams continue to pay a premium for trusted research workflows and policy-safe orchestration.",
  findings: [
    "Governance and traceability are now primary buying criteria for enterprise AI research platforms.",
    "Competitors are improving source aggregation, but citation verification quality still varies widely.",
    "Cross-functional research teams prefer one workspace for discovery, synthesis, and executive reporting.",
  ],
  recommendations: [
    "Lead with governance, replay, and memory differentiation in enterprise sales conversations.",
    "Package executive-grade report export features as a premium capability.",
    "Expand policy-aware source verification for regulated accounts.",
  ],
  sources: "126 sources",
  confidence: "87%",
};

export const actionCards = [
  { label: "Research Templates", icon: LayoutTemplate },
  { label: "Import Sources", icon: Upload },
  { label: "Filters", icon: Filter },
  { label: "Refresh", icon: Workflow },
];

export const shellChips = {
  currentMission: "Q2 Market Intelligence",
  voiceStatus: "Listening...",
};
