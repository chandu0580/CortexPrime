import { type SlackNotification, NotificationPriority } from "./types"
import { SlackClient } from "./SlackClient"

export const SlackNotificationManager = {
  async sendImmediateNotification(channelId: string, text: string): Promise<boolean> {
    const result = await SlackClient.post("/chat.postMessage", { channel: channelId, text })
    return result.success
  },

  async queueNotification(
    workspaceId: string, channelId: string, userId: string,
    title: string, body: string,
    priority: NotificationPriority = NotificationPriority.NORMAL,
  ): Promise<SlackNotification> {
    const text = priority === NotificationPriority.URGENT ? `🚨 *${title}*\n${body}` : priority === NotificationPriority.HIGH ? `⚠️ *${title}*\n${body}` : `*${title}*\n${body}`
    const result = await SlackClient.post("/chat.postMessage", { channel: channelId, text })
    const now = new Date().toISOString()
    return { id: result.success ? String((result.data as Record<string, unknown>)?.ts ?? "") : "", workspaceId, channelId, userId, title, body, priority, delivered: result.success, readAt: result.success ? now : null, createdAt: now }
  },

  async dispatchNotification(id: string): Promise<SlackNotification | null> {
    return null
  },

  async getNotification(id: string): Promise<SlackNotification | null> {
    return null
  },

  async listNotifications(workspaceId: string): Promise<SlackNotification[]> {
    return []
  },
}