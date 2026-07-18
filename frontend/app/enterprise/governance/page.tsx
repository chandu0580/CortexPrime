"use client"

import { motion } from "framer-motion"
import { useGovernanceHealth, usePolicies, useApprovals, useViolations, useAuditLog } from "@/hooks/queries/useGovernance"
import { ShieldCheck, FileText, CheckCircle, AlertTriangle, History } from "lucide-react"
import { Badge } from "@/components/enterprise/ui"

export default function GovernanceCenter() {
  const { data: health } = useGovernanceHealth()
  const { data: policies } = usePolicies()
  const { data: approvals } = useApprovals()
  const { data: violations } = useViolations()
  const { data: audit } = useAuditLog()

  const sections = [
    { icon: FileText, label: "Policies", count: policies?.total ?? 0, color: "var(--accent)" },
    { icon: CheckCircle, label: "Approvals", count: approvals?.total ?? 0, color: "var(--success)" },
    { icon: AlertTriangle, label: "Violations", count: violations?.total ?? 0, color: "var(--danger)" },
    { icon: History, label: "Audit Entries", count: audit?.total ?? 0, color: "var(--info)" },
  ]

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="type-heading-xl text-[var(--text-primary)]">Governance Center</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">
          Policy management, approvals, and compliance monitoring
        </p>
      </div>

      {health && (
        <div className="surface-panel-accent p-4 flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-[var(--accent)]" />
          <span className="type-body-sm text-[var(--text-primary)]">
            Governance Runtime: <span className="text-[var(--success)] font-semibold">{health.status}</span>
          </span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {sections.map((s) => (
          <motion.div key={s.label} whileHover={{ y: -2 }} className="surface-panel p-5">
            <div className="flex items-center gap-3 mb-3">
              <s.icon className="w-5 h-5" style={{ color: s.color }} />
              <span className="type-body-sm text-[var(--text-primary)]">{s.label}</span>
            </div>
            <p className="type-metric" style={{ color: s.color }}>{s.count}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="surface-panel p-5">
          <h2 className="type-heading-sm text-[var(--text-primary)] mb-4">Recent Approvals</h2>
          {approvals?.approvals?.length ? (
            <div className="space-y-2">
              {(approvals.approvals as Record<string, unknown>[]).slice(0, 5).map((a, i) => (
                <div key={i} className="flex items-center justify-between p-2.5 rounded-xl bg-[var(--surface-raised)]">
                  <span className="type-body-sm text-[var(--text-secondary)]">{String(a.request_id || a.id || "")}</span>
                  <Badge variant={a.denied ? "danger" : "success"}>
                    {a.denied ? "DENIED" : "APPROVED"}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <p className="type-body-sm text-[var(--text-muted)] text-center py-6">No pending approvals</p>
          )}
        </div>

        <div className="surface-panel p-5">
          <h2 className="type-heading-sm text-[var(--text-primary)] mb-4">Violations</h2>
          {violations?.violations?.length ? (
            <div className="space-y-2">
              {(violations.violations as Record<string, unknown>[]).slice(0, 5).map((v, i) => (
                <div key={i} className="p-2.5 rounded-xl bg-[var(--danger-muted)]">
                  <p className="type-body-sm text-[var(--danger)]">{String(v.message || v.description || "")}</p>
                  <p className="type-caption text-[var(--text-muted)]">{String(v.resource || v.policy || "")}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="type-body-sm text-[var(--text-muted)] text-center py-6">No violations</p>
          )}
        </div>
      </div>
    </div>
  )
}
