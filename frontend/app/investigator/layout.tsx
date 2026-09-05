import AuthGuard from "@/components/auth/AuthGuard"

/**
 * The investigator workspace shell.
 *
 * Reuses the existing AuthGuard rather than adding a second session concept.
 * The guard only decides whether to render; it is not an authorisation check
 * and is not treated as one. Every read is authorised by the backend against
 * the HttpOnly session cookie, so a user who defeated this guard in their own
 * browser would still see nothing but 401s.
 */
export default function InvestigatorLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <AuthGuard>
            <div
                className="min-h-screen px-4 py-6 sm:px-8"
                style={{ background: "var(--background)", color: "var(--text-primary)" }}
            >
                <div className="mx-auto max-w-5xl">{children}</div>
            </div>
        </AuthGuard>
    )
}
