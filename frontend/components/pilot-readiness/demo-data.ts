export const DEMO_ORGANIZATION = {
  id: "org-acmecorp",
  name: "AcmeCorp Inc.",
  industry: "Technology & Manufacturing",
  size: "5,000+ employees",
  location: "Global (HQ: San Francisco)",
  tenants: 3,
  departments: 8,
}

export interface Department {
  id: string
  name: string
  headCount: number
  budget: number
  leadName: string
}

export const DEMO_DEPARTMENTS: Department[] = [
  { id: "dept-eng", name: "Engineering", headCount: 320, budget: 4500000, leadName: "Alice Chen" },
  { id: "dept-mkt", name: "Marketing", headCount: 85, budget: 2100000, leadName: "Bob Martinez" },
  { id: "dept-sales", name: "Sales", headCount: 140, budget: 3800000, leadName: "Carol Kim" },
  { id: "dept-fin", name: "Finance", headCount: 45, budget: 1200000, leadName: "David Okafor" },
  { id: "dept-hr", name: "HR", headCount: 30, budget: 800000, leadName: "Elena Rossi" },
  { id: "dept-ops", name: "Operations", headCount: 95, budget: 1900000, leadName: "Frank Delgado" },
  { id: "dept-legal", name: "Legal", headCount: 18, budget: 950000, leadName: "Grace Liu" },
  { id: "dept-cs", name: "Customer Success", headCount: 72, budget: 1600000, leadName: "Henry Park" },
]

export interface User {
  id: string
  name: string
  email: string
  role: string
  department: string
  status: "active" | "invited"
  mfaEnabled: boolean
  lastLogin: string
  avatar: string
}

function initialsAvatar(name: string): string {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
  const hue = name.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) % 360
  return `data:image/svg+xml,${encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40"><rect width="40" height="40" rx="8" fill="hsl(${hue},55%,75%)"/><text x="20" y="20" text-anchor="middle" dominant-baseline="central" font-family="system-ui,sans-serif" font-size="16" font-weight="600" fill="hsl(${hue},40%,20%)">${initials}</text></svg>`,
  )}`
}

export const DEMO_USERS: User[] = [
  { id: "user-alice", name: "Alice Chen", email: "alice.chen@acmecorp.com", role: "VP Engineering", department: "Engineering", status: "active", mfaEnabled: true, lastLogin: "2026-07-04T08:12:00Z", avatar: initialsAvatar("Alice Chen") },
  { id: "user-bob", name: "Bob Martinez", email: "bob.martinez@acmecorp.com", role: "CMO", department: "Marketing", status: "active", mfaEnabled: true, lastLogin: "2026-07-03T14:30:00Z", avatar: initialsAvatar("Bob Martinez") },
  { id: "user-carol", name: "Carol Kim", email: "carol.kim@acmecorp.com", role: "SVP Sales", department: "Sales", status: "active", mfaEnabled: true, lastLogin: "2026-07-04T09:45:00Z", avatar: initialsAvatar("Carol Kim") },
  { id: "user-david", name: "David Okafor", email: "david.okafor@acmecorp.com", role: "CFO", department: "Finance", status: "active", mfaEnabled: true, lastLogin: "2026-07-02T16:00:00Z", avatar: initialsAvatar("David Okafor") },
  { id: "user-elena", name: "Elena Rossi", email: "elena.rossi@acmecorp.com", role: "VP People", department: "HR", status: "active", mfaEnabled: false, lastLogin: "2026-07-01T11:20:00Z", avatar: initialsAvatar("Elena Rossi") },
  { id: "user-frank", name: "Frank Delgado", email: "frank.delgado@acmecorp.com", role: "COO", department: "Operations", status: "active", mfaEnabled: true, lastLogin: "2026-07-04T07:30:00Z", avatar: initialsAvatar("Frank Delgado") },
  { id: "user-grace", name: "Grace Liu", email: "grace.liu@acmecorp.com", role: "General Counsel", department: "Legal", status: "active", mfaEnabled: true, lastLogin: "2026-07-03T10:15:00Z", avatar: initialsAvatar("Grace Liu") },
  { id: "user-henry", name: "Henry Park", email: "henry.park@acmecorp.com", role: "VP Customer Success", department: "Customer Success", status: "active", mfaEnabled: false, lastLogin: "2026-07-04T06:50:00Z", avatar: initialsAvatar("Henry Park") },
  { id: "user-ivy", name: "Ivy Nakamura", email: "ivy.nakamura@acmecorp.com", role: "Staff Engineer", department: "Engineering", status: "active", mfaEnabled: true, lastLogin: "2026-07-04T08:05:00Z", avatar: initialsAvatar("Ivy Nakamura") },
  { id: "user-jack", name: "Jack Thompson", email: "jack.thompson@acmecorp.com", role: "Data Engineer", department: "Engineering", status: "active", mfaEnabled: false, lastLogin: "2026-07-03T19:40:00Z", avatar: initialsAvatar("Jack Thompson") },
  { id: "user-karen", name: "Karen Singh", email: "karen.singh@acmecorp.com", role: "Product Manager", department: "Marketing", status: "invited", mfaEnabled: false, lastLogin: "", avatar: initialsAvatar("Karen Singh") },
  { id: "user-leo", name: "Leo Andersen", email: "leo.andersen@acmecorp.com", role: "Solutions Architect", department: "Sales", status: "active", mfaEnabled: true, lastLogin: "2026-07-02T13:55:00Z", avatar: initialsAvatar("Leo Andersen") },
]

export interface Project {
  id: string
  name: string
  department: string
  status: "active" | "completed" | "on-hold" | "planning"
  progress: number
  startDate: string
  deadline: string
  leadName: string
}

export const DEMO_PROJECTS: Project[] = [
  { id: "proj-digital", name: "Digital Workplace", department: "Engineering", status: "active", progress: 72, startDate: "2026-01-15", deadline: "2026-09-30", leadName: "Alice Chen" },
  { id: "proj-ai", name: "AI Assistant", department: "Engineering", status: "active", progress: 45, startDate: "2026-03-01", deadline: "2026-12-15", leadName: "Ivy Nakamura" },
  { id: "proj-portal", name: "Customer Portal", department: "Customer Success", status: "active", progress: 88, startDate: "2025-11-01", deadline: "2026-08-01", leadName: "Henry Park" },
  { id: "proj-datalake", name: "Data Lake", department: "Engineering", status: "completed", progress: 100, startDate: "2025-06-01", deadline: "2026-04-30", leadName: "Jack Thompson" },
  { id: "proj-security", name: "Security Audit", department: "Legal", status: "active", progress: 30, startDate: "2026-05-15", deadline: "2026-10-31", leadName: "Grace Liu" },
  { id: "proj-mobile", name: "Mobile App", department: "Marketing", status: "planning", progress: 10, startDate: "2026-07-15", deadline: "2027-03-31", leadName: "Karen Singh" },
]

export interface Repository {
  id: string
  name: string
  language: string
  stars: number
  forks: number
  lastCommit: string
  branch: string
}

export const DEMO_REPOSITORIES: Repository[] = [
  { id: "repo-cortex", name: "cortex-core", language: "TypeScript", stars: 847, forks: 203, lastCommit: "2026-07-04T10:22:00Z", branch: "main" },
  { id: "repo-ai", name: "ai-assistant", language: "Python", stars: 512, forks: 98, lastCommit: "2026-07-03T16:45:00Z", branch: "develop" },
  { id: "repo-portal", name: "customer-portal", language: "TypeScript", stars: 234, forks: 67, lastCommit: "2026-07-04T08:10:00Z", branch: "main" },
  { id: "repo-datalake", name: "data-lake-pipeline", language: "Scala", stars: 156, forks: 42, lastCommit: "2026-06-28T12:30:00Z", branch: "main" },
  { id: "repo-mobile", name: "mobile-app", language: "Kotlin", stars: 89, forks: 23, lastCommit: "2026-07-02T09:15:00Z", branch: "feature/onboarding" },
  { id: "repo-security", name: "security-toolkit", language: "Rust", stars: 312, forks: 78, lastCommit: "2026-07-01T14:20:00Z", branch: "main" },
  { id: "repo-docs", name: "acmecorp-docs", language: "Markdown", stars: 45, forks: 156, lastCommit: "2026-07-04T06:00:00Z", branch: "main" },
  { id: "repo-infra", name: "infra-as-code", language: "HCL", stars: 178, forks: 54, lastCommit: "2026-06-30T11:40:00Z", branch: "develop" },
]

export interface JiraIssue {
  id: string
  summary: string
  type: "Bug" | "Task" | "Story" | "Epic"
  status: "Open" | "In Progress" | "In Review" | "Done" | "Backlog"
  priority: "Low" | "Medium" | "High" | "Critical"
  assignee: string
  sprint: string
}

export const DEMO_JIRA_ISSUES: JiraIssue[] = [
  { id: "ACM-101", summary: "SSO login redirect fails on Firefox", type: "Bug", status: "In Progress", priority: "Critical", assignee: "Ivy Nakamura", sprint: "Sprint 12" },
  { id: "ACM-102", summary: "Implement role-based access control for admin panel", type: "Story", status: "In Review", priority: "High", assignee: "Alice Chen", sprint: "Sprint 12" },
  { id: "ACM-103", summary: "Update API rate limit documentation", type: "Task", status: "Done", priority: "Low", assignee: "Jack Thompson", sprint: "Sprint 11" },
  { id: "ACM-104", summary: "Dashboard performance optimization", type: "Epic", status: "In Progress", priority: "High", assignee: "Alice Chen", sprint: "Sprint 12" },
  { id: "ACM-105", summary: "Data export fails for datasets over 10k rows", type: "Bug", status: "Open", priority: "High", assignee: "Jack Thompson", sprint: "Sprint 12" },
  { id: "ACM-106", summary: "Add dark mode support to customer portal", type: "Story", status: "Backlog", priority: "Medium", assignee: "Ivy Nakamura", sprint: "Sprint 13" },
  { id: "ACM-107", summary: "Migrate CI/CD pipeline to GitHub Actions", type: "Task", status: "Done", priority: "Medium", assignee: "Frank Delgado", sprint: "Sprint 10" },
  { id: "ACM-108", summary: "Audit third-party dependency licenses", type: "Task", status: "In Progress", priority: "Critical", assignee: "Grace Liu", sprint: "Sprint 12" },
  { id: "ACM-109", summary: "Real-time notification system", type: "Epic", status: "Backlog", priority: "Medium", assignee: "Henry Park", sprint: "Sprint 14" },
  { id: "ACM-110", summary: "Search results missing for special characters", type: "Bug", status: "Open", priority: "Medium", assignee: "Leo Andersen", sprint: "Sprint 12" },
  { id: "ACM-111", summary: "Onboarding wizard for new tenants", type: "Story", status: "In Review", priority: "High", assignee: "Karen Singh", sprint: "Sprint 12" },
  { id: "ACM-112", summary: "Quarterly compliance report automation", type: "Task", status: "Done", priority: "Low", assignee: "Grace Liu", sprint: "Sprint 11" },
]

export interface Mission {
  id: string
  objective: string
  status: "completed" | "failed" | "running" | "pending"
  agent: string
  startedAt: string
  duration: string
  confidence: number
  tokens: number
}

export const DEMO_MISSIONS: Mission[] = [
  { id: "mis-001", objective: "Analyze Q3 revenue trends across regions", status: "completed", agent: "Analyst", startedAt: "2026-07-04T08:00:00Z", duration: "1m 42s", confidence: 94, tokens: 2840 },
  { id: "mis-002", objective: "Draft quarterly board summary memo", status: "completed", agent: "Writer", startedAt: "2026-07-04T08:05:00Z", duration: "2m 13s", confidence: 88, tokens: 4150 },
  { id: "mis-003", objective: "Audit IAM roles for least-privilege compliance", status: "completed", agent: "Security Auditor", startedAt: "2026-07-04T07:30:00Z", duration: "4m 07s", confidence: 97, tokens: 6200 },
  { id: "mis-004", objective: "Generate customer churn prediction model", status: "running", agent: "Data Scientist", startedAt: "2026-07-04T09:15:00Z", duration: "12m 30s", confidence: 76, tokens: 18300 },
  { id: "mis-005", objective: "Summarize 50 support tickets from past week", status: "completed", agent: "Analyst", startedAt: "2026-07-03T22:00:00Z", duration: "3m 05s", confidence: 91, tokens: 5200 },
  { id: "mis-006", objective: "Cross-reference vendor contracts for renewal dates", status: "completed", agent: "Researcher", startedAt: "2026-07-04T06:00:00Z", duration: "5m 20s", confidence: 85, tokens: 8900 },
  { id: "mis-007", objective: "Export and sanitize PII from staging DB", status: "pending", agent: "Data Engineer", startedAt: "", duration: "", confidence: 0, tokens: 0 },
  { id: "mis-008", objective: "Compare competitor pricing vs AcmeCorp tiers", status: "completed", agent: "Researcher", startedAt: "2026-07-03T15:30:00Z", duration: "2m 48s", confidence: 82, tokens: 5100 },
  { id: "mis-009", objective: "Optimize cloud spend for unused EC2 instances", status: "failed", agent: "Optimizer", startedAt: "2026-07-02T11:00:00Z", duration: "1m 10s", confidence: 45, tokens: 1800 },
  { id: "mis-010", objective: "Generate monthly SOC 2 compliance report", status: "completed", agent: "Compliance Officer", startedAt: "2026-07-01T00:00:00Z", duration: "8m 15s", confidence: 99, tokens: 14500 },
]

export interface KnowledgeGraphEntity {
  id: string
  type: "agent" | "concept" | "memory"
  name: string
  properties: Record<string, string>
}

export const DEMO_KNOWLEDGE_GRAPH: KnowledgeGraphEntity[] = [
  { id: "kg-agent-1", type: "agent", name: "Orchestrator", properties: { version: "2.4.1", status: "active", upstream: "system" } },
  { id: "kg-agent-2", type: "agent", name: "ResearchAgent", properties: { model: "gpt-4o", maxRetries: "3", timeout: "30s" } },
  { id: "kg-agent-3", type: "agent", name: "SecurityAuditor", properties: { scope: "IAM,Network,Secrets", ruleset: "cis-v8" } },
  { id: "kg-concept-1", type: "concept", name: "Zero Trust Architecture", properties: { domain: "security", maturity: "implementing" } },
  { id: "kg-concept-2", type: "concept", name: "Q3 Digital Transformation", properties: { initiative: "digital-transformation", quarter: "Q3-2026" } },
  { id: "kg-concept-3", type: "concept", name: "GDPR Compliance", properties: { regulation: "GDPR", jurisdiction: "EU", status: "audited" } },
  { id: "kg-concept-4", type: "concept", name: "Data Lake Architecture", properties: { tech: "Apache Iceberg", storage: "S3", format: "Parquet" } },
  { id: "kg-concept-5", type: "concept", name: "Customer 360", properties: { source: "CRM,Support,Product", freshness: "real-time" } },
  { id: "kg-memory-1", type: "memory", name: "Previous audit findings", properties: { severity: "medium", count: "12", resolved: "10" } },
  { id: "kg-memory-2", type: "memory", name: "Vendor approval workflow", properties: { owner: "Grace Liu", steps: "4", sla: "48h" } },
  { id: "kg-memory-3", type: "memory", name: "SSO migration notes", properties: { provider: "Okta", migrated: "85%", issues: "3" } },
  { id: "kg-memory-4", type: "memory", name: "Cloud cost optimization playbook", properties: { savings: "$240k/yr", services: "EC2,RDS,CloudFront" } },
  { id: "kg-memory-5", type: "memory", name: "Employee onboarding checklist", properties: { steps: "22", avgTime: "3.5d", automation: "60%" } },
  { id: "kg-concept-6", type: "concept", name: "SOC 2 Type II", properties: { status: "in-progress", auditor: "Deloitte", due: "2026-09-30" } },
  { id: "kg-memory-6", type: "memory", name: "Incident response runbook", properties: { severity: "P0-P3", lastTested: "2026-06-15", ttr: "18m" } },
]

export interface MemoryRecord {
  id: string
  type: "working" | "semantic" | "episodic"
  content: string
  agent: string
  timestamp: string
  relevance: number
}

export const DEMO_MEMORY_RECORDS: MemoryRecord[] = [
  { id: "mem-w-1", type: "working", content: "Processing Q3 revenue data for regional breakdown analysis", agent: "Analyst", timestamp: "2026-07-04T08:00:15Z", relevance: 95 },
  { id: "mem-w-2", type: "working", content: "Drafting board memo — waiting for revenue finalization", agent: "Writer", timestamp: "2026-07-04T08:05:30Z", relevance: 88 },
  { id: "mem-s-1", type: "semantic", content: "AcmeCorp operates in 14 countries with primary revenue from North America (62%)", agent: "Analyst", timestamp: "2026-07-03T22:00:00Z", relevance: 80 },
  { id: "mem-s-2", type: "semantic", content: "IAM least-privilege policy requires approval for cross-account role creation", agent: "Security Auditor", timestamp: "2026-07-04T07:30:00Z", relevance: 92 },
  { id: "mem-e-1", type: "episodic", content: "Previous SOC 2 audit flagged missing access reviews for dept-admin roles", agent: "Compliance Officer", timestamp: "2026-06-15T10:00:00Z", relevance: 78 },
  { id: "mem-e-2", type: "episodic", content: "Cloud optimization mission failed due to insufficient permissions in prod account", agent: "Optimizer", timestamp: "2026-07-02T11:01:10Z", relevance: 85 },
  { id: "mem-w-3", type: "working", content: "Churn model training — feature engineering phase 80% complete", agent: "Data Scientist", timestamp: "2026-07-04T09:30:00Z", relevance: 91 },
  { id: "mem-s-3", type: "semantic", content: "Vendor contracts renew quarterly on Jan/Apr/Jul/Oct cycle", agent: "Researcher", timestamp: "2026-07-04T06:00:00Z", relevance: 73 },
  { id: "mem-e-3", type: "episodic", content: "Customer reported portal outage on 2026-06-28 — resolved in 14m via cache warmup", agent: "Engineer", timestamp: "2026-06-28T09:15:00Z", relevance: 65 },
  { id: "mem-s-4", type: "semantic", content: "PII sanitization script requires DPA confirmation before staging export", agent: "Data Engineer", timestamp: "2026-07-04T06:30:00Z", relevance: 96 },
]

export interface Approval {
  id: string
  action: string
  requester: string
  riskLevel: "low" | "medium" | "high" | "critical"
  status: "pending" | "approved" | "rejected"
  decidedBy: string
  decidedAt: string
}

export const DEMO_APPROVALS: Approval[] = [
  { id: "apr-001", action: "Deploy to production (v2.8.1)", requester: "Alice Chen", riskLevel: "high", status: "approved", decidedBy: "David Okafor", decidedAt: "2026-07-04T09:00:00Z" },
  { id: "apr-002", action: "AWS root account access request", requester: "Jack Thompson", riskLevel: "critical", status: "pending", decidedBy: "", decidedAt: "" },
  { id: "apr-003", action: "Vendor contract renewal — DataDog ($120k/yr)", requester: "Frank Delgado", riskLevel: "medium", status: "approved", decidedBy: "David Okafor", decidedAt: "2026-07-03T14:00:00Z" },
  { id: "apr-004", action: "Change RBAC policy for contractor group", requester: "Grace Liu", riskLevel: "high", status: "rejected", decidedBy: "Alice Chen", decidedAt: "2026-07-02T11:30:00Z" },
  { id: "apr-005", action: "New integration: Salesforce -> Data Lake", requester: "Henry Park", riskLevel: "medium", status: "pending", decidedBy: "", decidedAt: "" },
  { id: "apr-006", action: "Hiring budget for 3 senior engineers", requester: "Elena Rossi", riskLevel: "low", status: "approved", decidedBy: "David Okafor", decidedAt: "2026-07-01T10:00:00Z" },
  { id: "apr-007", action: "Export customer PII for analytics sandbox", requester: "Carol Kim", riskLevel: "critical", status: "rejected", decidedBy: "Grace Liu", decidedAt: "2026-06-30T16:45:00Z" },
  { id: "apr-008", action: "Schedule security penetration test", requester: "Grace Liu", riskLevel: "high", status: "approved", decidedBy: "Frank Delgado", decidedAt: "2026-07-04T08:00:00Z" },
]

export interface ConnectorActivity {
  connector: string
  action: string
  status: "success" | "error" | "running"
  duration: string
  timestamp: string
}

export const DEMO_CONNECTOR_ACTIVITY: ConnectorActivity[] = [
  { connector: "GitHub", action: "Sync PRs & commits", status: "success", duration: "1.2s", timestamp: "2026-07-04T10:22:00Z" },
  { connector: "Jira", action: "Fetch sprint issues", status: "success", duration: "0.8s", timestamp: "2026-07-04T10:20:00Z" },
  { connector: "Slack", action: "Post deployment notification", status: "success", duration: "0.3s", timestamp: "2026-07-04T09:01:00Z" },
  { connector: "AWS", action: "Check EC2 instance metrics", status: "success", duration: "1.7s", timestamp: "2026-07-04T09:00:00Z" },
  { connector: "DataDog", action: "Query dashboard data", status: "error", duration: "4.5s", timestamp: "2026-07-04T08:55:00Z" },
  { connector: "Salesforce", action: "Pull opportunity pipeline", status: "running", duration: "3.2s", timestamp: "2026-07-04T10:25:00Z" },
  { connector: "Okta", action: "Verify SSO session", status: "success", duration: "0.5s", timestamp: "2026-07-04T10:18:00Z" },
  { connector: "PagerDuty", action: "Acknowledge alert", status: "success", duration: "0.2s", timestamp: "2026-07-04T08:30:00Z" },
  { connector: "Snowflake", action: "Run analytics query", status: "success", duration: "2.1s", timestamp: "2026-07-04T10:15:00Z" },
  { connector: "Confluence", action: "Update runbook page", status: "error", duration: "0.9s", timestamp: "2026-07-04T09:15:00Z" },
]

export interface AuditLog {
  id: string
  actor: string
  action: string
  resource: string
  category: "auth" | "data" | "config" | "deploy" | "access"
  timestamp: string
  details: string
}

export const DEMO_AUDIT_LOGS: AuditLog[] = [
  { id: "audit-001", actor: "Alice Chen", action: "deploy.create", resource: "cortex-core:v2.8.1", category: "deploy", timestamp: "2026-07-04T09:00:00Z", details: "Deployed to production cluster us-east-1a" },
  { id: "audit-002", actor: "system", action: "auth.mfa_challenge", resource: "user:jack.thompson", category: "auth", timestamp: "2026-07-04T08:45:00Z", details: "MFA challenge passed from IP 203.0.113.42" },
  { id: "audit-003", actor: "Grace Liu", action: "config.rbac.update", resource: "contractor-group-policy", category: "config", timestamp: "2026-07-02T11:25:00Z", details: "Attempted RBAC update — rejected by policy (APPROVAL_REQUIRED)" },
  { id: "audit-004", actor: "David Okafor", action: "approval.grant", resource: "deploy.create", category: "access", timestamp: "2026-07-04T09:00:01Z", details: "Approved production deployment for v2.8.1" },
  { id: "audit-005", actor: "system", action: "data.export", resource: "analytics-sandbox.customer_360", category: "data", timestamp: "2026-07-04T06:30:00Z", details: "Automated data export — 1.2M rows to parquet" },
  { id: "audit-006", actor: "Ivy Nakamura", action: "auth.login", resource: "user:ivy.nakamura", category: "auth", timestamp: "2026-07-04T08:05:00Z", details: "Login from SF office VPN (MFA: true)" },
  { id: "audit-007", actor: "system", action: "config.backup", resource: "global-config", category: "config", timestamp: "2026-07-04T04:00:00Z", details: "Daily config backup completed — 14.2 MB" },
  { id: "audit-008", actor: "Carol Kim", action: "data.query", resource: "sales.pipeline", category: "data", timestamp: "2026-07-04T09:45:00Z", details: "Exported opportunity pipeline — 340 records" },
  { id: "audit-009", actor: "system", action: "deploy.rollback", resource: "ai-assistant:v1.9.2", category: "deploy", timestamp: "2026-07-03T17:00:00Z", details: "Auto-rollback triggered — canary failure rate 12%" },
  { id: "audit-010", actor: "Henry Park", action: "access.role_escalation", resource: "support-admin-role", category: "access", timestamp: "2026-07-04T06:50:00Z", details: "Temporary role escalation for 24h — incident INC-3421" },
  { id: "audit-011", actor: "Frank Delgado", action: "config.feature_flag", resource: "ai-assistant:new-skill-mgmt", category: "config", timestamp: "2026-07-04T07:30:00Z", details: "Enabled feature flag for 10% of users" },
  { id: "audit-012", actor: "system", action: "auth.mfa_disabled", resource: "user:elena.rossi", category: "auth", timestamp: "2026-07-01T11:20:00Z", details: "MFA disabled by admin request — ticket SEC-112" },
]

export const DEMO_DASHBOARD_METRICS = {
  missionsCompleted: 248,
  missionsFailed: 12,
  totalTokens: 2842000,
  totalCost: 142.83,
  activeUsers: 48,
  workersActive: 12,
  avgResponseTime: 342,
  uptime: 99.97,
}
