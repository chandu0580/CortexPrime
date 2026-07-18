import { type SlackNotification, NotificationPriority } from "./types"
import { SlackClient } from "./SlackClient"

const notifications: SlackNotification[] = []

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
    const id = result.success ? String((result.data as Record<string, unknown>)?.ts ?? "") : `${Date.now()}`
    const notif: SlackNotification = { id, workspaceId, channelId, userId, title, body, priority, delivered: result.success, readAt: result.success ? now : null, createdAt: now }
    notifications.push(notif)
    return notif
  },

  async dispatchNotification(id: string): Promise<SlackNotification | null> {
    const notif = notifications.find((n) => n.id === id)
    if (!notif) return null
    const result = await SlackClient.post("/chat.postMessage", { channel: notif.channelId, text: `${notif.title}\n${notif.body}` })
    if (result.success) {
      notif.delivered = true
      notif.readAt = new Date().toISOString()
    }
    return { ...notif }
  },

  async getNotification(id: string): Promise<SlackNotification | null> {
    return notifications.find((n) => n.id === id) ?? null
  },

  async listNotifications(workspaceId: string): Promise<SlackNotification[]> {
    return notifications.filter((n) => n.workspaceId === workspaceId).map((n) => ({ ...n }))
  },
}