import { TeamsNotification } from "./types"
import { TeamsClient } from "./TeamsClient"

export const TeamsNotificationManager = {
  async sendImmediateNotification(teamId: string, channelId: string, body: string): Promise<boolean> {
    const result = await TeamsClient.post(`/teams/${teamId}/channels/${channelId}/messages`, { body: { contentType: "html", content: body } })
    return result.success
  },

  async queueNotification(organizationId: string, teamId: string, channelId: string, userId: string, title: string, body: string, priority: "low" | "normal" | "high" | "urgent" = "normal"): Promise<TeamsNotification> {
    const html = priority === "urgent" ? `<h2>🚨 ${title}</h2><p>${body}</p>` : priority === "high" ? `<h2>⚠️ ${title}</h2><p>${body}</p>` : `<h2>${title}</h2><p>${body}</p>`
    const result = await TeamsClient.post(`/teams/${teamId}/channels/${channelId}/messages`, { body: { contentType: "html", content: html } })
    const now = new Date().toISOString()
    return { id: result.success ? String((result.data as Record<string, unknown>)?.id ?? "") : "", organizationId, teamId, channelId, userId, title, body, priority, delivered: result.success, readAt: null, createdAt: now }
  },

  async dispatchNotification(id: string): Promise<TeamsNotification | null> { return null },
  async getNotification(id: string): Promise<TeamsNotification | null> { return null },
  async listNotifications(teamId: string): Promise<TeamsNotification[]> { return [] },
}