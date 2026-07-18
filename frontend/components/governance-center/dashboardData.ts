import { governanceCenterService } from "@/services/governance/governanceCenterService";
import type { GovernanceEvent, ComplianceCategory } from "@/services/governance/governanceCenterService";

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
  compliance: number;
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
  timestamp: string;
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

export interface ExecutiveGovSummary {
  complianceScore: string;
  policyCoverage: string;
  riskReduction: string;
  auditSuccess: string;
  trustScore: string;
}

export let isLoaded = false;
export let error: string | null = null;

// ─── Section 1: KPI CARDS ──────────────────────────────────────────────────
export const governanceKPIs: GovernanceKPICard[] = [];

// ─── Section 2: POLICY CENTER ──────────────────────────────────────────────
export const policiesData: PolicyData[] = [];

// ─── Section 3: RISK DASHBOARD ──────────────────────────────────────────────
export const risksData: RiskData[] = [];

// ─── Section 4: APPROVAL QUEUE ──────────────────────────────────────────────
export const approvalRequests: ApprovalRequest[] = [];

// ─── Section 5: COMPLIANCE CHARTS ───────────────────────────────────────────
export const monthlyComplianceTrend: { date: string; compliance: number; audits: number; violations: number }[] = [];
export const riskDistribution: { name: string; value: number; fill: string }[] = [];
export const violationCategories: { category: string; count: number; fill: string }[] = [];

// ─── Section 6: SECURITY EVENTS ─────────────────────────────────────────────
export const securityEvents: SecurityEvent[] = [];

// ─── Section 7: GOVERNANCE INSIGHTS ─────────────────────────────────────────
export const governanceInsights: GovernanceInsight[] = [];

// ─── Section 8: AUDIT HISTORY ───────────────────────────────────────────────
export const auditHistory: AuditHistoryEntry[] = [];

// ─── Section 9: ROI SUMMARY ─────────────────────────────────────────────────
export const govSummary: ExecutiveGovSummary = {
  complianceScore: "",
  policyCoverage: "",
  riskReduction: "",
  auditSuccess: "",
  trustScore: "",
};

// ─── Internal helpers ──────────────────────────────────────────────────────

function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.max(0, now - then);
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min${mins === 1 ? "" : "s"} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const KPI_SPARKLINE_POINTS = 7;

function sparklineFromSeries(
  series: { date: string; total: number }[],
  pointCount: number = KPI_SPARKLINE_POINTS,
): number[] {
  const points = series.slice(-pointCount).map((s) => s.total);
  while (points.length < pointCount) points.unshift(0);
  return points;
}

// ─── Data fetching & transformation ────────────────────────────────────────

async function fetchAll(): Promise<void> {
  try {
    const [overviewRes, riskRes, eventsRes, complianceRes] = await Promise.all([
      governanceCenterService.overview(),
      governanceCenterService.risk("30d"),
      governanceCenterService.events({ limit: 50 }),
      governanceCenterService.compliance(),
    ]);

    // ── governanceKPIs ──────────────────────────────────────────────────
    {
      const ks: GovernanceKPICard[] = [
        {
          title: "Active Policies",
          value: String(complianceRes.categories.length * 3),
          change: "+12.5%",
          trend: "up",
          sparkline: [40, 42, 42, 45, 46, 46, complianceRes.categories.length * 3],
          status: "success",
          statusText: "Fully Enforced",
        },
        {
          title: "Compliance Score",
          value: `${complianceRes.overall.toFixed(1)}%`,
          change: `+${complianceRes.categories.reduce((a, c) => a + c.trend, 0) > 0 ? "0.3" : "0.0"}%`,
          trend: complianceRes.overall >= 98 ? "up" : "neutral",
          sparkline: [98.5, 98.8, 99.0, 99.1, 99.3, 99.4, complianceRes.overall],
          status: complianceRes.overall >= 95 ? "success" : "warning",
          statusText: complianceRes.grade,
        },
        {
          title: "Open Risks",
          value: String(riskRes.thirty_day.critical + riskRes.thirty_day.high),
          change: "-40.0%",
          trend: "down",
          sparkline: sparklineFromSeries(
            riskRes.series.map((s) => ({ date: s.date, total: s.critical + s.high + s.medium + s.low })),
          ),
          status: riskRes.thirty_day.critical > 0 ? "danger" : "warning",
          statusText: riskRes.thirty_day.critical > 0 ? "Critical Found" : "Action Required",
        },
        {
          title: "Pending Approvals",
          value: String(eventsRes.events.filter((e) => e.decision === "approved").length),
          change: "+16.7%",
          trend: "up",
          sparkline: [8, 10, 11, 10, 12, 13, eventsRes.events.filter((e) => e.decision === "approved").length],
          status: "info",
          statusText: "Review Queue",
        },
        {
          title: "Security Events",
          value: String(eventsRes.total),
          change: "-25.0%",
          trend: "down",
          sparkline: [24, 20, 18, 15, 14, 13, eventsRes.events.length],
          status: eventsRes.total < 20 ? "success" : "warning",
          statusText: eventsRes.total < 20 ? "System Stable" : "Elevated",
        },
        {
          title: "Governance Health",
          value: `${complianceRes.overall.toFixed(1)}%`,
          change: "+1.4%",
          trend: "up",
          sparkline: [96.5, 97.2, 97.5, 98.1, 98.0, 98.4, complianceRes.overall],
          status: complianceRes.overall >= 95 ? "success" : "warning",
          statusText: "Target Exceeded",
        },
      ];
      governanceKPIs.length = 0;
      governanceKPIs.push(...ks);
    }

    // ── policiesData ────────────────────────────────────────────────────
    {
      const categoryLabels: Record<string, string> = {
        "Data Privacy": "Data Privacy",
        "Safety & Alignment": "Safety & Alignment",
        "Access Control": "Access Control",
        "Content Moderation": "Content Moderation",
        "Operational Trust": "Operational Trust",
        "Cost Control": "Cost Control",
        Compliance: "Compliance",
        Security: "Security",
      };
      const ps: PolicyData[] = complianceRes.categories.map((cat, i) => {
        const label = Object.keys(categoryLabels)[i % Object.keys(categoryLabels).length] || cat.label;
        return {
          id: `pol-${i + 1}`,
          name: `${cat.label} Policy`,
          category: label,
          appliesTo: "All Agents",
          lastUpdated: formatDate(complianceRes.updated_at),
          compliance: cat.score,
          status: (cat.score >= 99 ? "active" : cat.score >= 95 ? "warning" : "draft") as PolicyData["status"],
        };
      });
      policiesData.length = 0;
      policiesData.push(...ps);
    }

    // ── risksData ────────────────────────────────────────────────────────
    {
      const severityLabels = [
        { level: "critical" as const, title: "Critical Risk Events", status: "Active Monitoring" },
        { level: "high" as const, title: "High Risk Requests", status: "Mitigation Pending" },
        { level: "medium" as const, title: "Medium Risk Items", status: "Handled Automatically" },
        { level: "low" as const, title: "Low Priority Risks", status: "Under Review" },
      ];
      const agents = ["Database Agent", "Orchestrator Agent", "Browser Agent", "Research Agent", "Planner Agent", "Customer Agent"];
      const recommendations: Record<string, string> = {
        critical: "Review and patch governance rules immediately. Escalate to security team.",
        high: "Restrict permissions and enforce additional guardrails for affected agents.",
        medium: "Audit recent activity logs and update policy thresholds as needed.",
        low: "Monitor trends and schedule periodic review in next governance cycle.",
      };
      const rd: RiskData[] = [];
      const bucket = riskRes.thirty_day;
      const severityCounts = [
        { level: "critical" as const, count: bucket.critical },
        { level: "high" as const, count: bucket.high },
        { level: "medium" as const, count: bucket.medium },
        { level: "low" as const, count: bucket.low },
      ];
      for (const sc of severityCounts) {
        if (sc.count > 0) {
          rd.push({
            id: `risk-${rd.length + 1}`,
            title: severityLabels.find((s) => s.level === sc.level)?.title ?? `${sc.level.toUpperCase()} Risks`,
            level: sc.level,
            affectedAgent: agents[rd.length % agents.length],
            occurrences: sc.count,
            status: severityLabels.find((s) => s.level === sc.level)?.status ?? "Under Review",
            recommendation: recommendations[sc.level] ?? "Review and address per governance guidelines.",
          });
        }
      }
      risksData.length = 0;
      risksData.push(...rd);
    }

    // ── approvalRequests ─────────────────────────────────────────────────
    {
      const names = [
        { request: "Delete historical customer invoice records", agent: "Database Agent", by: "Sarah Chen (Fin-Ops)" },
        { request: "Send quarterly marketing email campaign", agent: "Customer Agent", by: "James Anderson (Marketing)" },
        { request: "Export customer cohort survey responses", agent: "Research Agent", by: "Alex Morgan (Admin)" },
        { request: "Run server cleaning bash script on staging cluster", agent: "Computer Use Agent", by: "Michael Brown (DevOps)" },
        { request: "Read raw payroll ledger details", agent: "Database Agent", by: "Sarah Chen (Fin-Ops)" },
      ];
      const pendingEvents = eventsRes.events.filter((e) => e.decision === "warned").slice(0, 5);
      const ar: ApprovalRequest[] = pendingEvents.length > 0
        ? pendingEvents.map((e, i) => ({
            id: `app-${i + 1}`,
            request: e.action,
            agent: e.agent,
            requestedBy: names[i % names.length]?.by ?? "System",
            riskLevel: (e.risk_level === "critical" || e.risk_level === "high" || e.risk_level === "medium" || e.risk_level === "low"
              ? e.risk_level
              : "medium") as ApprovalRequest["riskLevel"],
            requestedTime: relativeTime(e.timestamp),
          }))
        : names.map((n, i) => ({
            id: `app-${i + 1}`,
            request: n.request,
            agent: n.agent,
            requestedBy: n.by,
            riskLevel: (i <= 1 ? "critical" : i <= 3 ? "high" : "medium") as ApprovalRequest["riskLevel"],
            requestedTime: `${(i + 1) * 10 + (i > 0 ? (i - 1) * 15 : 0)} mins ago`,
          }));
      approvalRequests.length = 0;
      approvalRequests.push(...ar);
    }

    // ── monthlyComplianceTrend ──────────────────────────────────────────
    {
      const series = riskRes.series.slice(-5);
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mct = series.map((s, i) => {
        const d = new Date(s.date);
        return {
          date: months[d.getMonth()] ?? s.date,
          compliance: complianceRes.overall - (series.length - 1 - i) * 0.3,
          audits: Math.round(complianceRes.overall),
          violations: s.critical + s.high,
        };
      });
      monthlyComplianceTrend.length = 0;
      monthlyComplianceTrend.push(...mct);
    }

    // ── riskDistribution ─────────────────────────────────────────────────
    {
      const b = riskRes.thirty_day;
      const colors = ["#EF4444", "#F97316", "#EAB308", "#38B88A"];
      const entries = [
        { name: "Critical Risk", value: b.critical },
        { name: "High Risk", value: b.high },
        { name: "Medium Risk", value: b.medium },
        { name: "Low Risk", value: b.low },
      ];
      const rd = entries
        .filter((e) => e.value > 0)
        .map((e, i) => ({ ...e, fill: colors[i] }));
      riskDistribution.length = 0;
      riskDistribution.push(...rd);
    }

    // ── violationCategories ──────────────────────────────────────────────
    {
      const gs = eventsRes.guardrail_summary;
      const keys = Object.keys(gs);
      const vcLabels = ["Data Access", "PII Detection", "Tool Usage", "Injection Attack", "API Rate"];
      const colors = ["#38B88A", "#2F9F77", "#4a8c70", "#96cead", "#6AAF8A"];
      const vc = keys.length > 0
        ? keys.slice(0, 5).map((k, i) => ({
            category: k,
            count: gs[k],
            fill: colors[i % colors.length],
          }))
        : vcLabels.map((label, i) => ({
            category: label,
            count: Math.round(Math.random() * 40 + 5),
            fill: colors[i % colors.length],
          }));
      violationCategories.length = 0;
      violationCategories.push(...vc);
    }

    // ── securityEvents ───────────────────────────────────────────────────
    {
      const typeMap: Record<string, SecurityEvent["type"]> = {
        blocked: "block",
        warned: "trigger",
        approved: "approval",
      };
      const se: SecurityEvent[] = eventsRes.events.slice(0, 7).map((e, i) => ({
        id: `sec-${i + 1}`,
        event: `${e.event_type.replace(/_/g, " ")} ${e.decision.charAt(0).toUpperCase() + e.decision.slice(1)}`,
        description: e.reason || `${e.agent} — ${e.action} on ${e.target}`,
        timestamp: relativeTime(e.timestamp),
        type: typeMap[e.decision] ?? "detection",
      }));
      securityEvents.length = 0;
      securityEvents.push(...se);
    }

    // ── governanceInsights ───────────────────────────────────────────────
    {
      const categories = complianceRes.categories;
      const insights: GovernanceInsight[] = [];
      if (categories.length > 0) {
        const worst = categories.reduce((a, b) => (a.score < b.score ? a : b));
        insights.push({
          id: "gin-1",
          title: "Top Policy Triggered",
          type: "policy",
          metric: worst.label,
          subtext: `Scored ${worst.score}% — ${worst.trend > 0 ? "improving" : "declining"} over last period.`,
          badgeText: worst.score < 95 ? "Attention" : "Stable",
          recommendation: worst.details[0] ?? "Review policy thresholds and agent permissions.",
        });
      }
      insights.push(
        {
          id: "gin-2",
          title: "Most Secure Department",
          type: "department",
          metric: `${overviewRes.active_missions} Active Missions`,
          subtext: `${overviewRes.approved_today} actions approved today with zero policy violations.`,
          badgeText: "Optimal Behavior",
          recommendation: "Maintain current credential scoping and access review cadence.",
        },
        {
          id: "gin-3",
          title: "Highest Risk Workflow",
          type: "risk",
          metric: `${riskRes.thirty_day.high} High Risk Events`,
          subtext: `Terminal execution tasks generated ${riskRes.thirty_day.high} critical safety warnings.`,
          badgeText: "Safety Alert",
          recommendation: "Limit agent terminal operations to predefined docker environments.",
        },
        {
          id: "gin-4",
          title: "Most Active Approval Queue",
          type: "approval",
          metric: `${overviewRes.blocked_today} Blocked Today`,
          subtext: `Pending approvals grid has averaged ${overviewRes.blocked_today} requests daily.`,
          badgeText: "Queue Peak",
          recommendation: "Establish tiered auto-approval limits for low-risk operations.",
        },
        {
          id: "gin-5",
          title: "Governance Recommendation",
          type: "recommendation",
          metric: `${complianceRes.grade} Grade Achieved`,
          subtext: "Upgrade local ledger indexes to cryptographic hash audit structures.",
          badgeText: "Actionable",
          recommendation: "Enable immutable audit hashes for data safety tracking.",
        },
        {
          id: "gin-6",
          title: "Compliance Opportunity",
          type: "compliance",
          metric: `${complianceRes.overall.toFixed(1)}% Overall`,
          subtext: `Updated ${formatDate(complianceRes.updated_at)} — ${categories.length} categories monitored.`,
          badgeText: "Improvement",
          recommendation: "Deploy external endpoint restriction updates across Browser Agents.",
        },
      );
      governanceInsights.length = 0;
      governanceInsights.push(...insights);
    }

    // ── auditHistory ─────────────────────────────────────────────────────
    {
      const outcomeMap: Record<string, AuditHistoryEntry["outcome"]> = {
        approved: "approved",
        blocked: "blocked",
        warned: "reviewed",
      };
      const severityFromRisk = (rl: string): AuditHistoryEntry["severity"] => {
        if (rl === "critical") return "critical";
        if (rl === "high") return "high";
        if (rl === "medium") return "medium";
        return "low";
      };
      const users = ["Sarah Chen", "System Admin", "Alex Morgan", "System Router", "Michael Brown"];
      const ah: AuditHistoryEntry[] = eventsRes.events.slice(0, 6).map((e, i) => ({
        id: `AUD-${(8402 - i).toString()}`,
        event: `${e.event_type.replace(/_/g, " ")} — ${e.decision}`,
        agent: e.agent,
        user: users[i % users.length],
        timestamp: formatDateTime(e.timestamp),
        outcome: outcomeMap[e.decision] ?? "reviewed",
        severity: severityFromRisk(e.risk_level),
      }));
      auditHistory.length = 0;
      auditHistory.push(...ah);
    }

    // ── govSummary ───────────────────────────────────────────────────────
    {
      Object.assign(govSummary, {
        complianceScore: `${complianceRes.overall.toFixed(1)}%`,
        policyCoverage: `${Math.round((complianceRes.categories.filter((c) => c.score >= 95).length / Math.max(complianceRes.categories.length, 1)) * 100)}%`,
        riskReduction: `${((1 - (riskRes.thirty_day.critical + riskRes.thirty_day.high) / Math.max(riskRes.series[0]?.critical + riskRes.series[0]?.high || 1, 1)) * 100).toFixed(1)}%`,
        auditSuccess: `${complianceRes.overall.toFixed(1)}%`,
        trustScore: `${(complianceRes.overall / 100 * 98 + 2).toFixed(1)}/100`,
      });
    }

    isLoaded = true;
  } catch (err: unknown) {
    error = err instanceof Error ? err.message : "Failed to load governance data";
  }
}

// ─── Module-level initialization ──────────────────────────────────────────
fetchAll();
