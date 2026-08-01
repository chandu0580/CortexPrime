"use client"

import { KeyRound, ShieldAlert, ShieldCheck } from "lucide-react"
import { Card } from "./Card"
import { SectionHead } from "./SectionHeader"
import type { CredentialCheck } from "@/services/dashboard/credentials"

function timeAgo(iso: string): string {
    const diffMs = Date.now() - new Date(iso).getTime()
    const mins = Math.round(diffMs / 60000)
    if (mins < 1) return "just now"
    if (mins < 60) return `${mins}m ago`
    const hours = Math.round(mins / 60)
    if (hours < 24) return `${hours}h ago`
    return `${Math.round(hours / 24)}d ago`
}

const CONNECTOR_LABELS: Record<string, string> = {
    github: "GitHub",
    gitlab_ci: "GitLab CI",
    jira: "Jira",
}

export function CredentialHealthPanel({
    latest = [],
    isLoading,
}: {
    latest?: CredentialCheck[]
    isLoading?: boolean
}) {
    const showSkeleton = isLoading && latest.length === 0
    const showEmpty = !isLoading && latest.length === 0

    return (
        <Card className="p-5">
            <SectionHead title="Credential Health" action="View All" />
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
                        <KeyRound className="h-8 w-8 text-[#D1D5DB]" />
                        <p className="text-[0.86rem] font-medium text-[#9CA3AF]">No credential checks yet</p>
                        <p className="text-[0.75rem] text-[#B0B7C3]">Checked once at startup, and on demand</p>
                    </div>
                )}
                {!showSkeleton && !showEmpty && (
                    <>
                        {latest.map((c) => {
                            const expiringSoon = c.valid && c.days_until_expiry !== null && c.days_until_expiry <= 30
                            const tone = !c.valid
                                ? { backgroundColor: "#FEE2E2", color: "#B91C1C" }
                                : expiringSoon
                                    ? { backgroundColor: "#FEF3C7", color: "#B45309" }
                                    : { backgroundColor: "#DCFCE7", color: "#15803D" }
                            return (
                                <div key={c.connector_type} className="flex items-center gap-3">
                                    <div
                                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                                        style={tone}
                                    >
                                        {c.valid ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-1.5">
                                            <span className="text-[0.81rem] text-[#374151] truncate">
                                                {CONNECTOR_LABELS[c.connector_type] ?? c.connector_type}
                                            </span>
                                            {c.ticket_key && (
                                                <span className="shrink-0 text-[0.72rem] font-semibold text-[#B45309]">{c.ticket_key}</span>
                                            )}
                                        </div>
                                        <p className="truncate text-[0.73rem] text-[#6B7280]">
                                            {!c.valid
                                                ? c.error ?? "Authentication failing"
                                                : c.days_until_expiry !== null
                                                    ? `Expires in ${c.days_until_expiry}d${c.expires_at_source === "advisory_header" ? " (advisory)" : ""}`
                                                    : "Authenticated"}
                                        </p>
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
