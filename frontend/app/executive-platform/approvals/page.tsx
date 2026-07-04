"use client"

import { useEnterpriseData } from "@/services/enterprise/EnterpriseDataProvider"
import { useLiveData, DataWidget } from "@/services/enterprise/liveHooks"
import { LiveDataService } from "@/services/enterprise/platformService"
import { GlassCard, StatusBadge } from "@/components/executive-platform/shared"
import { ShieldCheck, AlertTriangle, CheckCircle2, XCircle, Clock } from "lucide-react"

export default function LiveApprovals() {
  const enterprise = useEnterpriseData()
  const workflows = useLiveData((signal) => LiveDataService.getApprovalWorkflows(undefined, signal), [], 10000)
  const analytics = useLiveData((signal) => LiveDataService.getApprovalAnalytics(signal), [], 30000)

  const summary = enterprise.approvalSummary as Record<string, unknown> | null
  const byStatus = (analytics.data as Record<string, unknown>)?.by_status as Record<string, unknown> || {}
  const pendingCount = (byStatus?.pending as number || 0) + (byStatus?.in_progress as number || 0)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <ShieldCheck className="w-6 h-6 text-emerald-400" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Approvals</h1>
          <p className="text-xs text-white/40 mt-0.5">Live approval workflows from enterprise governance</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <GlassCard>
          <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
            <Clock className="w-3.5 h-3.5 text-amber-400" />Pending
          </div>
          <div className="text-xl font-semibold text-amber-400">{pendingCount}</div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />Approved
          </div>
          <div className="text-xl font-semibold text-emerald-400">{byStatus?.approved as number || 0}</div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
            <XCircle className="w-3.5 h-3.5 text-red-400" />Rejected
          </div>
          <div className="text-xl font-semibold text-red-400">{byStatus?.rejected as number || 0}</div>
        </GlassCard>
        <GlassCard>
          <div className="flex items-center gap-2 text-xs text-white/40 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-violet-400" />Break-Glass
          </div>
          <div className="text-xl font-semibold text-violet-400">{analytics.data ? (analytics.data as Record<string, unknown>).break_glass_count as number || 0 : 0}</div>
        </GlassCard>
      </div>

      <GlassCard>
        <h2 className="text-sm font-medium text-white/60 mb-3">Live Approval Workflows</h2>
        <DataWidget result={workflows} skeletonLines={4} emptyMessage="No approval workflows found">
          {(data) => (
            <div className="space-y-1">
              {((data as Record<string, unknown>).workflows as Record<string, unknown>[] || []).length === 0 ? (
                <div className="text-sm text-white/20 py-6 text-center">No workflows</div>
              ) : (
                ((data as Record<string, unknown>).workflows as Record<string, unknown>[]).slice(0, 10).map((wf: Record<string, unknown>, i: number) => (
                  <div key={i} className="flex items-center gap-3 p-2.5 rounded-lg border border-white/5">
                    <ShieldCheck className="w-4 h-4 text-white/30 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white/70 truncate">{String(wf.objective || wf.mission_id || `Workflow ${wf.workflow_id}`).slice(0, 60)}</div>
                      <div className="text-xs text-white/30 mt-0.5">
                        {String(wf.risk_level || "unknown")} · {String(wf.current_step || 0)}/{String(wf.total_steps ?? "?")} steps
                      </div>
                    </div>
                    <StatusBadge status={String(wf.status || "pending")} />
                    {(wf.break_glass as boolean) && <span className="text-[10px] text-violet-400 font-medium">BREAK-GLASS</span>}
                  </div>
                ))
              )}
            </div>
          )}
        </DataWidget>
      </GlassCard>
    </div>
  )
}