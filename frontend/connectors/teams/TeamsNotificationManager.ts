import { TeamsNotification } from "./types"
import { TeamsClient } from "./TeamsClient"

const notifications: TeamsNotification[] = []

export const TeamsNotificationManager = {
  async sendImmediateNotification(teamId: string, channelId: string, body: string): Promise<boolean> {
    const result = await TeamsClient.post(`/teams/${teamId}/channels/${channelId}/messages`, { body: { contentType: "html", content: body } })
    return result.success
  },

  async queueNotification(organizationId: string, teamId: string, channelId: string, userId: string, title: string, body: string, priority: "low" | "normal" | "high" | "urgent" = "normal"): Promise<TeamsNotification> {
    const html = priority === "urgent" ? `<h2>🚨 ${title}</h2><p>${body}</p>` : priority === "high" ? `<h2>⚠️ ${title}</h2><p>${body}</p>` : `<h2>${title}</h2><p>${body}</p>`
    const result = await TeamsClient.post(`/teams/${teamId}/channels/${channelId}/messages`, { body: { contentType: "html", content: html } })
    const now = new Date().toISOString()
    const id = result.success ? String((result.data as Record<string, unknown>)?.id ?? "") : `${Date.now()}`
    const notif: TeamsNotification = { id, organizationId, teamId, channelId, userId, title, body, priority, delivered: result.success, readAt: null, createdAt: now }
    notifications.push(notif)
    return notif
  },

  async dispatchNotification(id: string): Promise<TeamsNotification | null> {
    const notif = notifications.find((n) => n.id === id)
    if (!notif) return null
    const html = `<h2>${notif.title}</h2><p>${notif.body}</p>`
    const result = await TeamsClient.post(`/teams/${notif.teamId}/channels/${notif.channelId}/messages`, { body: { contentType: "html", content: html } })
    if (result.success) {
      notif.delivered = true
      notif.readAt = new Date().toISOString()
    }
    return { ...notif }
  },

  async getNotification(id: string): Promise<TeamsNotification | null> {
    return notifications.find((n) => n.id === id) ?? null
  },

  async listNotifications(teamId: string): Promise<TeamsNotification[]> {
    return notifications.filter((n) => n.teamId === teamId).map((n) => ({ ...n }))
  },
}