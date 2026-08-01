"use client"

import { Layers } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { CorrelatedIncident } from "@/services/dashboard/incidents"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

export function IncidentsPanel({
    recent = [],
    isLoading,
}: {
    recent?: CorrelatedIncident[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && recent.length === 0
    const showEmpty = !isLoading && recent.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Correlated Incidents" action="View All" />
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
                        <Layers className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No incidents correlated yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Watching for repeated alerts on the same service</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {recent.map((incident) => (
                            <div key={incident.incident_id} className="flex items-center gap-3">
                                <div
                                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                    style={{ backgroundColor: "#FEF3C7", color: "#B45309" }}
                                >
                                    <Layers className="h-4 w-4" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center gap-1.5">
                                        <span className="text-[0.81rem] text-[#374151] truncate">{incident.service}</span>
                                        {incident.suppressed_count > 0 && (
                                            <span className="shrink-0 text-[0.72rem] text-[#9CA3AF]">
                                                {incident.signals.length} signals, {incident.suppressed_count} suppressed
                                            </span>
                                        )}
                                        {incident.ticket_key && (
                                            <span className="shrink-0 text-[0.72rem] font-semibold text-[#B45309]">{incident.ticket_key}</span>
                                        )}
                                    </div>
                                    <p className="truncate text-[0.73rem] text-[#6B7280]">
                                        {incident.hypothesis ?? incident.signals[incident.signals.length - 1]?.summary ?? "Signal correlated"}
                                    </p>
                                </div>
                                <span className="shrink-0 text-[0.73rem] text-[#9CA3AF]">{timeAgo(incident.last_signal_at)}</span>
                            </div>
                        ))}
                    </>
                )}
            </div>
        </Card>
    )
}
