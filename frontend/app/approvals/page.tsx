import Link from "next/link"

import ApprovalQueue from "@/components/investigator/ApprovalQueue"

export const metadata = {
    title: "Approvals — CortexPrime",
    description: "Remediation requests awaiting a human decision.",
}

export default function ApprovalsPage() {
    return (
        <div className="space-y-5">
            <header>
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                        Approvals
                    </h1>
                    <Link
                        href="/investigator"
                        className="text-xs underline underline-offset-2"
                        style={{ color: "var(--accent-primary)" }}
                    >
                        Investigations →
                    </Link>
                </div>
                <p className="mt-1 max-w-3xl text-sm leading-relaxed"
                   style={{ color: "var(--text-secondary)" }}>
                    Every remediation awaiting a decision in your tenant, from every
                    investigation. You do not need to know which investigation raised a
                    request to find it here. Each approval authorizes exactly one action —
                    there is no bulk approval and no way to run anything from this list.
                </p>
            </header>
            <ApprovalQueue />
        </div>
    )
}
