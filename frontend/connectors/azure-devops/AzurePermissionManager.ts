import { type AzurePermission, type AzureOrganization, type AzureProject, type AzureBoard, type AzureRepository, type AzurePipeline, PermissionLevel } from "./types"

export const AzurePermissionManager = {
  async evaluateOrganizationPermissions(
    permissions: AzurePermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: PermissionLevel }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: PermissionLevel.NONE }
    return { granted: perm.granted && perm.access !== PermissionLevel.NONE, effectiveLevel: perm.access }
  },

  async evaluateProjectPermissions(
    permissions: AzurePermission[],
    organizationId: string,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `project:${organizationId}`)
    if (!perm) return { allowed: false, reason: "no project permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient project access" }
    if (action === "delete" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete project" }
    if (action === "create" && perm.access === PermissionLevel.READ) return { allowed: false, reason: "read-only access cannot create projects" }
    return { allowed: true, reason: "project permission granted" }
  },

  async evaluateBoardPermissions(
    permissions: AzurePermission[],
    board: AzureBoard,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `board:${board.projectId}`)
    if (!perm) return { allowed: false, reason: "no board permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient board access" }
    if (action === "delete" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete board" }
    if (action === "create_work_item" && perm.access === PermissionLevel.READ) return { allowed: false, reason: "read-only cannot create work items" }
    return { allowed: true, reason: "board permission granted" }
  },

  async evaluateRepositoryPermissions(
    permissions: AzurePermission[],
    repository: AzureRepository,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `repository:${repository.projectId}`)
    if (!perm) return { allowed: false, reason: "no repository permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient repository access" }
    if (action === "delete" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete repository" }
    if (action === "push" && perm.access === PermissionLevel.READ) return { allowed: false, reason: "read-only cannot push" }
    if (repository.archived) return { allowed: false, reason: "repository is archived" }
    return { allowed: true, reason: "repository permission granted" }
  },

  async evaluatePipelinePermissions(
    permissions: AzurePermission[],
    pipeline: AzurePipeline,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `pipeline:${pipeline.projectId}`)
    if (!perm) return { allowed: false, reason: "no pipeline permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient pipeline access" }
    if (perm.access === PermissionLevel.READ) return { allowed: false, reason: "read-only access cannot manage pipelines" }
    return { allowed: true, reason: "pipeline permission granted" }
  },
}