import Workspace from "@/components/investigator/Workspace"

export const metadata = {
    title: "Investigation — CortexPrime",
}

/**
 * Next 16: `params` is a Promise and must be awaited (see
 * node_modules/next/dist/docs/01-app/.../dynamic-routes.md).
 *
 * The reference in the URL names a resource, never a tenant. The server
 * resolves the tenant from the session and refuses a reference belonging to
 * another tenant with a 404, so a URL a user edits by hand grants nothing.
 */
export default async function InvestigationPage({
    params,
}: {
    params: Promise<{ ref: string }>
}) {
    const { ref } = await params
    return <Workspace investigationRef={decodeURIComponent(ref)} />
}
