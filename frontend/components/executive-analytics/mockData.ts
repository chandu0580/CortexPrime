export interface KPICardData {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: "success" | "warning" | "danger" | "info" | "neutral";
  statusText: string;
}

export interface ChartDataPoint {
  name: string;
  volume: number;
  successRate: number;
  avgRuntime: number; // in seconds
  usageCount: number;
}

export interface AgentPerformanceData {
  agent: string;
  completedMissions: number;
  successRate: number; // percentage
  avgRuntime: string;
  avgLatency: string;
  resourceUsage: string;
  healthScore: number;
  role: string;
  status: "active" | "idle" | "error";
}

export interface DepartmentAdoptionData {
  department: string;
  activeUsers: number;
  missions: number;
  timeSaved: string; // e.g. "640 hrs"
  adoptionScore: number; // percentage
}

export interface CostIntelligenceData {
  tokenUsage: number;
  infraCost: number;
  modelCost: number;
  voiceCost: number;
  browserCost: number;
  computerUseCost: number;
  dailySpend: number;
  monthlySpend: number;
  projectedSpend: number;
}

export interface SpendDataPoint {
  date: string;
  tokens: number;
  models: number;
  infrastructure: number;
  voice: number;
  browser: number;
  computerUse: number;
}

export interface BusinessInsight {
  id: string;
  title: string;
  type: "department" | "capability" | "productivity" | "cost" | "optimization" | "savings";
  metric: string;
  subtext: string;
  badgeText: string;
  recommendation: string;
}

export interface MissionIntelligenceData {
  type: string;
  count: number;
  successCount: number;
  failureCount: number;
  avgDuration: number; // mins
  priority: "high" | "medium" | "low";
}

export interface TimelineEvent {
  id: string;
  title: string;
  description: string;
  timestamp: string; // relative
  type: "milestone" | "agent" | "policy" | "report" | "governance";
}

// ─── KPI METRICS ───────────────────────────────────────────────────────────
export const kpiCards: KPICardData[] = [
  {
    title: "Total AI Missions",
    value: "14,862",
    change: "+22.4%",
    trend: "up",
    sparkline: [250, 280, 270, 310, 340, 320, 390],
    status: "success",
    statusText: "Optimal",
  },
  {
    title: "Mission Success Rate",
    value: "98.9%",
    change: "+1.2%",
    trend: "up",
    sparkline: [97.5, 98.1, 97.9, 98.4, 98.6, 98.8, 98.9],
    status: "success",
    statusText: "Target Achieved",
  },
  {
    title: "Active AI Agents",
    value: "42",
    change: "+8.3%",
    trend: "up",
    sparkline: [32, 34, 34, 38, 40, 40, 42],
    status: "info",
    statusText: "Expanding",
  },
  {
    title: "Total Users",
    value: "1,248",
    change: "+15.6%",
    trend: "up",
    sparkline: [1020, 1050, 1100, 1120, 1180, 1210, 1248],
    status: "info",
    statusText: "Growing Adoption",
  },
  {
    title: "Cost Today",
    value: "$1,842",
    change: "-11.2%",
    trend: "down",
    sparkline: [2100, 2050, 1980, 1920, 1890, 1870, 1842],
    status: "success",
    statusText: "Under Budget",
  },
  {
    title: "Business Efficiency Score",
    value: "94.2",
    change: "+4.7%",
    trend: "up",
    sparkline: [88.5, 89.2, 90.1, 91.5, 92.0, 93.5, 94.2],
    status: "success",
    statusText: "Peak efficiency",
  },
];

// ─── PERFORMANCE OVER TIME ──────────────────────────────────────────────────
export const performanceOverview: ChartDataPoint[] = [
  { name: "Mon", volume: 1840, successRate: 98.2, avgRuntime: 45, usageCount: 820 },
  { name: "Tue", volume: 1980, successRate: 98.5, avgRuntime: 42, usageCount: 890 },
  { name: "Wed", volume: 2120, successRate: 98.1, avgRuntime: 46, usageCount: 940 },
  { name: "Thu", volume: 2050, successRate: 98.7, avgRuntime: 38, usageCount: 910 },
  { name: "Fri", volume: 2240, successRate: 99.1, avgRuntime: 35, usageCount: 1010 },
  { name: "Sat", volume: 1420, successRate: 99.4, avgRuntime: 32, usageCount: 650 },
  { name: "Sun", volume: 1210, successRate: 99.6, avgRuntime: 28, usageCount: 520 },
];

// ─── AI WORKFORCE LEADERBOARD ───────────────────────────────────────────────
export const workforcePerformance: AgentPerformanceData[] = [
  {
    agent: "Orchestrator Agent",
    role: "Mission Coordinator",
    completedMissions: 5420,
    successRate: 99.6,
    avgRuntime: "4.2s",
    avgLatency: "24ms",
    resourceUsage: "Low (12% CPU)",
    healthScore: 99,
    status: "active",
  },
  {
    agent: "Research Agent",
    role: "Deep Intelligence Search",
    completedMissions: 3125,
    successRate: 98.4,
    avgRuntime: "18.5s",
    avgLatency: "145ms",
    resourceUsage: "Medium (42% CPU)",
    healthScore: 97,
    status: "active",
  },
  {
    agent: "Planner Agent",
    role: "Constraint Optimization",
    completedMissions: 2842,
    successRate: 99.1,
    avgRuntime: "8.1s",
    avgLatency: "65ms",
    resourceUsage: "Low (18% CPU)",
    healthScore: 98,
    status: "active",
  },
  {
    agent: "Computer Use Agent",
    role: "Desktop Automation UI",
    completedMissions: 1840,
    successRate: 96.8,
    avgRuntime: "54.2s",
    avgLatency: "480ms",
    resourceUsage: "High (74% CPU)",
    healthScore: 94,
    status: "active",
  },
  {
    agent: "Browser Agent",
    role: "Web Navigation & Scraping",
    completedMissions: 1120,
    successRate: 97.5,
    avgRuntime: "24.1s",
    avgLatency: "210ms",
    resourceUsage: "Medium (35% CPU)",
    healthScore: 96,
    status: "idle",
  },
  {
    agent: "Voice Agent",
    role: "Speech Synthesis & Call Routing",
    completedMissions: 515,
    successRate: 99.0,
    avgRuntime: "12.8s",
    avgLatency: "88ms",
    resourceUsage: "Low (15% CPU)",
    healthScore: 99,
    status: "active",
  },
];

// ─── DEPARTMENT ADOPTION ────────────────────────────────────────────────────
export const departmentAdoption: DepartmentAdoptionData[] = [
  {
    department: "Engineering",
    activeUsers: 450,
    missions: 6420,
    timeSaved: "640 hrs",
    adoptionScore: 96.4,
  },
  {
    department: "Support",
    activeUsers: 320,
    missions: 3840,
    timeSaved: "480 hrs",
    adoptionScore: 92.1,
  },
  {
    department: "Operations",
    activeUsers: 180,
    missions: 1950,
    timeSaved: "310 hrs",
    adoptionScore: 88.5,
  },
  {
    department: "Sales",
    activeUsers: 140,
    missions: 1120,
    timeSaved: "145 hrs",
    adoptionScore: 82.3,
  },
  {
    department: "Finance",
    activeUsers: 65,
    missions: 680,
    timeSaved: "110 hrs",
    adoptionScore: 78.4,
  },
  {
    department: "Marketing",
    activeUsers: 50,
    missions: 450,
    timeSaved: "85 hrs",
    adoptionScore: 74.2,
  },
  {
    department: "HR",
    activeUsers: 30,
    missions: 280,
    timeSaved: "52 hrs",
    adoptionScore: 68.9,
  },
  {
    department: "Legal",
    activeUsers: 13,
    missions: 122,
    timeSaved: "40 hrs",
    adoptionScore: 62.1,
  },
];

// ─── COST SPEND INTELLIGENCE ───────────────────────────────────────────────
export const costOverview: CostIntelligenceData = {
  tokenUsage: 148200000,
  infraCost: 3120,
  modelCost: 8420,
  voiceCost: 450,
  browserCost: 680,
  computerUseCost: 1180,
  dailySpend: 1842,
  monthlySpend: 13850,
  projectedSpend: 15400,
};

export const spendTrend: SpendDataPoint[] = [
  { date: "May 6", tokens: 840, models: 1120, infrastructure: 410, voice: 60, browser: 90, computerUse: 150 },
  { date: "May 7", tokens: 910, models: 1180, infrastructure: 420, voice: 70, browser: 95, computerUse: 160 },
  { date: "May 8", tokens: 880, models: 1140, infrastructure: 415, voice: 65, browser: 85, computerUse: 155 },
  { date: "May 9", tokens: 980, models: 1250, infrastructure: 440, voice: 75, browser: 100, computerUse: 180 },
  { date: "May 10", tokens: 1020, models: 1310, infrastructure: 450, voice: 80, browser: 110, computerUse: 190 },
  { date: "May 11", tokens: 710, models: 920, infrastructure: 320, voice: 50, browser: 70, computerUse: 110 },
  { date: "May 12", tokens: 620, models: 810, infrastructure: 290, voice: 40, browser: 60, computerUse: 90 },
];

export const modelCostBreakdown = [
  { name: "GPT-4o / Claude 3.5 Sonnet", value: 5820, fill: "#38B88A" },
  { name: "Llama 3.1 Enterprise", value: 1600, fill: "#4a8c70" },
  { name: "Gemini 1.5 Pro", value: 1000, fill: "#96cead" },
];

// ─── BUSINESS INSIGHTS ──────────────────────────────────────────────────────
export const businessInsights: BusinessInsight[] = [
  {
    id: "insight-1",
    title: "Top Performing Department",
    type: "department",
    metric: "Engineering",
    subtext: "Achieved highest autonomy score (96.4%) and adoption level.",
    badgeText: "High Value",
    recommendation: "Replicate developer workflows in Product and Design divisions.",
  },
  {
    id: "insight-2",
    title: "Most Used AI Capability",
    type: "capability",
    metric: "Deep Search & Scrape",
    subtext: "Orchestrator called Research and Browser agents 8,542 times.",
    badgeText: "High Frequency",
    recommendation: "Enable persistent cache for research queries to reduce token cost.",
  },
  {
    id: "insight-3",
    title: "Largest Productivity Gain",
    type: "productivity",
    metric: "640 Hours Saved",
    subtext: "Support agent mission resolution workflow automated 84% of Tier 1 logs.",
    badgeText: "+24% ROI",
    recommendation: "Expand support workflows to Tier 2 escalation cases.",
  },
  {
    id: "insight-4",
    title: "Highest Cost Driver",
    type: "cost",
    metric: "Computer Use API",
    subtext: "Computer Use Agent accounted for 38% of total daily spend ($700).",
    badgeText: "Cost Warning",
    recommendation: "Optimize pixel processing rate and limit desktop session durations.",
  },
  {
    id: "insight-5",
    title: "Recommended Optimization",
    type: "optimization",
    metric: "Prompt Caching",
    subtext: "System intelligence estimates 30% reduction in input token costs.",
    badgeText: "Actionable",
    recommendation: "Deploy cache headers on developer tools & planning pipelines.",
  },
  {
    id: "insight-6",
    title: "Projected Monthly Savings",
    type: "savings",
    metric: "$4,250 Saved",
    subtext: "Based on cache optimisations, workflow scaling, and model routing.",
    badgeText: "Efficiency",
    recommendation: "Approve transition of low-criticality agents to Llama 3.1 models.",
  },
];

// ─── MISSION INTELLIGENCE ───────────────────────────────────────────────────
export const missionTypes = [
  { name: "Code Execution", value: 4520, fill: "#38B88A" },
  { name: "Data Extraction", value: 3840, fill: "#2F9F77" },
  { name: "Report Generation", value: 2980, fill: "#4a8c70" },
  { name: "Desktop Automation", value: 1840, fill: "#96cead" },
  { name: "Web Research", value: 1682, fill: "#6AAF8A" },
];

export const missionStats: MissionIntelligenceData[] = [
  { type: "Data Extraction", count: 3840, successCount: 3810, failureCount: 30, avgDuration: 12, priority: "medium" },
  { type: "Web Search & Research", count: 2842, successCount: 2810, failureCount: 32, avgDuration: 35, priority: "high" },
  { type: "File Operations", count: 2101, successCount: 2095, failureCount: 6, avgDuration: 4, priority: "low" },
  { type: "Report Generation", count: 1785, successCount: 1775, failureCount: 10, avgDuration: 42, priority: "medium" },
  { type: "Data Analysis", count: 1456, successCount: 1448, failureCount: 8, avgDuration: 18, priority: "high" },
  { type: "Voice Streaming", count: 1402, successCount: 1398, failureCount: 4, avgDuration: 8, priority: "medium" },
];

export const missionPriorityData = [
  { name: "High Priority", value: 4280, fill: "#38B88A" },
  { name: "Medium Priority", value: 7540, fill: "#6B7280" },
  { name: "Low Priority", value: 3042, fill: "#E5E7EB" },
];

// ─── EXECUTIVE TIMELINE ─────────────────────────────────────────────────────
export const timelineEvents: TimelineEvent[] = [
  {
    id: "evt-1",
    title: "Engineering reached 6,000 AI missions",
    description: "Milestone achieved by developer runtime cluster. Success rate remained stable at 99.6%.",
    timestamp: "10 mins ago",
    type: "milestone",
  },
  {
    id: "evt-2",
    title: "New voice routing AI Agent deployed",
    description: "Voice routing agent version 2.4-pro is live. Integrated with CRM pipeline.",
    timestamp: "1 hour ago",
    type: "agent",
  },
  {
    id: "evt-3",
    title: "Monthly financial audit report generated",
    description: "Finance agents compiled the Q2 cost allocation sheets. Governance review completed.",
    timestamp: "3 hours ago",
    type: "report",
  },
  {
    id: "evt-4",
    title: "Enterprise policy updated",
    description: "Updated memory-access limits on research agents to adhere to GDPR constraints.",
    timestamp: "6 hours ago",
    type: "policy",
  },
  {
    id: "evt-5",
    title: "Governance compliance score improved to 99.8%",
    description: "Audit agent scanned 100% of data extraction logs. Zero anomalies detected.",
    timestamp: "12 hours ago",
    type: "governance",
  },
  {
    id: "evt-6",
    title: "Mission volume milestone achieved",
    description: "CortexPrime executed the 100,000th autonomous transaction of this quarter.",
    timestamp: "1 day ago",
    type: "milestone",
  },
];
