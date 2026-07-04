import { type SpacePermission, type UserPermission, type ConfluencePage, type ConfluenceSpace, type ConfluenceAttachment, type ConfluenceTemplate, PermissionLevel } from "./types"

export const ConfluencePermissionManager = {
  async evaluateSpacePermissions(
    permissions: SpacePermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: PermissionLevel }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: PermissionLevel.NONE }
    return { granted: perm.granted && perm.level !== PermissionLevel.NONE, effectiveLevel: perm.level }
  },

  async evaluatePagePermissions(
    userPermissions: UserPermission[],
    page: ConfluencePage,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.spaceId === page.spaceId)
    if (!perm) return { allowed: false, reason: "no page permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient page access" }
    if (action === "delete" && perm.level !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete page" }
    if (action === "edit" && perm.level === PermissionLevel.VIEW) return { allowed: false, reason: "view-only access cannot edit" }
    if (page.status === "archived" && action !== "restore") return { allowed: false, reason: "page is archived" }
    return { allowed: true, reason: "page permission granted" }
  },

  async evaluateAttachmentPermissions(
    userPermissions: UserPermission[],
    attachment: ConfluenceAttachment,
  ): Promise<{ allowed: boolean; reason: string }> {
    const spaceId = attachment.pageId
    const perm = userPermissions.find((p) => p.spaceId === spaceId)
    if (!perm) return { allowed: false, reason: "no attachment permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient attachment access" }
    if (attachment.archived) return { allowed: false, reason: "attachment is archived" }
    return { allowed: true, reason: "attachment permission granted" }
  },

  async evaluateTemplatePermissions(
    userPermissions: UserPermission[],
    template: ConfluenceTemplate,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.spaceId === template.spaceId)
    if (!perm) return { allowed: false, reason: "no template permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient template access" }
    if (perm.level === PermissionLevel.VIEW) return { allowed: false, reason: "view-only access cannot manage templates" }
    return { allowed: true, reason: "template permission granted" }
  },

  async evaluateSearchPermissions(
    userPermissions: UserPermission[],
    spaceId: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = userPermissions.find((p) => p.spaceId === spaceId)
    if (!perm) return { allowed: false, reason: "no search permission defined" }
    if (!perm.granted || perm.level === PermissionLevel.NONE) return { allowed: false, reason: "insufficient search access" }
    return { allowed: true, reason: "search permission granted" }
  },
}