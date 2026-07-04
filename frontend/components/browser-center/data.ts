import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Archive,
  BarChart3,
  Bot,
  Brain,
  CheckCircle2,
  Database,
  Download,
  FileText,
  Filter,
  Globe,
  Home,
  Image,
  LayoutGrid,
  Link2,
  Mic,
  Monitor,
  Newspaper,
  Puzzle,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Table2,
  Target,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";

export type BrowserTone =
  | "browsing"
  | "extracting"
  | "reading"
  | "clicking"
  | "typing"
  | "waiting"
  | "completed"
  | "idle"
  | "reviewing"
  | "info";

export type BrowserMetric = {
  label: string;
  value: string;
  trend: string;
  status: string;
  tone: BrowserTone;
  icon: LucideIcon;
  data: number[];
};

export type BrowserSession = {
  id: string;
  browser: "chrome" | "edge" | "safari" | "firefox" | "brave";
  os: string;
  agent: string;
  mission: string;
  url: string;
  status: BrowserTone;
  pages: number;
  duration: string;
  progress: number;
};

export type DomainItem = {
  domain: string;
  visits: number;
  logo: string;
};

export type ActivityItem = {
  label: string;
  time: string;
  icon: LucideIcon;
  tone: BrowserTone;
};

export type CurrentTask = {
  title: string;
  agent: string;
  url: string;
  action: string;
  eta: string;
  progress: number;
  confidence: string;
  status: string;
};

export type TimelineItem = {
  action: string;
  website: string;
  timestamp: string;
  duration: string;
  tone: BrowserTone;
  icon: LucideIcon;
};

export type WebsiteRow = {
  website: string;
  category: string;
  pagesVisited: number;
  timeSpent: string;
  extracted: string;
  trust: string;
  status: BrowserTone;
};

export type ExtractionItem = {
  label: string;
  items: string;
  confidence: string;
  updated: string;
  icon: LucideIcon;
};

export type AnalyticsCard = {
  label: string;
  value: string;
  trend: string;
  data: number[];
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
  { label: "Browser", href: "/browser", icon: Globe, active: true },
  { label: "Replay", href: "/replay", icon: Archive },
  { label: "Analytics", href: "/analytics", icon: BarChart3 },
  { label: "Governance", href: "/governance", icon: ShieldCheck },
  { label: "Monitoring", href: "/system-status", icon: Activity },
  { label: "Integrations", href: "/settings", icon: Puzzle },
  { label: "Settings", href: "/settings", icon: Settings },
];

export const metrics: BrowserMetric[] = [
  { label: "Active Sessions", value: "12", trend: "+20%", status: "Browsing", tone: "browsing", icon: Globe, data: [6, 7, 8, 8, 9, 10, 10, 11, 12] },
  { label: "Pages Visited", value: "1,842", trend: "+18.3%", status: "Scanning", tone: "browsing", icon: LayoutGrid, data: [940, 1020, 1110, 1188, 1320, 1490, 1602, 1715, 1842] },
  { label: "Data Extracted", value: "3.24 GB", trend: "+24.7%", status: "Extracting", tone: "extracting", icon: Download, data: [1.2, 1.5, 1.7, 1.9, 2.1, 2.4, 2.7, 3.0, 3.24] },
  { label: "Requests Made", value: "6,731", trend: "+16.1%", status: "Live", tone: "browsing", icon: TrendingUp, data: [3200, 3510, 3800, 4200, 4680, 5120, 5710, 6210, 6731] },
  { label: "Success Rate", value: "96.8%", trend: "+3.6%", status: "Trusted", tone: "completed", icon: CheckCircle2, data: [86, 88, 90, 92, 93, 94, 95, 96, 96.8] },
];

export const sessions: BrowserSession[] = [
  { id: "#7821", browser: "chrome", os: "Windows 11", agent: "Research Agent", mission: "Q2 Market Intelligence", url: "https://www.bloomberg.com/markets", status: "browsing", pages: 245, duration: "00:32:18", progress: 65 },
  { id: "#7819", browser: "edge", os: "Windows 11", agent: "Data Analyst", mission: "Competitor Analysis", url: "https://www.crunchbase.com/search", status: "extracting", pages: 189, duration: "00:28:43", progress: 78 },
  { id: "#7818", browser: "chrome", os: "macOS Sonoma", agent: "Insight Agent", mission: "Industry Research", url: "https://www.mckinsey.com/industries", status: "browsing", pages: 312, duration: "00:41:07", progress: 55 },
  { id: "#7817", browser: "firefox", os: "Windows 11", agent: "Finance Agent", mission: "Financial Analysis", url: "https://www.sec.gov/edgar/search", status: "extracting", pages: 156, duration: "00:22:31", progress: 92 },
  { id: "#7816", browser: "safari", os: "macOS Sonoma", agent: "Marketing Agent", mission: "Market Research", url: "https://www.statista.com/statistics", status: "browsing", pages: 178, duration: "00:19:54", progress: 40 },
  { id: "#7815", browser: "brave", os: "Ubuntu 22.04", agent: "Support Agent", mission: "Customer Insights", url: "https://www.reddit.com/r/SaaS", status: "idle", pages: 32, duration: "00:05:12", progress: 10 },
];

export const topDomains: DomainItem[] = [
  { domain: "bloomberg.com", visits: 456, logo: "B" },
  { domain: "crunchbase.com", visits: 312, logo: "cb" },
  { domain: "mckinsey.com", visits: 289, logo: "Mc" },
  { domain: "sec.gov", visits: 256, logo: "SEC" },
  { domain: "statista.com", visits: 198, logo: "S" },
];

export const recentActivity: ActivityItem[] = [
  { label: "Research Agent started session #7821", time: "2m ago", icon: Globe, tone: "browsing" },
  { label: "Data Analyst extracted data from crunchbase.com", time: "6m ago", icon: Download, tone: "extracting" },
  { label: "Insight Agent visited mckinsey.com", time: "12m ago", icon: Search, tone: "browsing" },
  { label: "Finance Agent downloaded SEC filing", time: "18m ago", icon: FileText, tone: "completed" },
  { label: "Marketing Agent captured market data", time: "24m ago", icon: Database, tone: "extracting" },
];

export const activityOverview = [
  { label: "Browsing", value: 5, color: "#38B88A" },
  { label: "Extracting", value: 4, color: "#3B82F6" },
  { label: "Idle", value: 2, color: "#F59E0B" },
  { label: "Completed", value: 1, color: "#CBD5E1" },
];

export const pagesVisitedSeries = [
  { day: "May 6", value: 520 },
  { day: "May 8", value: 730 },
  { day: "May 10", value: 690 },
  { day: "May 11", value: 1110 },
  { day: "May 13", value: 920 },
  { day: "May 16", value: 1180 },
  { day: "May 18", value: 830 },
  { day: "May 21", value: 790 },
  { day: "May 24", value: 960 },
  { day: "May 26", value: 1320 },
  { day: "May 28", value: 1010 },
  { day: "May 31", value: 1240 },
];

export const extractedSeries = [
  { day: "May 6", value: 1.6 },
  { day: "May 7", value: 1.3 },
  { day: "May 8", value: 2.1 },
  { day: "May 9", value: 1.8 },
  { day: "May 10", value: 2.7 },
  { day: "May 11", value: 3.2 },
  { day: "May 12", value: 1.9 },
  { day: "May 13", value: 2.4 },
  { day: "May 14", value: 2.1 },
  { day: "May 15", value: 2.2 },
  { day: "May 16", value: 2.5 },
  { day: "May 17", value: 2.9 },
  { day: "May 18", value: 2.4 },
  { day: "May 19", value: 1.8 },
  { day: "May 20", value: 1.7 },
  { day: "May 21", value: 1.9 },
  { day: "May 22", value: 1.5 },
  { day: "May 23", value: 1.4 },
  { day: "May 24", value: 2.0 },
  { day: "May 25", value: 1.8 },
  { day: "May 26", value: 2.7 },
  { day: "May 27", value: 2.5 },
  { day: "May 28", value: 1.6 },
  { day: "May 29", value: 1.2 },
  { day: "May 30", value: 2.3 },
  { day: "May 31", value: 2.6 },
];

export const currentTask: CurrentTask = {
  title: "Competitive Pricing Research",
  agent: "Research Agent",
  url: "https://www.bloomberg.com/markets",
  action: "Extracting pricing references and company updates from market pages",
  eta: "03:10 min",
  progress: 68,
  confidence: "94%",
  status: "Extracting",
};

export const navigationTimeline: TimelineItem[] = [
  { action: "Opened website", website: "google.com", timestamp: "10:21:03", duration: "1s", tone: "completed", icon: Globe },
  { action: "Accepted cookies", website: "bloomberg.com", timestamp: "10:21:07", duration: "2s", tone: "completed", icon: CheckCircle2 },
  { action: "Filled search", website: "bloomberg.com", timestamp: "10:21:14", duration: "3s", tone: "typing", icon: Search },
  { action: "Opened result", website: "bloomberg.com", timestamp: "10:21:20", duration: "2s", tone: "clicking", icon: Link2 },
  { action: "Scrolled page", website: "bloomberg.com", timestamp: "10:22:03", duration: "6s", tone: "reading", icon: LayoutGrid },
  { action: "Extracted content", website: "bloomberg.com", timestamp: "10:22:22", duration: "8s", tone: "extracting", icon: Download },
  { action: "Downloaded file", website: "sec.gov", timestamp: "10:23:11", duration: "4s", tone: "extracting", icon: FileText },
  { action: "Completed session", website: "pending", timestamp: "Pending", duration: "--", tone: "waiting", icon: CheckCircle2 },
];

export const visitedWebsites: WebsiteRow[] = [
  { website: "Google", category: "Search", pagesVisited: 24, timeSpent: "06m 14s", extracted: "Queries, links", trust: "High", status: "completed" },
  { website: "LinkedIn", category: "People", pagesVisited: 12, timeSpent: "09m 08s", extracted: "Profiles", trust: "High", status: "browsing" },
  { website: "GitHub", category: "Code", pagesVisited: 31, timeSpent: "15m 41s", extracted: "Repos, readmes", trust: "High", status: "extracting" },
  { website: "Wikipedia", category: "Reference", pagesVisited: 18, timeSpent: "07m 02s", extracted: "Facts", trust: "Medium", status: "reading" },
  { website: "AWS", category: "Docs", pagesVisited: 27, timeSpent: "13m 19s", extracted: "Pricing, specs", trust: "High", status: "extracting" },
  { website: "Microsoft Docs", category: "Docs", pagesVisited: 22, timeSpent: "11m 44s", extracted: "Guides", trust: "High", status: "browsing" },
  { website: "OpenAI", category: "AI", pagesVisited: 17, timeSpent: "08m 12s", extracted: "Model notes", trust: "High", status: "completed" },
  { website: "Internal Portal", category: "Internal", pagesVisited: 9, timeSpent: "05m 01s", extracted: "Policies", trust: "Verified", status: "reviewing" },
];

export const extractedIntelligence: ExtractionItem[] = [
  { label: "Contacts", items: "184 items", confidence: "92%", updated: "3m ago", icon: Users },
  { label: "Documents", items: "62 files", confidence: "96%", updated: "8m ago", icon: FileText },
  { label: "Tables", items: "48 tables", confidence: "89%", updated: "12m ago", icon: Table2 },
  { label: "Images", items: "137 assets", confidence: "83%", updated: "16m ago", icon: Image },
  { label: "Pricing", items: "29 entries", confidence: "94%", updated: "18m ago", icon: TrendingUp },
  { label: "Technical Specs", items: "74 specs", confidence: "91%", updated: "25m ago", icon: LayoutGrid },
  { label: "News", items: "41 articles", confidence: "87%", updated: "31m ago", icon: Newspaper },
  { label: "Reports", items: "13 reports", confidence: "95%", updated: "44m ago", icon: Sparkles },
];

export const analyticsCards: AnalyticsCard[] = [
  { label: "Pages Visited", value: "1,842", trend: "+18.3%", data: [600, 720, 910, 840, 1120, 1190, 1320, 1510, 1842] },
  { label: "Session Duration", value: "31m avg", trend: "+6.4%", data: [19, 21, 23, 25, 26, 28, 29, 30, 31] },
  { label: "Extraction Accuracy", value: "94.1%", trend: "+2.7%", data: [82, 84, 86, 88, 89, 91, 92, 93, 94.1] },
  { label: "Request Volume", value: "6,731", trend: "+16.1%", data: [3200, 3420, 3800, 4100, 4680, 5200, 5710, 6200, 6731] },
];

export const browserInsight =
  "Today, CortexPrime explored 86 websites across 12 browser sessions, extracted 3,200 structured data points, and achieved a 98.8% automation success rate. Most activity focused on technical documentation and competitive intelligence.";

export const actions = [
  { label: "Filter", icon: Filter },
  { label: "Refresh", icon: RefreshCw },
  { label: "Open URL", icon: Link2 },
  { label: "Start Automation", icon: Zap },
];
