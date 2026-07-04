import { type WorkspacePermission, type PagePermission, type DatabasePermission, type UserPermission, type NotionPage, type NotionDatabase, type NotionTemplate, PermissionLevel } from "./types"

export const PermissionManager = {
  async evaluateWorkspacePermissions(
    permissions: WorkspacePermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: PermissionLevel }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: PermissionLevel.NONE }
    return { granted: perm.granted && perm.level !== PermissionLevel.NONE, effectiveLevel: perm.level }
  },

  async evaluateDatabasePermissions(
    userPermissions: UserPermission[],
    database: NotionDatabase,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.workspaceId === database.workspaceId)
    if (!perm) return { allowed: false, reason: "no database permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient database access" }
    if (action === "delete" && perm.level !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete database" }
    if (action === "insert" && perm.level === PermissionLevel.VIEW) return { allowed: false, reason: "view-only cannot insert rows" }
    if (database.archived) return { allowed: false, reason: "database is archived" }
    return { allowed: true, reason: "database permission granted" }
  },

  async evaluatePagePermissions(
    userPermissions: UserPermission[],
    page: NotionPage,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.workspaceId === page.workspaceId)
    if (!perm) return { allowed: false, reason: "no page permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient page access" }
    if (action === "delete" && perm.level !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete page" }
    if (page.status === "archived" && action !== "restore") return { allowed: false, reason: "page is archived" }
    return { allowed: true, reason: "page permission granted" }
  },

  async evaluateTemplatePermissions(
    userPermissions: UserPermission[],
    template: NotionTemplate,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.workspaceId === template.workspaceId)
    if (!perm) return { allowed: false, reason: "no template permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient template access" }
    if (action === "create" && perm.level === PermissionLevel.VIEW) return { allowed: false, reason: "view-only cannot create templates" }
    return { allowed: true, reason: "template permission granted" }
  },

  async evaluateSearchPermissions(
    userPermissions: UserPermission[],
    workspaceId: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.workspaceId === workspaceId)
    if (!perm) return { allowed: false, reason: "no search permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient search access" }
    return { allowed: true, reason: "search permission granted" }
  },
}