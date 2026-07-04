import { TeamsPermission, TeamsOrganization, Team, TeamChannel, TeamMeeting } from "./types"

export const TeamsPermissionManager = {
  async evaluateOrganizationPermissions(
    permissions: TeamsPermission[],
    resource: string,
  ): Promise<{ granted: boolean; effectiveLevel: string }> {
    const perm = permissions.find((p) => p.resource === resource)
    if (!perm) return { granted: false, effectiveLevel: "none" }
    return { granted: perm.granted && perm.access !== "none", effectiveLevel: perm.access }
  },

  async evaluateTeamPermissions(
    permissions: TeamsPermission[],
    team: Team,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `team:${team.organizationId}`)
    if (!perm) return { allowed: false, reason: "no team permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient team access" }
    if (action === "archive" && perm.access !== "admin") return { allowed: false, reason: "admin required to archive team" }
    if (team.archived && action !== "unarchive") return { allowed: false, reason: "team is archived" }
    return { allowed: true, reason: "team permission granted" }
  },

  async evaluateChannelPermissions(
    permissions: TeamsPermission[],
    channel: TeamChannel,
    action: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `channel:${channel.teamId}`)
    if (!perm) return { allowed: false, reason: "no channel permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient channel access" }
    if (action === "delete" && perm.access !== "admin") return { allowed: false, reason: "admin required to delete channel" }
    if (channel.archived && action !== "unarchive") return { allowed: false, reason: "channel is archived" }
    return { allowed: true, reason: "channel permission granted" }
  },

  async evaluateWorkflowPermissions(
    permissions: TeamsPermission[],
    organizationId: string,
    workflowStatus: string,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `workflow:${organizationId}`)
    if (!perm) return { allowed: false, reason: "no workflow permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient workflow access" }
    if (workflowStatus === "completed") return { allowed: false, reason: "workflow is already completed" }
    if (workflowStatus === "failed") return { allowed: false, reason: "workflow has failed" }
    return { allowed: true, reason: "workflow permission granted" }
  },

  async evaluateMeetingPermissions(
    permissions: TeamsPermission[],
    meeting: TeamMeeting,
  ): Promise<{ allowed: boolean; reason: string }> {
    const perm = permissions.find((p) => p.resource === `meeting:${meeting.teamId}`)
    if (!perm) return { allowed: false, reason: "no meeting permission defined" }
    if (!perm.granted || perm.access === "none") return { allowed: false, reason: "insufficient meeting access" }
    if (meeting.status === "ended") return { allowed: false, reason: "meeting has already ended" }
    if (meeting.status === "cancelled") return { allowed: false, reason: "meeting was cancelled" }
    return { allowed: true, reason: "meeting permission granted" }
  },
}