import { GitHubPermission, GitHubRepository, GitHubBranch, GitHubWorkflow } from "./types"
import { generateId } from "./shared"

export const GitHubSecurityManager = {
  async evaluateRepositoryPermissions(
    permissions: GitHubPermission[],
    resource: string
  ): Promise<{ granted: boolean; effectiveLevel: string }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: "none" }
    return { granted: perm.granted && perm.access !== "none", effectiveLevel: perm.access }
  },

  async evaluateProtectedBranches(
    branches: GitHubBranch[],
    branchName: string
  ): Promise<{ protected: boolean; rules: string[] }> {
    const branch = branches.find((b) => b.name === branchName)
    if (!branch) return { protected: false, rules: [] }
    return { protected: branch.protected, rules: branch.protectionRules }
  },

  async evaluateWorkflowPermissions(
    workflow: GitHubWorkflow,
    requiredPermission: string
  ): Promise<{ allowed: boolean; reason: string }> {
    if (workflow.state === "disabled") {
      return { allowed: false, reason: "workflow is disabled" }
    }
    if (workflow.state === "deleted") {
      return { allowed: false, reason: "workflow has been deleted" }
    }
    return { allowed: true, reason: "workflow is active" }
  },

  async evaluateSecretAvailability(
    secretNames: string[],
    requiredSecrets: string[]
  ): Promise<{ available: boolean; missing: string[] }> {
    const missing = requiredSecrets.filter((s) => !secretNames.includes(s))
    return { available: missing.length === 0, missing }
  },

  async evaluateDeploymentProtection(
    environment: string,
    requiredApprovals: number,
    currentApprovals: number
  ): Promise<{ approved: boolean; remainingApprovals: number }> {
    const remaining = Math.max(0, requiredApprovals - currentApprovals)
    return { approved: remaining === 0, remainingApprovals: remaining }
  },
}
