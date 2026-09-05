import IncidentList from "@/components/investigator/IncidentList"

export const metadata = {
    title: "Incident investigator — CortexPrime",
    description: "Read-only investigation of incidents against governed evidence.",
}

export default function InvestigatorPage() {
    return (
        <div className="space-y-5">
            <header>
                <h1 className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
                    Incident investigator
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                    Investigations for your tenant, read from the governed engine. This
                    workspace is read-only: it cannot execute, approve, change autonomy or
                    contact any provider, and nothing shown here was produced by this page.
                </p>
            </header>
            <IncidentList />
        </div>
    )
}
