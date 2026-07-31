"use client"

import { AlertTriangle, CheckCircle2, Clock, Rocket } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { DeployCheckRecord, PendingDeployCheck } from "@/services/dashboard/deployChecks"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

export function DeployRegressionsPanel({
    pending = [],
    recent = [],
    isLoading,
}: {
    pending?: PendingDeployCheck[]
    recent?: DeployCheckRecord[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && pending.length === 0 && recent.length === 0
    const showEmpty = !isLoading && pending.length === 0 && recent.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Deploy Regressions" action="View All" />
            <div className="space-y-3">
                {showSkeleton && (
                    <>
                        {[1, 2, 3].map((n) => (
                            <div key={n} className="flex animate-pulse items-center gap-3">
                                <div className="h-8 w-8 shrink-0 rounded-[10px] bg-[#F0F4F8]" />
                                <div className="flex-1 space-y-1.5">
                                    <div className="h-3 w-5/6 rounded bg-[#F0F4F8]" />
                                    <div className="h-3 w-1/3 rounded bg-[#F0F4F8]" />
                                </div>
                            </div>
                        ))}
                    </>
                )}
                {showEmpty && (
                    <div className="flex flex-col items-center gap-2 py-6 text-center">
                        <Rocket className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No deploys checked yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Watching for the next successful deployment</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {pending.map((p) => (
                            <div key={p.check_id} className="flex items-center gap-3">
                                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] bg-[#F0F4F8] text-[#9CA3AF]">
                                    <Clock className="h-4 w-4" />
                                </div>
                                <p className="flex-1 text-[0.81rem] leading-[1.4] text-[#374151]">
                                    {p.service} — deployment {p.deployment_id} checking…
                                </p>
                            </div>
                        ))}
                        {recent.map((r) => (
                            <div key={r.history_id} className="flex items-center gap-3">
                                <div
                                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                    style={r.regressed ? { backgroundColor: "#FEE2E2", color: "#B91C1C" } : { backgroundColor: "#DCFCE7", color: "#15803D" }}
                                >
                                    {r.regressed ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[0.81rem] text-[#374151] truncate">{r.service}</span>
                                        {r.ticket_key && (
                                            <span className="shrink-0 text-[0.72rem] font-semibold text-[#B45309]">{r.ticket_key}</span>
                                        )}
                                    </div>
                                    {r.regressed && r.reasons.length > 0 && (
                                        <p className="truncate text-[0.73rem] text-[#B91C1C]">{r.reasons[0]}</p>
                                    )}
                                </div>
                                <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{timeAgo(r.checked_at)}</span>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </Card>
    )
}
