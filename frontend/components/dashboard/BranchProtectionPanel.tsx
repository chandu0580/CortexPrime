"use client"

import { GitBranch, HelpCircle, ShieldAlert, ShieldCheck } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { BranchProtectionCheck } from "@/services/dashboard/branchProtection"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

const SEVERITY_TONE: Record<string, { backgroundColor: string; color: string }> = {
    critical: { backgroundColor: "#FEE2E2", color: "#B91C1C" },
    high: { backgroundColor: "#FEE2E2", color: "#B91C1C" },
    medium: { backgroundColor: "#FEF3C7", color: "#B45309" },
    low: { backgroundColor: "#DCFCE7", color: "#15803D" },
    unknown: { backgroundColor: "#F0F4F8", color: "#6B7280" },
}

export function BranchProtectionPanel({
    recent = [],
    isLoading,
}: {
    recent?: BranchProtectionCheck[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && recent.length === 0
    const showEmpty = !isLoading && recent.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Branch Protection" action="View All" />
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
                        <GitBranch className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No repos checked yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Checked once at startup, and on demand</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {recent.map((c) => {
                            const tone = SEVERITY_TONE[c.severity] ?? SEVERITY_TONE.low
                            const isUnknown = c.severity === "unknown"
                            const isClean = !isUnknown && c.gaps.length === 0
                            const icon = isUnknown ? (
                                <HelpCircle className="h-4 w-4" />
                            ) : isClean ? (
                                <ShieldCheck className="h-4 w-4" />
                            ) : (
                                <ShieldAlert className="h-4 w-4" />
                            )
                            const detail = isUnknown
                                ? (c.error ?? "Unable to check")
                                : isClean
                                    ? "Fully protected"
                                    : c.gaps.map((g) => g.description).join(" ")
                            return (
                                <div key={`${c.repo}#${c.branch}`} className="flex items-center gap-3">
                                    <div
                                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                        style={tone}
                                    >
                                        {icon}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1.5">
                                            <span className="text-[0.81rem] text-[#374151] truncate">
                                                {c.repo}@{c.branch}
                                            </span>
                                            {c.ticket_key && (
                                                <span className="shrink-0 text-[0.72rem] font-semibold text-[#B45309]">{c.ticket_key}</span>
                                            )}
                                            {c.fix_applied && (
                                                <span className="shrink-0 text-[0.72rem] font-semibold text-[#15803D]">fixed</span>
                                            )}
                                        </div>
                                        <p className="truncate text-[0.73rem] text-[#6B7280]">{detail}</p>
                                    </div>
                                    <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{timeAgo(c.checked_at)}</span>
                                </div>
                            )
                        })}
                    </>
                )}
            </div>
        </Card>
    )
}
