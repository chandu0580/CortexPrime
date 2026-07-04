export interface KPICardData {
  title: string;
  value: string;
  change: string;
  isPositive: boolean;
  vsText: string;
  sparkline: number[];
  color: string;
  icon: "sessions" | "actions" | "compute" | "data" | "success" | "errors";
}

export interface PerformanceData {
  date: string;
  sessions: number;
  actions: number;
  successRate: number;
}

export interface CategoryUsageData {
  category: string;
  percentage: number;
  actions: number;
  color: string;
}

export interface AgentActivityData {
  name: string;
  actions: number;
  change: string;
  isPositive: boolean;
  color: string;
}

export interface ActionTypeData {
  type: string;
  actions: number;
  percentage: number;
  color: string;
}

export interface SuccessRateData {
  date: string;
  rate: number;
}

export interface InsightData {
  type: "success" | "info" | "purple" | "warning";
  title: string;
  text: string;
}

export interface SummaryItem {
  label: string;
  value: string;
  change?: string;
  isPositive?: boolean;
}

export const kpiMetrics: KPICardData[] = [
  {
    title: "Total Sessions",
    value: "248",
    change: "↑ 18.6%",
    isPositive: true,
    vsText: "vs May 1 - May 5",
    sparkline: [120, 135, 140, 158, 148, 172, 160, 185, 192, 180, 210, 225, 248],
    color: "#38B88A",
    icon: "sessions",
  },
  {
    title: "Total Actions",
    value: "12,842",
    change: "↑ 22.4%",
    isPositive: true,
    vsText: "vs May 1 - May 5",
    sparkline: [8200, 8900, 9100, 9400, 9800, 10200, 10900, 11200, 11500, 11800, 12100, 12500, 12842],
    color: "#8B5CF6",
    icon: "actions",
  },
  {
    title: "Total Compute Time",
    value: "32h 45m",
    change: "↑ 16.8%",
    isPositive: true,
    vsText: "vs May 1 - May 5",
    sparkline: [18, 20, 21, 23, 22, 25, 26, 28, 27, 29, 30, 31, 32.75],
    color: "#38B88A",
    icon: "compute",
  },
  {
    title: "Data Processed",
    value: "15.6 GB",
    change: "↑ 9.3%",
    isPositive: true,
    vsText: "vs May 1 - May 5",
    sparkline: [10.2, 10.8, 11.2, 11.9, 12.1, 12.8, 13.2, 13.9, 14.1, 14.5, 14.9, 15.2, 15.6],
    color: "#F59E0B",
    icon: "data",
  },
  {
    title: "Success Rate",
    value: "96.3%",
    change: "↑ 3.7%",
    isPositive: true,
    vsText: "vs May 1 - May 5",
    sparkline: [92.1, 92.8, 93.2, 93.9, 94.5, 94.2, 95.1, 95.5, 95.8, 96.0, 96.1, 96.2, 96.3],
    color: "#38B88A",
    icon: "success",
  },
  {
    title: "Errors",
    value: "52",
    change: "↓ 12.1%",
    isPositive: false,
    vsText: "vs May 1 - May 5",
    sparkline: [85, 80, 75, 78, 72, 68, 65, 62, 59, 58, 56, 54, 52],
    color: "#EF4444",
    icon: "errors",
  },
];

export const performanceSeries: PerformanceData[] = [
  { date: "May 6", sessions: 100, actions: 180, successRate: 93 },
  { date: "May 7", sessions: 120, actions: 200, successRate: 94 },
  { date: "May 8", sessions: 140, actions: 220, successRate: 95 },
  { date: "May 9", sessions: 160, actions: 250, successRate: 96 },
  { date: "May 10", sessions: 150, actions: 220, successRate: 95 },
  { date: "May 11", sessions: 170, actions: 240, successRate: 96 },
  { date: "May 12", sessions: 155, actions: 230, successRate: 95 },
];

export const usageByCategory: CategoryUsageData[] = [
  { category: "Research", percentage: 32.4, actions: 4158, color: "#38B88A" },
  { category: "Computer Use", percentage: 24.7, actions: 3171, color: "#3B82F6" },
  { category: "Browser", percentage: 19.8, actions: 2544, color: "#8B5CF6" },
  { category: "Data Analysis", percentage: 13.6, actions: 1744, color: "#F59E0B" },
  { category: "Other", percentage: 9.5, actions: 1225, color: "#9CA3AF" },
];

export const topAgents: AgentActivityData[] = [
  { name: "Research Agent", actions: 4158, change: "↑ 18.6%", isPositive: true, color: "#38B88A" },
  { name: "Data Analyst", actions: 3171, change: "↑ 22.3%", isPositive: true, color: "#3B82F6" },
  { name: "Insight Agent", actions: 2544, change: "↑ 16.1%", isPositive: true, color: "#8B5CF6" },
  { name: "Browser Agent", actions: 1744, change: "↑ 11.2%", isPositive: true, color: "#F59E0B" },
  { name: "Support Agent", actions: 1225, change: "↓ 3.2%", isPositive: false, color: "#9CA3AF" },
];

export const actionTypes: ActionTypeData[] = [
  { type: "Data Extraction", actions: 3256, percentage: 25.3, color: "#38B88A" },
  { type: "Web Search", actions: 2842, percentage: 22.1, color: "#3B82F6" },
  { type: "File Operations", actions: 2101, percentage: 16.4, color: "#8B5CF6" },
  { type: "Report Generation", actions: 1785, percentage: 13.9, color: "#EC4899" }, // pink/orchid
  { type: "Data Analysis", actions: 1456, percentage: 11.3, color: "#F59E0B" },
  { type: "Other", actions: 1402, percentage: 10.9, color: "#9CA3AF" },
];

export const successRateOverTime: SuccessRateData[] = [
  { date: "May 6", rate: 88 },
  { date: "May 7", rate: 91 },
  { date: "May 8", rate: 93 },
  { date: "May 9", rate: 91 },
  { date: "May 10", rate: 92 },
  { date: "May 11", rate: 93 },
  { date: "May 12", rate: 91 },
];

export const keyInsights: InsightData[] = [
  {
    type: "success",
    title: "Performance Improving",
    text: "Total actions increased by 22.4% compared to last week.",
  },
  {
    type: "info",
    title: "Peak Activity Time",
    text: "10:00 AM - 12:00 PM sees the highest activity.",
  },
  {
    type: "purple",
    title: "Most Used Category",
    text: "Research operations account for 32.4% of total actions.",
  },
  {
    type: "warning",
    title: "Error Reduction Needed",
    text: "Errors increased by 12.1% compared to last week.",
  },
];

// Heatmap data: rows are Mon-Sun, cols are 12 time blocks (12 AM, 2 AM, 4 AM, 6 AM, 8 AM, 10 AM, 12 PM, 2 PM, 4 PM, 6 PM, 8 PM, 10 PM)
// Matrix representing values from 1-10 (intensity of green)
export const heatmapData: number[][] = [
  [1, 1, 1, 2, 3, 5, 4, 6, 7, 5, 3, 2], // Mon
  [1, 1, 2, 2, 4, 6, 8, 9, 6, 5, 4, 1], // Tue
  [2, 1, 1, 3, 5, 8, 9, 10, 8, 6, 3, 2], // Wed
  [1, 1, 2, 3, 4, 7, 9, 9, 7, 5, 3, 1], // Thu
  [1, 2, 1, 3, 5, 7, 8, 8, 6, 4, 2, 1], // Fri
  [1, 1, 1, 1, 2, 3, 4, 3, 3, 2, 2, 1], // Sat
  [1, 1, 1, 1, 2, 2, 3, 4, 3, 2, 1, 1], // Sun
];

export const heatmapHours = [
  "12 AM", "2 AM", "4 AM", "6 AM", "8 AM", "10 AM",
  "12 PM", "2 PM", "4 PM", "6 PM", "8 PM", "10 PM"
];

export const summaryItems: SummaryItem[] = [
  { label: "Total Users", value: "42", change: "+ 5", isPositive: true },
  { label: "Active Missions", value: "18", change: "+ 3", isPositive: true },
  { label: "Active Agents", value: "36", change: "+ 4", isPositive: true },
  { label: "System Uptime", value: "99.8%" },
  { label: "Avg. Response Time", value: "1.24s", change: "+ 8.3%", isPositive: true },
];
