import { SlackPermission, SlackWorkspace, SlackChannel, SlackWorkflow, SlackNotification } from "./types"

export const SlackPermissionManager = {
  async evaluateWorkspacePermissions(
    permissions: SlackPermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: string }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: "none" }
    return { granted: perm.granted && perm.access !== "none", effectiveLevel: perm.access }
  },

  async evaluateChannelPermissions(
    permissions: SlackPermission[],
    channel: SlackChannel,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `channel:${channel.workspaceId}`)
    if (!perm) return { allowed: false, reason: "no channel permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient channel access" }
    if (action === "archive" && perm.access !== "admin") return { allowed: false, reason: "admin required to archive channel" }
    if (channel.archived && action !== "unarchive") return { allowed: false, reason: "channel is archived" }
    return { allowed: true, reason: "channel permission granted" }
  },

  async evaluateMessagingPermissions(
    permissions: SlackPermission[],
    workspaceId: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `messaging:${workspaceId}`)
    if (!perm) return { allowed: false, reason: "no messaging permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient messaging access" }
    if (perm.access === "read") return { allowed: false, reason: "read-only access cannot send messages" }
    return { allowed: true, reason: "messaging permission granted" }
  },

  async evaluateWorkflowPermissions(
    permissions: SlackPermission[],
    workflow: SlackWorkflow,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `workflow:${workflow.workspaceId}`)
    if (!perm) return { allowed: false, reason: "no workflow permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient workflow access" }
    if (workflow.status === "completed") return { allowed: false, reason: "workflow is already completed" }
    if (workflow.status === "failed") return { allowed: false, reason: "workflow has failed" }
    return { allowed: true, reason: "workflow permission granted" }
  },

  async evaluateNotificationPermissions(
    permissions: SlackPermission[],
    notification: SlackNotification,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `notification:${notification.workspaceId}`)
    if (!perm) return { allowed: false, reason: "no notification permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient notification access" }
    if (notification.priority === "urgent" && perm.access !== "admin") return { allowed: false, reason: "admin required to send urgent notifications" }
    return { allowed: true, reason: "notification permission granted" }
  },
}