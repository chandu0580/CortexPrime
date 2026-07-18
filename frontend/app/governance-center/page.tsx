"use client";

import { useState, useEffect } from "react"
import { motion } from "framer-motion";
import CortexShell from "@/components/layout/CortexShell";
import GovernanceHeader from "@/components/governance-center/GovernanceHeader";
import MetricCard from "@/components/governance-center/MetricCard";
import PolicyTable from "@/components/governance-center/PolicyTable";
import RiskCard from "@/components/governance-center/RiskCard";
import ApprovalTable from "@/components/governance-center/ApprovalTable";
import ComplianceChart from "@/components/governance-center/ComplianceChart";
import SecurityTimeline from "@/components/governance-center/SecurityTimeline";
import AuditTable from "@/components/governance-center/AuditTable";
import InsightCard from "@/components/governance-center/InsightCard";
import ExecutiveSummaryCard from "@/components/governance-center/ExecutiveSummaryCard";
import SectionTitle from "@/components/governance-center/SectionTitle";
import { stagger } from "@/lib/motion-tokens";
import { PageLoading, PageError, PageEmpty } from "@/app/loading-states"

export default function GovernanceCenterPage() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [kpiData, setKpiData] = useState<any[]>([])

  useEffect(() => {
    async function fetchKPIs() {
      try {
        setLoading(true)
        setError(null)
        const res = await fetch("/api/governance/kpis")
        if (!res.ok) throw new Error(`API error: ${res.status}`)
        const data = await res.json()
        setKpiData(data.kpis ?? data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load KPIs")
      } finally {
        setLoading(false)
      }
    }
    fetchKPIs()
  }, [])

  const handleRefresh = () => {
    console.log("Refreshing governance center...");
  };

  const handleCreatePolicy = () => {
    console.log("Opening Create Policy dialog... Draft version 1.0 will be saved.");
  };

  const handleReviewRisks = () => {
    console.log("Navigating to risk detail logs...");
  };

  const handleExportAudit = () => {
    console.log("Exporting secure compliance audit history (CSV/JSON)...");
  };

  return (
    <CortexShell title="Governance Center" subtitle="Monitor, enforce, and manage enterprise AI governance">
      {/* Background radial gradient to align with platform design */}
      <div
        className="fixed inset-0 pointer-events-none z-0"
        style={{
          background:
            "radial-gradient(ellipse at 50% 0%, rgba(56,184,138,0.03) 0%, transparent 60%), radial-gradient(ellipse at 10% 80%, rgba(74,140,112,0.02) 0%, transparent 50%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-7xl space-y-8 pb-12">
        {/* Page Header */}
        <GovernanceHeader
          onCreatePolicy={handleCreatePolicy}
          onReviewRisks={handleReviewRisks}
          onExportAudit={handleExportAudit}
          onRefresh={handleRefresh}
        />

        {/* Section 1: Governance Overview Cards */}
        {loading ? (
          <PageLoading />
        ) : error ? (
          <PageError message={error} />
        ) : kpiData.length === 0 ? (
          <PageEmpty message="No KPI data available" />
        ) : (
        <motion.div
          initial="hidden"
          animate="visible"
          variants={stagger(0.05, 0.05)}
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6"
        >
          {kpiData.map((kpi: any, idx: number) => (
            <MetricCard
              key={kpi.title}
              title={kpi.title}
              value={kpi.value}
              change={kpi.change}
              trend={kpi.trend}
              sparkline={kpi.sparkline}
              status={kpi.status}
              statusText={kpi.statusText}
              delayIndex={idx}
            />
          ))}
        </motion.div>
        )}

        {/* Section 9: Executive Summary */}
        <div className="space-y-3">
          <SectionTitle
            title="Executive Summary & Oversight"
            subtitle="High-level operational stats summarizing checked actions, risk counts, and policy coverage."
          />
          <ExecutiveSummaryCard />
        </div>

        {/* Section 2 & 4: Policy Table + Approval Queue */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Policy Table takes 2 cols on Desktop */}
          <div className="lg:col-span-2 space-y-3">
            <SectionTitle
              title="Operational Policies"
              subtitle="Enforced restrictions, rate limits, and output filters active across platform workflows."
            />
            <PolicyTable />
          </div>

          {/* Approvals Table takes 1 col on Desktop */}
          <div className="space-y-3">
            <SectionTitle
              title="Approvals"
              subtitle="Active manual-override requests pending review."
            />
            <ApprovalTable />
          </div>
        </div>

        {/* Section 3: Risk Dashboard */}
        <div className="space-y-3">
          <SectionTitle
            title="Risk Dashboard"
            subtitle="Flagged events, occurrences by category, and recommended mitigation actions."
          />
          <RiskCard />
        </div>

        {/* Section 5: Compliance Charts */}
        <div className="space-y-3">
          <SectionTitle
            title="Compliance Trends"
            subtitle="Understand historical compliance trends, category divisions, and threat types."
          />
          <ComplianceChart />
        </div>

        {/* Section 6 & 7: Security Timeline + Insights */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Security activity takes 1 col */}
          <div className="space-y-3">
            <SectionTitle
              title="Safety Feed"
              subtitle="Real-time log of security events."
            />
            <SecurityTimeline />
          </div>

          {/* Insights takes 2 cols */}
          <div className="lg:col-span-2 space-y-3">
            <SectionTitle
              title="Intelligence & Opportunities"
              subtitle="Actionable safety recommendations generated by Cortex Intelligence."
            />
            <InsightCard />
          </div>
        </div>

        {/* Section 8: Audit History */}
        <div className="space-y-3">
          <SectionTitle
            title="Audit Trail"
            subtitle="View full durable event logging history matching compliance metrics."
          />
          <AuditTable />
        </div>
      </div>
    </CortexShell>
  );
}
