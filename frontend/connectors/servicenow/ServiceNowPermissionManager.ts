import { type ServiceNowPermission, type Incident, type ChangeRequest, type ConfigurationItem, type KnowledgeArticle, PermissionLevel } from "./types"

export const ServiceNowPermissionManager = {
  async evaluateInstancePermissions(
    permissions: ServiceNowPermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: PermissionLevel }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: PermissionLevel.NONE }
    return { granted: perm.granted && perm.access !== PermissionLevel.NONE, effectiveLevel: perm.access }
  },

  async evaluateIncidentPermissions(
    permissions: ServiceNowPermission[],
    incident: Incident,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `incident:${incident.instanceId}`)
    if (!perm) return { allowed: false, reason: "no incident permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient incident access" }
    if (action === "delete" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete incident" }
    if (action === "resolve" && incident.state === "closed") return { allowed: false, reason: "cannot resolve a closed incident" }
    return { allowed: true, reason: "incident permission granted" }
  },

  async evaluateChangePermissions(
    permissions: ServiceNowPermission[],
    change: ChangeRequest,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `change:${change.instanceId}`)
    if (!perm) return { allowed: false, reason: "no change permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient change access" }
    if (action === "approve" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to approve changes" }
    if (change.state === "closed") return { allowed: false, reason: "change is already closed" }
    return { allowed: true, reason: "change permission granted" }
  },

  async evaluateCMDBPermissions(
    permissions: ServiceNowPermission[],
    ci: ConfigurationItem,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `cmdb:${ci.instanceId}`)
    if (!perm) return { allowed: false, reason: "no cmdb permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient cmdb access" }
    if (action === "delete" && perm.access !== PermissionLevel.ADMIN) return { allowed: false, reason: "admin required to delete configuration items" }
    return { allowed: true, reason: "cmdb permission granted" }
  },

  async evaluateKnowledgePermissions(
    permissions: ServiceNowPermission[],
    article: KnowledgeArticle,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `knowledge:${article.instanceId}`)
    if (!perm) return { allowed: false, reason: "no knowledge permission defined" }
    if (!perm.granted || perm.access === PermissionLevel.NONE) return { allowed: false, reason: "insufficient knowledge access" }
    if (action === "publish" && perm.access === PermissionLevel.READ) return { allowed: false, reason: "read-only cannot publish articles" }
    return { allowed: true, reason: "knowledge permission granted" }
  },
}