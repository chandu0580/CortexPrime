import { type SlackUser, UserPresence } from "./types"
import { SlackClient } from "./SlackClient"

function mapApiUser(api: Record<string, unknown>, workspaceId: string): SlackUser {
  return {
    id: String(api.id),
    workspaceId,
    name: String(api.name),
    displayName: String((api.profile as Record<string, unknown>)?.display_name ?? api.real_name ?? api.name ?? ""),
    email: String((api.profile as Record<string, unknown>)?.email ?? ""),
    presence: api.presence === "active" ? UserPresence.ONLINE : api.presence === "away" ? UserPresence.AWAY : UserPresence.OFFLINE,
    isAdmin: Boolean(api.is_admin),
    isBot: Boolean(api.is_bot),
    timezone: String(api.tz ?? "UTC"),
    avatarUrl: String((api.profile as Record<string, unknown>)?.image_192 ?? ""),
    createdAt: "", updatedAt: "",
  }
}

export const SlackUserManager = {
  async listUsers(): Promise<SlackUser[]> {
    const result = await SlackClient.post<Record<string, unknown>>("/users.list", { limit: 200 })
    if (result.success && result.data?.members) {
      return (result.data.members as Record<string, unknown>[]).map((u) => mapApiUser(u, ""))
    }
    return []
  },

  async getUser(userId: string): Promise<SlackUser | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/users.info", { user: userId })
    if (result.success && result.data?.user) return mapApiUser(result.data.user as Record<string, unknown>, "")
    return null
  },

  async updatePresence(userId: string, presence: UserPresence): Promise<SlackUser | null> {
    const presenceStr = presence === UserPresence.ONLINE ? "auto" : "away"
    await SlackClient.post("/users.setPresence", { presence: presenceStr })
    return this.getUser(userId)
  },
}