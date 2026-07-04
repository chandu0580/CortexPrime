import { SlackThread, SlackReply } from "./types"
import { SlackClient } from "./SlackClient"

function mapApiReply(api: Record<string, unknown>, threadId: string): SlackReply {
  return {
    id: String(api.ts),
    threadId,
    userId: String(api.user ?? ""),
    text: String(api.text ?? ""),
    mentions: [],
    attachments: [],
    reactions: [],
    createdAt: new Date(Number(api.ts) * 1000).toISOString(),
    updatedAt: new Date(Number(api.ts) * 1000).toISOString(),
  }
}

export const SlackThreadManager = {
  async createThread(channelId: string, text: string): Promise<SlackThread | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/chat.postMessage", { channel: channelId, text })
    if (result.success && result.data?.message) {
      const msg = result.data.message as Record<string, unknown>
      return { id: String(msg.ts), channelId, parentMessageId: String(msg.ts), replies: [], replyCount: 0, closed: false, createdAt: new Date(Number(msg.ts) * 1000).toISOString(), updatedAt: new Date(Number(msg.ts) * 1000).toISOString() }
    }
    return null
  },

  async reply(channelId: string, threadTs: string, text: string): Promise<SlackReply | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/chat.postMessage", { channel: channelId, thread_ts: threadTs, text })
    if (result.success && result.data?.message) return mapApiReply(result.data.message as Record<string, unknown>, threadTs)
    return null
  },

  async closeThread(_threadId: string): Promise<SlackThread | null> {
    return null
  },

  async retrieveThread(channelId: string, threadTs: string): Promise<SlackThread | null> {
    const result = await SlackClient.post<Record<string, unknown>>("/conversations.replies", { channel: channelId, ts: threadTs, limit: 100 })
    if (result.success && result.data?.messages) {
      const msgs = result.data.messages as Record<string, unknown>[]
      if (msgs.length > 0) {
        const parent = msgs[0]
        const replies = msgs.slice(1).map((r) => mapApiReply(r, threadTs))
        return { id: threadTs, channelId, parentMessageId: threadTs, replies, replyCount: replies.length, closed: false, createdAt: new Date(Number(parent.ts) * 1000).toISOString(), updatedAt: new Date(Number(parent.ts) * 1000).toISOString() }
      }
    }
    return null
  },

  async getThread(id: string): Promise<SlackThread | null> {
    return null
  },
}