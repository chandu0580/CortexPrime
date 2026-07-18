"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import CortexShell from "@/components/layout/CortexShell"
import { stagger, variants } from "@/lib/motion-tokens"
import {
  useGovernanceDashboard,
  usePolicyList,
  useCreatePolicy,
  useUpdatePolicy,
  useDeletePolicy,
  useComplianceCheck,
  useComplianceHistory,
  useAuditLog,
} from "@/hooks/queries/enterprise/useEnterpriseGovernance"
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  FileText,
  Gavel,
  Plus,
  Shield,
  ShieldAlert,
  Trash2,
} from "lucide-react"

function SeverityBadge({ severity }: { severity: string }) {
  const colors: Record<string, string> = {
    critical: "bg-red-50 text-red-600",
    high: "bg-orange-50 text-orange-600",
    medium: "bg-amber-50 text-amber-600",
    low: "bg-gray-100 text-gray-600",
  }
  return <span className={`rounded-full px-2 py-0.5 text-[0.55rem] font-medium capitalize ${colors[severity] || "bg-gray-100 text-gray-600"}`}>{severity}</span>
}

export default function EnterpriseGovernanceCenter() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [showCreate, setShowCreate] = useState(false)
  const [newPolicyName, setNewPolicyName] = useState("")
  const [newPolicyScope, setNewPolicyScope] = useState("all")
  const [newPolicySeverity, setNewPolicySeverity] = useState("medium")
  const [newPolicyAction, setNewPolicyAction] = useState("warn")
  const [complianceTargetType, setComplianceTargetType] = useState("patch")
  const [complianceTargetId, setComplianceTargetId] = useState("")

  const { data: dashboard } = useGovernanceDashboard()
  const { data: policies } = usePolicyList()
  const { data: complianceHistory } = useComplianceHistory()
  const { data: auditLog } = useAuditLog()
  const createMutation = useCreatePolicy()
  const deleteMutation = useDeletePolicy()
  const complianceMutation = useComplianceCheck()

  const handleCreate = async () => {
    if (!newPolicyName) return
    try {
      await createMutation.mutateAsync({
        name: newPolicyName,
        scope: newPolicyScope,
        severity: newPolicySeverity,
        action: newPolicyAction,
      })
      setNewPolicyName("")
      setShowCreate(false)
    } catch (err) { console.error(err) }
  }

  const handleCompliance = async () => {
    if (!complianceTargetId) return
    try {
      await complianceMutation.mutateAsync({
        target_type: complianceTargetType,
        target_id: complianceTargetId,
      })
    } catch (err) { console.error(err) }
  }

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: Shield },
    { id: "policies", label: "Policies", icon: Gavel },
    { id: "compliance", label: "Compliance", icon: CheckCircle2 },
    { id: "audit", label: "Audit Trail", icon: BookOpen },
  ]

  return (
    <CortexShell title="Governance Center" subtitle="Policy enforcement, compliance monitoring, and audit trail">
      <div className="relative z-10 mx-auto max-w-7xl space-y-6">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && (
          <motion.div initial="hidden" animate="visible" variants={stagger(0.04, 0.01)} className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {[
                { icon: Gavel, label: "Total Policies", value: dashboard?.total_policies ?? "-", color: "bg-blue-500" },
                { icon: Shield, label: "Enabled", value: dashboard?.enabled_policies ?? "-", color: "bg-[#38B88A]" },
                { icon: AlertTriangle, label: "Violations", value: dashboard?.total_violations ?? "-", color: "bg-red-500" },
                { icon: CheckCircle2, label: "Compliance Rate", value: `${dashboard?.compliance_rate ?? 0}%`, color: "bg-purple-500" },
              ].map((stat, i) => {
                const Icon = stat.icon
                return (
                  <motion.div key={i} variants={variants.fadeUp} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg p-2.5 ${stat.color}`}><Icon className="h-4 w-4 text-white" /></div>
                      <div>
                        <p className="text-[0.7rem] font-medium text-[#6B7280]">{stat.label}</p>
                        <p className="text-xl font-bold text-[#111827]">{stat.value}</p>
                      </div>
                    </div>
                  </motion.div>
                )
              })}
            </div>
            {dashboard?.policies_by_severity && (
              <div className="rounded-xl border border-[#E8EDF3] bg-white p-5">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Policies by Severity</h3>
                <div className="grid grid-cols-4 gap-4">
                  {Object.entries(dashboard.policies_by_severity).map(([sev, count]) => (
                    <div key={sev} className="rounded-lg bg-[#FAFBFC] px-3 py-3 text-center">
                      <SeverityBadge severity={sev} />
                      <p className="mt-1 text-lg font-bold text-[#111827]">{count}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

        {/* Policies Tab */}
        {activeTab === "policies" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="flex justify-end">
              <button onClick={() => setShowCreate(!showCreate)}
                className="flex items-center gap-1.5 rounded-lg border border-[#38B88A]/30 px-3 py-1.5 text-[0.65rem] font-medium text-[#38B88A] hover:bg-[#F0FDF4]">
                <Plus className="h-3.5 w-3.5" /> New Policy
              </button>
            </div>
            {showCreate && (
              <div className="rounded-xl border border-[#38B88A]/30 bg-[#F0FDF4] p-4">
                <h3 className="mb-3 text-sm font-bold text-[#111827]">Create Policy</h3>
                <div className="grid gap-3 sm:grid-cols-4">
                  <input value={newPolicyName} onChange={e => setNewPolicyName(e.target.value)} placeholder="Policy name" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                  <select value={newPolicyScope} onChange={e => setNewPolicyScope(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    {["all", "patch", "deployment", "workspace", "build"].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select value={newPolicySeverity} onChange={e => setNewPolicySeverity(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    {["critical", "high", "medium", "low"].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                  <select value={newPolicyAction} onChange={e => setNewPolicyAction(e.target.value)} className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    {["deny", "warn", "notify", "require_approval"].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <button onClick={handleCreate} disabled={!newPolicyName} className="mt-3 rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white">Create Policy</button>
              </div>
            )}
            <div className="space-y-3">
              {policies?.map((policy) => (
                <div key={policy.id} className="flex items-start justify-between rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="min-w-0 flex-1">
                    <div className="mb-1 flex items-center gap-2">
                      <SeverityBadge severity={policy.severity} />
                      <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{policy.scope}</span>
                      <span className="rounded bg-[#F4F7FA] px-1.5 py-0.5 text-[0.5rem] text-[#6B7280]">{policy.action}</span>
                      {policy.enabled ?
                        <span className="text-[0.5rem] text-[#38B88A]">enabled</span> :
                        <span className="text-[0.5rem] text-[#9CA3AF]">disabled</span>
                      }
                    </div>
                    <h3 className="text-[0.82rem] font-bold text-[#111827]">{policy.name}</h3>
                    {policy.description && <p className="text-[0.65rem] text-[#6B7280]">{policy.description}</p>}
                    <div className="mt-1 flex gap-3 text-[0.55rem] text-[#9CA3AF]">
                      <span>Violations: {policy.violation_count}</span>
                      <span>Rule: {policy.rule_type}</span>
                    </div>
                  </div>
                  <button onClick={() => deleteMutation.mutate(policy.id)} className="rounded-lg p-1.5 text-red-400 hover:bg-red-50">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {(!policies || policies.length === 0) && (
                <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                  <Gavel className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">No policies defined.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Compliance Tab */}
        {activeTab === "compliance" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
            <div className="rounded-xl border border-[#E8EDF3] bg-white p-4">
              <h3 className="mb-3 text-sm font-bold text-[#111827]">Run Compliance Check</h3>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <p className="mb-1 text-[0.55rem] font-medium text-[#6B7280]">Target Type</p>
                  <select value={complianceTargetType} onChange={e => setComplianceTargetType(e.target.value)}
                    className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none">
                    {["patch", "deployment", "workspace", "build"].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <p className="mb-1 text-[0.55rem] font-medium text-[#6B7280]">Target ID</p>
                  <input value={complianceTargetId} onChange={e => setComplianceTargetId(e.target.value)}
                    placeholder="ID" className="rounded-lg border border-[#E8EDF3] px-3 py-2 text-[0.78rem] outline-none" />
                </div>
                <button onClick={handleCompliance} disabled={!complianceTargetId || complianceMutation.isPending}
                  className="rounded-lg bg-[#38B88A] px-4 py-2 text-[0.72rem] font-bold text-white">
                  Check Compliance
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {complianceHistory?.map((check) => (
                <div key={check.id} className="rounded-xl border border-[#E8EDF3] bg-white p-4">
                  <div className="flex items-center gap-2 mb-2">
                    {check.status === "compliant" ?
                      <CheckCircle2 className="h-4 w-4 text-[#38B88A]" /> :
                      <AlertTriangle className="h-4 w-4 text-red-500" />
                    }
                    <span className={`text-[0.65rem] font-medium capitalize ${check.status === "compliant" ? "text-[#38B88A]" : "text-red-500"}`}>{check.status}</span>
                    <span className="text-[0.55rem] text-[#9CA3AF]">{check.target_type}:{check.target_id}</span>
                    <span className="text-[0.55rem] text-[#6B7280]">{check.policies_evaluated} policies</span>
                  </div>
                  {check.violations?.map((v, i) => (
                    <div key={i} className="ml-6 flex items-start gap-2 text-[0.6rem] text-amber-600">
                      <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />
                      <span>[{v.severity}] {v.policy_name}: {v.reason}</span>
                    </div>
                  ))}
                </div>
              ))}
              {(!complianceHistory || complianceHistory.length === 0) && (
                <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                  <CheckCircle2 className="mb-3 h-10 w-10 opacity-30" />
                  <p className="text-sm">No compliance checks yet.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* Audit Trail Tab */}
        {activeTab === "audit" && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-3">
            {auditLog?.map((entry) => (
              <div key={entry.id} className="rounded-xl border border-[#E8EDF3] bg-white p-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-[#6B7280]" />
                    <span className="text-[0.65rem] font-medium text-[#111827]">{entry.action}</span>
                    <span className="text-[0.55rem] text-[#6B7280]">by {entry.actor}</span>
                  </div>
                  <span className={`text-[0.5rem] ${entry.result === "success" ? "text-[#38B88A]" : "text-red-500"}`}>{entry.result}</span>
                </div>
                <p className="ml-6 text-[0.55rem] text-[#9CA3AF]">{entry.target_type}:{entry.target_id} &middot; {new Date(entry.timestamp).toLocaleString()}</p>
              </div>
            ))}
            {(!auditLog || auditLog.length === 0) && (
              <div className="flex flex-col items-center rounded-xl border border-[#E8EDF3] bg-white py-16 text-[#9CA3AF]">
                <BookOpen className="mb-3 h-10 w-10 opacity-30" />
                <p className="text-sm">No audit entries yet.</p>
              </div>
            )}
          </motion.div>
        )}
      </div>
    </CortexShell>
  )
}
