import { Presence, PresenceStatus } from "./types"
import { TeamsClient } from "./TeamsClient"

function mapApiPresence(api: Record<string, unknown>): Presence {
  return {
    id: String(api.id),
    userId: String(api.id),
    status: (api.availability as string ?? "offline").toLowerCase().replace(/ /g, "_") as PresenceStatus,
    activity: String(api.activity ?? ""),
    lastSeenAt: null,
    updatedAt: new Date().toISOString(),
  }
}

export const TeamsPresenceManager = {
  async getPresence(userId: string): Promise<Presence | null> {
    const result = await TeamsClient.get<Record<string, unknown>>(`/users/${userId}/presence`)
    if (result.success && result.data) return mapApiPresence(result.data)
    return null
  },

  async updatePresence(userId: string, status: PresenceStatus): Promise<Presence | null> {
    const sessionBody = { sessionId: "CortexPrime" }
    await TeamsClient.post("/communications/presence/setPresence", { sessionId: "CortexPrime", availability: status.toUpperCase(), activity: status.replace(/_/g, " ") })
    return this.getPresence(userId)
  },

  async listPresence(userIds: string[]): Promise<Presence[]> {
    const result = await TeamsClient.post<Record<string, unknown>>("/communications/presence/getPresencesByUserId", { ids: userIds })
    if (result.success && result.data?.value) {
      return (result.data.value as Record<string, unknown>[]).map(mapApiPresence)
    }
    return []
  },
}