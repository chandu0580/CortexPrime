export interface GovernanceKPI {
  title: string;
  value: string;
  change: string;
  isPositive: boolean;
  vsText: string;
  sparkline: number[];
  color: string;
  icon: "shield" | "users" | "lock" | "checkCircle" | "alertTriangle";
}

export interface GovernancePolicy {
  name: string;
  description: string;
  category: string;
  status: "Active" | "Draft" | "Archived";
  lastUpdated: string;
  owner: string;
  ownerAvatar?: string;
}

export interface ComplianceBreakdown {
  status: string;
  percentage: number;
  change: string;
  isPositive: boolean;
  color: string;
}

export interface GovernanceIncident {
  title: string;
  timestamp: string;
  risk: "High" | "Medium" | "Low" | "Critical";
}

export interface AccessRequest {
  user: string;
  userAvatar?: string;
  request: string;
  status: "Pending" | "Approved" | "Rejected";
  time: string;
}

export interface PolicyViolationData {
  date: string;
  violations: number;
}

export interface PolicyCategoryData {
  category: string;
  count: number;
  percentage: number;
  color: string;
}

export const governanceKPIs: GovernanceKPI[] = [
  {
    title: "Policies",
    value: "48",
    change: "↑ 12.5%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [40, 42, 43, 44, 45, 45, 48],
    color: "#38B88A",
    icon: "shield",
  },
  {
    title: "Users",
    value: "156",
    change: "↑ 8.3%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [142, 145, 148, 150, 152, 155, 156],
    color: "#38B88A",
    icon: "users",
  },
  {
    title: "Access Requests",
    value: "23",
    change: "↓ 4.2%",
    isPositive: false, // in screenshot, this change is red down arrow
    vsText: "vs last 7 days",
    sparkline: [26, 25, 27, 24, 25, 22, 23],
    color: "#EF4444",
    icon: "lock",
  },
  {
    title: "Compliance Score",
    value: "98.6%",
    change: "↑ 2.1%",
    isPositive: true,
    vsText: "vs last 7 days",
    sparkline: [96.2, 96.8, 97.4, 98.0, 98.2, 98.5, 98.6],
    color: "#38B88A",
    icon: "checkCircle",
  },
  {
    title: "Incidents",
    value: "3",
    change: "↓ 25%",
    isPositive: false, // red text and red arrow down
    vsText: "vs last 7 days",
    sparkline: [5, 4, 4, 3, 3, 2, 3],
    color: "#EF4444",
    icon: "alertTriangle",
  },
];

export const governancePolicies: GovernancePolicy[] = [
  {
    name: "Data Access Control Policy",
    description: "Defines access levels and data handling rules",
    category: "Access Control",
    status: "Active",
    lastUpdated: "May 12, 2024 10:30 AM",
    owner: "Alex Morgan",
  },
  {
    name: "AI Usage Policy",
    description: "Guidelines for responsible AI system usage",
    category: "AI Usage",
    status: "Active",
    lastUpdated: "May 11, 2024 02:15 PM",
    owner: "Sarah Chen",
  },
  {
    name: "Data Privacy Policy",
    description: "Data collection, storage and privacy guidelines",
    category: "Data Privacy",
    status: "Active",
    lastUpdated: "May 10, 2024 11:45 AM",
    owner: "Alex Morgan",
  },
  {
    name: "Security Policy",
    description: "System security and access requirements",
    category: "Security",
    status: "Active",
    lastUpdated: "May 9, 2024 09:20 AM",
    owner: "Michael Brown",
  },
  {
    name: "Audit & Logging Policy",
    description: "Logging requirements and audit procedures",
    category: "Audit",
    status: "Active",
    lastUpdated: "May 8, 2024 04:30 PM",
    owner: "Sarah Chen",
  },
  {
    name: "Compliance Policy",
    description: "Regulatory compliance and standards",
    category: "Compliance",
    status: "Draft",
    lastUpdated: "May 7, 2024 01:10 PM",
    owner: "Jennifer Lee",
  },
];

export const complianceBreakdown: ComplianceBreakdown[] = [
  { status: "Compliant", percentage: 98.6, change: "↑ 2.1%", isPositive: true, color: "#38B88A" },
  { status: "Warning", percentage: 1.2, change: "↑ 0.3%", isPositive: true, color: "#F59E0B" },
  { status: "Non-Compliant", percentage: 0.2, change: "↓ 0.1%", isPositive: false, color: "#EF4444" },
  { status: "Not Assessed", percentage: 0.0, change: "—", isPositive: false, color: "#9CA3AF" },
];

export const recentIncidents: GovernanceIncident[] = [
  {
    title: "Unauthorized data access attempt",
    timestamp: "May 12, 2024 • 10:20 AM",
    risk: "High",
  },
  {
    title: "Policy violation: Data export limit",
    timestamp: "May 11, 2024 • 03:45 PM",
    risk: "Medium",
  },
  {
    title: "Access request timeout",
    timestamp: "May 10, 2024 • 11:30 AM",
    risk: "Low",
  },
];

export const accessRequests: AccessRequest[] = [
  {
    user: "Emma Wilson",
    request: "Requesting access to Customer Database",
    status: "Pending",
    time: "2m ago",
  },
  {
    user: "James Anderson",
    request: "Requesting admin access to Analytics",
    status: "Pending",
    time: "15m ago",
  },
  {
    user: "Lisa Park",
    request: "Requesting access to Financial Data",
    status: "Approved",
    time: "1h ago",
  },
  {
    user: "David Kim",
    request: "Requesting access to Research Data",
    status: "Rejected",
    time: "2h ago",
  },
];

export const violationSeries: PolicyViolationData[] = [
  { date: "May 6", violations: 10 },
  { date: "May 7", violations: 8 },
  { date: "May 8", violations: 17 },
  { date: "May 9", violations: 10 },
  { date: "May 10", violations: 14 },
  { date: "May 11", violations: 9 },
  { date: "May 12", violations: 11 },
];

export const topPolicyCategories: PolicyCategoryData[] = [
  { category: "Access Control", count: 18, percentage: 37.5, color: "#38B88A" },
  { category: "Data Privacy", count: 12, percentage: 25.0, color: "#3B82F6" },
  { category: "Security", count: 8, percentage: 16.7, color: "#8B5CF6" },
  { category: "AI Usage", count: 6, percentage: 12.5, color: "#F59E0B" },
  { category: "Compliance", count: 4, percentage: 8.3, color: "#9CA3AF" },
];
