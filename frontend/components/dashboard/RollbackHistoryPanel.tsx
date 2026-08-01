"use client"

import { AlertTriangle, RotateCcw } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { RollbackAttempt } from "@/services/dashboard/rollbacks"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

function shortSha(sha: string | null): string {
    return sha ? sha.slice(0, 7) : ""
}

export function RollbackHistoryPanel({
    recent = [],
    isLoading,
}: {
    recent?: RollbackAttempt[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && recent.length === 0
    const showEmpty = !isLoading && recent.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Automated Rollbacks" action="View All" />
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
                        <RotateCcw className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No rollbacks triggered yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Watching for regressed deploys to roll back</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {recent.map((r) => (
                            <div key={r.history_id} className="flex items-center gap-3">
                                <div
                                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                    style={r.triggered ? { backgroundColor: "#DCFCE7", color: "#15803D" } : { backgroundColor: "#FEE2E2", color: "#B91C1C" }}
                                >
                                    {r.triggered ? <RotateCcw className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[0.81rem] text-[#374151] truncate">{r.service}</span>
                                        <span className="shrink-0 text-[0.72rem] text-[#9CA3AF]">{r.environment}</span>
                                        {r.triggered && r.target_sha && (
                                            <span className="shrink-0 font-mono text-[0.72rem] text-[#15803D]">→ {shortSha(r.target_sha)}</span>
                                        )}
                                        {r.ticket_key && (
                                            <span className="shrink-0 text-[0.72rem] font-semibold text-[#B45309]">{r.ticket_key}</span>
                                        )}
                                    </div>
                                    <p className="truncate text-[0.73rem] text-[#6B7280]">
                                        {r.triggered ? (r.reasons[0] ?? "Regression detected") : r.error ?? "Rollback not triggered"}
                                    </p>
                                </div>
                                <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{timeAgo(r.triggered_at)}</span>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </Card>
    )
}
