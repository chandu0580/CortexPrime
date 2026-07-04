import { SlackReaction } from "./types"
import { SlackClient } from "./SlackClient"

export const SlackReactionManager = {
  async addReaction(channelId: string, timestamp: string, emoji: string): Promise<boolean> {
    const result = await SlackClient.post("/reactions.add", { channel: channelId, timestamp, name: emoji.replace(/:/g, "") })
    return result.success
  },

  async removeReaction(channelId: string, timestamp: string, emoji: string): Promise<boolean> {
    const result = await SlackClient.post("/reactions.remove", { channel: channelId, timestamp, name: emoji.replace(/:/g, "") })
    return result.success
  },

  async listReactions(channelId: string, timestamp: string): Promise<SlackReaction[]> {
    const result = await SlackClient.post<Record<string, unknown>>("/reactions.get", { channel: channelId, timestamp, full: true })
    if (result.success && result.data?.message) {
      const msg = result.data.message as Record<string, unknown>
      const reactions = msg.reactions as Record<string, unknown>[]
      return (reactions ?? []).map((r) => ({
        id: String(r.name),
        emoji: String(r.name),
        userIds: (r.users as string[]) ?? [],
        count: Number(r.count ?? 0),
      }))
    }
    return []
  },

  async getReaction(id: string): Promise<SlackReaction | null> {
    return null
  },
}