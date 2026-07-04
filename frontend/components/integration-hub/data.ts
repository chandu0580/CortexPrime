export interface IntegrationKPI {
  title: string;
  value: string;
  change: string;
  isPositive: boolean;
  vsText: string;
  sparkline: number[];
  color: string;
  icon: "plug" | "zap" | "warning" | "api" | "success";
}

export interface IntegrationItem {
  name: string;
  description: string;
  category: string;
  status: "Connected" | "Warning" | "Error" | "Disconnected";
  lastSynced: string;
  usage: number;
  successRate: string;
  logo: string;
}

export interface DonutSummarySector {
  status: string;
  count: number;
  percentage: number;
  color: string;
}

export interface RecentActivityItem {
  message: string;
  time: string;
  status: "success" | "warning" | "danger";
}

export interface CategoryCardData {
  name: string;
  count: string;
  icon: string;
}

export interface PopularIntegration {
  name: string;
  logo: string;
}

export const integrationKPIs: IntegrationKPI[] = [
  {
    title: "Connected Integrations",
    value: "24",
    change: "↑ 14.3%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [20, 21, 22, 22, 23, 23, 24],
    color: "#38B88A",
    icon: "plug",
  },
  {
    title: "Active Integrations",
    value: "18",
    change: "↑ 12.5%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [15, 16, 16, 17, 17, 18, 18],
    color: "#38B88A",
    icon: "zap",
  },
  {
    title: "Failed Integrations",
    value: "2",
    change: "↓ 33.3%",
    isPositive: false, // red down arrow
    vsText: "vs last 7 days",
    sparkline: [4, 4, 3, 3, 2, 3, 2],
    color: "#EF4444",
    icon: "warning",
  },
  {
    title: "API Calls (24h)",
    value: "12,842",
    change: "↑ 18.7%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [10200, 10800, 11100, 11400, 11900, 12200, 12842],
    color: "#38B88A",
    icon: "api",
  },
  {
    title: "Success Rate",
    value: "98.6%",
    change: "↑ 2.6%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [95.8, 96.2, 96.8, 97.4, 98.0, 98.3, 98.6],
    color: "#38B88A",
    icon: "success",
  },
];

export const integrationsList: IntegrationItem[] = [
  {
    name: "Slack",
    description: "Team communication",
    category: "Communication",
    status: "Connected",
    lastSynced: "2m ago",
    usage: 1248,
    successRate: "99.2%",
    logo: "slack",
  },
  {
    name: "Google Drive",
    description: "File storage & sync",
    category: "Storage",
    status: "Connected",
    lastSynced: "5m ago",
    usage: 965,
    successRate: "98.7%",
    logo: "gdrive",
  },
  {
    name: "Microsoft 365",
    description: "Office applications",
    category: "Productivity",
    status: "Connected",
    lastSynced: "8m ago",
    usage: 1842,
    successRate: "99.1%",
    logo: "m365",
  },
  {
    name: "Salesforce",
    description: "CRM platform",
    category: "CRM",
    status: "Connected",
    lastSynced: "15m ago",
    usage: 732,
    successRate: "97.8%",
    logo: "salesforce",
  },
  {
    name: "GitHub",
    description: "Code repository",
    category: "Development",
    status: "Connected",
    lastSynced: "18m ago",
    usage: 1125,
    successRate: "98.9%",
    logo: "github",
  },
  {
    name: "Jira",
    description: "Project management",
    category: "Project Management",
    status: "Warning",
    lastSynced: "45m ago",
    usage: 324,
    successRate: "95.2%",
    logo: "jira",
  },
  {
    name: "Twilio",
    description: "SMS & voice service",
    category: "Communication",
    status: "Error",
    lastSynced: "1h ago",
    usage: 128,
    successRate: "82.1%",
    logo: "twilio",
  },
  {
    name: "Notion",
    description: "Knowledge management",
    category: "Productivity",
    status: "Connected",
    lastSynced: "1h ago",
    usage: 587,
    successRate: "98.3%",
    logo: "notion",
  },
];

export const donutSummary: DonutSummarySector[] = [
  { status: "Connected", count: 18, percentage: 75, color: "#38B88A" },
  { status: "Warning", count: 2, percentage: 8.3, color: "#F59E0B" },
  { status: "Error", count: 2, percentage: 8.3, color: "#EF4444" },
  { status: "Disconnected", count: 2, percentage: 8.3, color: "#9CA3AF" },
];

export const recentActivityStream: RecentActivityItem[] = [
  { message: "Slack integration synced successfully", time: "2m ago", status: "success" },
  { message: "Google Drive file sync completed", time: "5m ago", status: "success" },
  { message: "Jira integration returned a warning", time: "45m ago", status: "warning" },
  { message: "Twilio integration failed to connect", time: "1h ago", status: "danger" },
  { message: "Microsoft 365 token refreshed", time: "2h ago", status: "success" },
];

export const activeCategories: CategoryCardData[] = [
  { name: "Communication", count: "4 Integrations", icon: "messageSquare" },
  { name: "Storage", count: "3 Integrations", icon: "folder" },
  { name: "Productivity", count: "5 Integrations", icon: "clipboard" },
  { name: "CRM", count: "2 Integrations", icon: "user" },
  { name: "Development", count: "3 Integrations", icon: "code" },
  { name: "Project Management", count: "2 Integrations", icon: "calendar" },
  { name: "Marketing", count: "2 Integrations", icon: "megaphone" },
  { name: "Finance", count: "1 Integration", icon: "dollarSign" },
];

export const popularIntegrationsList: PopularIntegration[] = [
  { name: "Slack", logo: "slack" },
  { name: "Google Drive", logo: "gdrive" },
  { name: "Microsoft 365", logo: "m365" },
  { name: "Salesforce", logo: "salesforce" },
  { name: "GitHub", logo: "github" },
];
