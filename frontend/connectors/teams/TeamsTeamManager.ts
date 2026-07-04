import { Team, TeamMember, TeamVisibility } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiTeam(api: Record<string, unknown>): Team {
  const displayName = String(api.displayName ?? api.mailNickname ?? "")
  return {
    id: String(api.id),
    organizationId: "",
    displayName,
    description: String(api.description ?? ""),
    visibility: (api.visibility as string ?? "private").toLowerCase() as TeamVisibility,
    members: [], channels: [],
    archived: Boolean(api.isArchived ?? (api.resourceProvisioningOptions as string[])?.includes("Team")),
    createdAt: String(api.createdDateTime ?? api.created_at ?? ""),
    updatedAt: String(api.updatedAt ?? api.updated_at ?? ""),
  }
}

export const TeamsTeamManager = {
  async createTeam(displayName: string, description: string = "", visibility: TeamVisibility = TeamVisibility.PRIVATE): Promise<Team | null> {
    const body: Record<string, unknown> = {
      displayName, description,
      "template@odata.bind": "https://graph.microsoft.com/v1.0/teamsTemplates('standard')",
      visibility: visibility.toUpperCase(),
      members: [],
    }
    const result = await TeamsClient.post<Record<string, unknown>>("/teams", body)
    if (result.success && result.data) return mapApiTeam(result.data)
    return null
  },

  async archiveTeam(teamId: string): Promise<boolean> {
    const result = await TeamsClient.post(`/teams/${teamId}/archive`)
    return result.success
  },

  async addMember(teamId: string, userId: string, role: "owner" | "member" = "member"): Promise<boolean> {
    const result = await TeamsClient.post(`/teams/${teamId}/members`, {
      "@odata.type": "#microsoft.graph.aadUserConversationMember",
      roles: [role],
      "user@odata.bind": `https://graph.microsoft.com/v1.0/users('${userId}')`,
    })
    return result.success
  },

  async listTeams(): Promise<Team[]> {
    const result = await TeamsClient.get<Record<string, unknown>>("/groups?$filter=resourceProvisioningOptions/Any(x:x eq 'Team')&$top=200")
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map(mapApiTeam)
    }
    return []
  },

  async getTeam(teamId: string): Promise<Team | null> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/teams/${teamId}`)
    if (result.success && result.data) return mapApiTeam(result.data)
    return null
  },
}