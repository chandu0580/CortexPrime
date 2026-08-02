"use client"

import { Lightbulb, Search } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { RootCauseRecentAnalysis } from "@/services/dashboard/rootCause"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

function confidenceTone(confidence: number): { backgroundColor: string; color: string } {
    if (confidence >= 0.7) return { backgroundColor: "#DCFCE7", color: "#15803D" }
    if (confidence >= 0.4) return { backgroundColor: "#FEF3C7", color: "#B45309" }
    return { backgroundColor: "#F0F4F8", color: "#6B7280" }
}

export function RootCauseAnalysisPanel({
    totalAnalyses = 0,
    avgConfidence = 0,
    recentAnalyses = [],
    isLoading,
}: {
    totalAnalyses?: number
    avgConfidence?: number
    recentAnalyses?: RootCauseRecentAnalysis[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && recentAnalyses.length === 0
    const showEmpty = !isLoading && recentAnalyses.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Root Cause Analysis" action="View All" />
            {!showSkeleton && !showEmpty && (
                <p className="-mt-2 mb-3 text-[0.75rem] text-[#9CA3AF]">
                    {totalAnalyses} analysis{totalAnalyses === 1 ? "" : "es"} · avg confidence {Math.round(avgConfidence * 100)}%
                </p>
            )}
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
                        <Search className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No root-cause analyses yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Run one from an incident to see it here</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {recentAnalyses.map((a) => (
                            <div key={a.analysis_id} className="flex items-center gap-3">
                                <div
                                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                    style={confidenceTone(a.confidence)}
                                >
                                    <Lightbulb className="h-4 w-4" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[0.81rem] text-[#374151] truncate">{a.problem}</span>
                                        <span className="shrink-0 text-[0.72rem] text-[#9CA3AF]">{Math.round(a.confidence * 100)}%</span>
                                    </div>
                                    <p className="truncate text-[0.73rem] text-[#6B7280]">{a.root_cause}</p>
                                </div>
                                <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{timeAgo(a.timestamp)}</span>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </Card>
    )
}
