import { JiraPermission, JiraProject, JiraIssue, JiraWorkflow, JiraRelease } from "./types"

export const JiraPermissionManager = {
  async evaluateProjectPermissions(
    permissions: JiraPermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: string }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: "none" }
    return { granted: perm.granted && perm.access !== "none", effectiveLevel: perm.access }
  },

  async evaluateIssuePermissions(
    permissions: JiraPermission[],
    issue: JiraIssue,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `issue:${issue.projectId}`)
    if (!perm) return { allowed: false, reason: "no permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient access" }
    if (action === "delete" && perm.access !== "admin") return { allowed: false, reason: "admin required to delete" }
    return { allowed: true, reason: "permission granted" }
  },

  async evaluateWorkflowPermissions(
    permissions: JiraPermission[],
    workflow: JiraWorkflow,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `workflow:${workflow.projectId}`)
    if (!perm) return { allowed: false, reason: "no workflow permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient workflow access" }
    if (workflow.state === "archived") return { allowed: false, reason: "workflow is archived" }
    return { allowed: true, reason: "workflow permission granted" }
  },

  async evaluateReleasePermissions(
    permissions: JiraPermission[],
    release: JiraRelease,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `release:${release.projectId}`)
    if (!perm) return { allowed: false, reason: "no release permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient release access" }
    if (perm.access !== "admin" && release.released) return { allowed: false, reason: "admin required to modify published release" }
    return { allowed: true, reason: "release permission granted" }
  },

  async evaluateTransitionPermissions(
    permissions: JiraPermission[],
    issue: JiraIssue,
    targetStatus: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `transition:${issue.projectId}`)
    if (!perm) return { allowed: false, reason: "no transition permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient transition access" }
    if (perm.access === "read") return { allowed: false, reason: "read-only access cannot transition issues" }
    return { allowed: true, reason: "transition permission granted" }
  },
}
