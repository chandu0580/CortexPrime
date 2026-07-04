export interface GovernanceKPICard {
  title: string;
  value: string;
  change: string;
  trend: "up" | "down" | "neutral";
  sparkline: number[];
  status: "success" | "warning" | "danger" | "info" | "neutral";
  statusText: string;
}

export interface PolicyData {
  id: string;
  name: string;
  category: string;
  appliesTo: string;
  lastUpdated: string;
  compliance: number; // percentage
  status: "active" | "warning" | "draft" | "disabled";
}

export interface RiskData {
  id: string;
  title: string;
  level: "critical" | "high" | "medium" | "low";
  affectedAgent: string;
  occurrences: number;
  status: string;
  recommendation: string;
}

export interface ApprovalRequest {
  id: string;
  request: string;
  agent: string;
  requestedBy: string;
  riskLevel: "critical" | "high" | "medium" | "low";
  requestedTime: string;
}

export interface SecurityEvent {
  id: string;
  event: string;
  description: string;
  timestamp: string; // relative
  type: "block" | "trigger" | "detection" | "approval" | "audit" | "update";
}

export interface GovernanceInsight {
  id: string;
  title: string;
  type: "policy" | "department" | "risk" | "approval" | "recommendation" | "compliance";
  metric: string;
  subtext: string;
  badgeText: string;
  recommendation: string;
}

export interface AuditHistoryEntry {
  id: string;
  event: string;
  agent: string;
  user: string;
  timestamp: string;
  outcome: "passed" | "blocked" | "approved" | "rejected" | "reviewed" | "updated";
  severity: "low" | "medium" | "high" | "critical";
}

// ─── Section 1: KPI CARDS ──────────────────────────────────────────────────
export const governanceKPIs: GovernanceKPICard[] = [
  {
    title: "Active Policies",
    value: "48",
    change: "+12.5%",
    trend: "up",
    sparkline: [40, 42, 42, 45, 46, 46, 48],
    status: "success",
    statusText: "Fully Enforced",
  },
  {
    title: "Compliance Score",
    value: "99.7%",
    change: "+0.3%",
    trend: "up",
    sparkline: [99.2, 99.4, 99.3, 99.5, 99.6, 99.6, 99.7],
    status: "success",
    statusText: "Excellent",
  },
  {
    title: "Open Risks",
    value: "3",
    change: "-40.0%",
    trend: "down",
    sparkline: [8, 7, 5, 5, 4, 3, 3],
    status: "warning",
    statusText: "Action Required",
  },
  {
    title: "Pending Approvals",
    value: "14",
    change: "+16.7%",
    trend: "up",
    sparkline: [8, 10, 11, 10, 12, 13, 14],
    status: "info",
    statusText: "Review Queue",
  },
  {
    title: "Security Events",
    value: "12",
    change: "-25.0%",
    trend: "down",
    sparkline: [24, 20, 18, 15, 14, 13, 12],
    status: "success",
    statusText: "System Stable",
  },
  {
    title: "Governance Health",
    value: "98.6%",
    change: "+1.4%",
    trend: "up",
    sparkline: [96.5, 97.2, 97.5, 98.1, 98.0, 98.4, 98.6],
    status: "success",
    statusText: "Target Exceeded",
  },
];

// ─── Section 2: POLICY CENTER ──────────────────────────────────────────────
export const policiesData: PolicyData[] = [
  {
    id: "pol-1",
    name: "PII Protection Policy",
    category: "Data Privacy",
    appliesTo: "All Agents",
    lastUpdated: "May 12, 2024",
    compliance: 100,
    status: "active",
  },
  {
    id: "pol-2",
    name: "Prompt Safety Guardrails",
    category: "Safety & Alignment",
    appliesTo: "All Agents",
    lastUpdated: "May 11, 2024",
    compliance: 99.8,
    status: "active",
  },
  {
    id: "pol-3",
    name: "Data Access Authorization",
    category: "Access Control",
    appliesTo: "Database Agent",
    lastUpdated: "May 10, 2024",
    compliance: 99.5,
    status: "active",
  },
  {
    id: "pol-4",
    name: "LLM Output Filtering",
    category: "Content Moderation",
    appliesTo: "Customer Agent",
    lastUpdated: "May 09, 2024",
    compliance: 98.2,
    status: "warning",
  },
  {
    id: "pol-5",
    name: "Human Approval for Deletes",
    category: "Operational Trust",
    appliesTo: "Orchestrator Agent",
    lastUpdated: "May 08, 2024",
    compliance: 100,
    status: "active",
  },
  {
    id: "pol-6",
    name: "LLM Rate Limiting",
    category: "Cost Control",
    appliesTo: "All Agents",
    lastUpdated: "May 07, 2024",
    compliance: 100,
    status: "draft",
  },
  {
    id: "pol-7",
    name: "Immutable Audit Logging",
    category: "Compliance",
    appliesTo: "All Agents",
    lastUpdated: "May 06, 2024",
    compliance: 100,
    status: "active",
  },
  {
    id: "pol-8",
    name: "External API Restrictions",
    category: "Security",
    appliesTo: "Browser Agent",
    lastUpdated: "May 05, 2024",
    compliance: 94.5,
    status: "disabled",
  },
];

// ─── Section 3: RISK DASHBOARD ──────────────────────────────────────────────
export const risksData: RiskData[] = [
  {
    id: "risk-1",
    title: "High Risk Requests",
    level: "high",
    affectedAgent: "Database Agent",
    occurrences: 8,
    status: "Active Monitoring",
    recommendation: "Review custom SQL generation schemas and restrict write permissions.",
  },
  {
    id: "risk-2",
    title: "Policy Violations",
    level: "critical",
    affectedAgent: "Orchestrator Agent",
    occurrences: 2,
    status: "Mitigation Pending",
    recommendation: "Halt orchestrator access to HR shared directories until governance check passes.",
  },
  {
    id: "risk-3",
    title: "Blocked Actions",
    level: "medium",
    affectedAgent: "Browser Agent",
    occurrences: 42,
    status: "Handled Automatically",
    recommendation: "Audit browser navigation links against blocked domain lists.",
  },
  {
    id: "risk-4",
    title: "Sensitive Data Access",
    level: "high",
    affectedAgent: "Research Agent",
    occurrences: 14,
    status: "Requires Override",
    recommendation: "Enforce pattern scanning filters for passport and customer SSN data.",
  },
  {
    id: "risk-5",
    title: "Unauthorized Tools Usage",
    level: "medium",
    affectedAgent: "Planner Agent",
    occurrences: 5,
    status: "Under Review",
    recommendation: "Whitelist agent CLI terminal commands and restrict docker executions.",
  },
  {
    id: "risk-6",
    title: "Prompt Injection Attempts",
    level: "critical",
    affectedAgent: "Customer Agent",
    occurrences: 3,
    status: "Investigating IP",
    recommendation: "Update systemic prompt templates and verify LLM payload filters.",
  },
];

// ─── Section 4: APPROVAL QUEUE ──────────────────────────────────────────────
export const approvalRequests: ApprovalRequest[] = [
  {
    id: "app-1",
    request: "Delete historical customer invoice records",
    agent: "Database Agent",
    requestedBy: "Sarah Chen (Fin-Ops)",
    riskLevel: "critical",
    requestedTime: "10 mins ago",
  },
  {
    id: "app-2",
    request: "Send quarterly marketing email campaign",
    agent: "Customer Agent",
    requestedBy: "James Anderson (Marketing)",
    riskLevel: "medium",
    requestedTime: "25 mins ago",
  },
  {
    id: "app-3",
    request: "Export customer cohort survey responses",
    agent: "Research Agent",
    requestedBy: "Alex Morgan (Admin)",
    riskLevel: "high",
    requestedTime: "1 hour ago",
  },
  {
    id: "app-4",
    request: "Run server cleaning bash script on staging cluster",
    agent: "Computer Use Agent",
    requestedBy: "Michael Brown (DevOps)",
    riskLevel: "critical",
    requestedTime: "3 hours ago",
  },
  {
    id: "app-5",
    request: "Read raw payroll ledger details",
    agent: "Database Agent",
    requestedBy: "Sarah Chen (Fin-Ops)",
    riskLevel: "high",
    requestedTime: "4 hours ago",
  },
];

// ─── Section 5: COMPLIANCE CHARTS ───────────────────────────────────────────
export const monthlyComplianceTrend = [
  { date: "Jan", compliance: 98.4, audits: 88, violations: 12 },
  { date: "Feb", compliance: 98.7, audits: 92, violations: 8 },
  { date: "Mar", compliance: 99.1, audits: 95, violations: 6 },
  { date: "Apr", compliance: 99.4, audits: 99, violations: 4 },
  { date: "May", compliance: 99.7, audits: 100, violations: 3 },
];

export const riskDistribution = [
  { name: "Critical Risk", value: 3, fill: "#EF4444" },
  { name: "High Risk", value: 14, fill: "#F97316" },
  { name: "Medium Risk", value: 47, fill: "#EAB308" },
  { name: "Low Risk", value: 120, fill: "#38B88A" },
];

export const violationCategories = [
  { category: "Data Access", count: 42, fill: "#38B88A" },
  { category: "PII Detection", count: 28, fill: "#2F9F77" },
  { category: "Tool Usage", count: 18, fill: "#4a8c70" },
  { category: "Injection Attack", count: 11, fill: "#96cead" },
  { category: "API Rate", count: 6, fill: "#6AAF8A" },
];

// ─── Section 6: SECURITY EVENTS ─────────────────────────────────────────────
export const securityEvents: SecurityEvent[] = [
  {
    id: "sec-1",
    event: "Prompt Injection Blocked",
    description: "System successfully blocked prompt injection payload triggered by customer agent chat session.",
    timestamp: "2 mins ago",
    type: "block",
  },
  {
    id: "sec-2",
    event: "PII Policy Rule Triggered",
    description: "Research agent output checked against customer SSN formats. Action held for review.",
    timestamp: "12 mins ago",
    type: "trigger",
  },
  {
    id: "sec-3",
    event: "Sensitive Data Masked",
    description: "Email routing agent masked passport numbers inside financial transaction attachment logs.",
    timestamp: "45 mins ago",
    type: "detection",
  },
  {
    id: "sec-4",
    event: "Agent Database Access Denied",
    description: "Browser agent request to inspect production Postgres database rejected by governance router.",
    timestamp: "2 hours ago",
    type: "block",
  },
  {
    id: "sec-5",
    event: "High Risk Approval Granted",
    description: "Human admin approved Database Agent export operation for cohort survey datasets.",
    timestamp: "3 hours ago",
    type: "approval",
  },
  {
    id: "sec-6",
    event: "Quarterly Audit Report Verified",
    description: "External auditor finished verification scan for 100k agent events. Compliance score confirmed.",
    timestamp: "8 hours ago",
    type: "audit",
  },
  {
    id: "sec-7",
    event: "Policy Constraint Updated",
    description: "Updated HR database scoping rules on planning agents. Policy version is now 1.8-stable.",
    timestamp: "1 day ago",
    type: "update",
  },
];

// ─── Section 7: GOVERNANCE INSIGHTS ─────────────────────────────────────────
export const governanceInsights: GovernanceInsight[] = [
  {
    id: "gin-1",
    title: "Top Policy Triggered",
    type: "policy",
    metric: "PII Masking Filter",
    subtext: "Triggered 143 times this month, preventing potential identity leaks.",
    badgeText: "High Frequency",
    recommendation: "Incorporate client-side pre-processing regex validation checks.",
  },
  {
    id: "gin-2",
    title: "Most Secure Department",
    type: "department",
    metric: "Finance division",
    subtext: "Achieved zero policy violations across 1,120 agent actions.",
    badgeText: "Optimal Behavior",
    recommendation: "Adopt Finance department's read-only credential scoping system.",
  },
  {
    id: "gin-3",
    title: "Highest Risk Workflow",
    type: "risk",
    metric: "Direct CLI Writing",
    subtext: "Terminal execution tasks generated 80% of critical safety warnings.",
    badgeText: "Safety Alert",
    recommendation: "Limit Computer Use agent terminal operations to predefined docker environments.",
  },
  {
    id: "gin-4",
    title: "Most Active Approval Queue",
    type: "approval",
    metric: "Database Executions",
    subtext: "Pending approvals grid has averaged 14 requests daily this week.",
    badgeText: "Queue Peak",
    recommendation: "Establish tiered auto-approval limits for low-risk tables.",
  },
  {
    id: "gin-5",
    title: "Governance Recommendation",
    type: "recommendation",
    metric: "Audit Logging Versioning",
    subtext: "Upgrade local ledger indexes to cryptographic hash audit structures.",
    badgeText: "Actionable",
    recommendation: "Enable immutable audit hashes for data safety tracking.",
  },
  {
    id: "gin-6",
    title: "Compliance Opportunity",
    type: "compliance",
    metric: "Scoping Update",
    subtext: "Updating policy version to 1.9 will close identified API security gaps.",
    badgeText: "Improvement",
    recommendation: "Deploy external endpoint restriction updates across Browser Agents.",
  },
];

// ─── Section 8: AUDIT HISTORY ───────────────────────────────────────────────
export const auditHistory: AuditHistoryEntry[] = [
  {
    id: "AUD-8402",
    event: "PII Masking Filter Checked",
    agent: "Research Agent",
    user: "Sarah Chen",
    timestamp: "May 12, 2024 14:22",
    outcome: "passed",
    severity: "low",
  },
  {
    id: "AUD-8395",
    event: "Write Transaction Request Blocked",
    agent: "Database Agent",
    user: "System Admin",
    timestamp: "May 12, 2024 13:05",
    outcome: "blocked",
    severity: "critical",
  },
  {
    id: "AUD-8354",
    event: "Manual Approval Granted",
    agent: "Customer Agent",
    user: "Alex Morgan",
    timestamp: "May 11, 2024 16:45",
    outcome: "approved",
    severity: "high",
  },
  {
    id: "AUD-8312",
    event: "CLI Command Execution Checked",
    agent: "Planner Agent",
    user: "Sarah Chen",
    timestamp: "May 10, 2024 11:20",
    outcome: "passed",
    severity: "medium",
  },
  {
    id: "AUD-8280",
    event: "External API Access Denied",
    agent: "Browser Agent",
    user: "System Router",
    timestamp: "May 09, 2024 09:30",
    outcome: "blocked",
    severity: "high",
  },
  {
    id: "AUD-8241",
    event: "HR Scoping Rules Updated",
    agent: "Orchestrator Agent",
    user: "Alex Morgan",
    timestamp: "May 08, 2024 15:10",
    outcome: "updated",
    severity: "medium",
  },
];

// ─── Section 9: ROI SUMMARY ─────────────────────────────────────────────────
export interface ExecutiveGovSummary {
  complianceScore: string;
  policyCoverage: string;
  riskReduction: string;
  auditSuccess: string;
  trustScore: string;
}

export const govSummary: ExecutiveGovSummary = {
  complianceScore: "99.7%",
  policyCoverage: "100%",
  riskReduction: "48.2%",
  auditSuccess: "99.9%",
  trustScore: "98.6/100",
};
