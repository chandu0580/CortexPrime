import AuthGuard from "@/components/auth/AuthGuard"

/**
 * The approval inbox shell.
 *
 * Reuses the existing AuthGuard rather than adding a second session concept.
 * The guard decides only whether to render; every read and every decision is
 * authorised by the backend against the HttpOnly session cookie, so defeating
 * it in a browser reveals nothing but 401s.
 */
export default function ApprovalsLayout({
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
                <div className="mx-auto max-w-6xl">{children}</div>
            </div>
        </AuthGuard>
    )
}
