import type { IntelligenceActivity, IntelligenceActivityType } from "./types"
import { generateId } from "@/worker-framework/shared"

const activities = new Map<string, IntelligenceActivity>()

export const IntelligenceActivityManager = {
  async recordActivity(
    sessionId: string,
    type: IntelligenceActivityType,
    description: string,
    metadata?: Record<string, string>,
  ): Promise<IntelligenceActivity> {
    const activity: IntelligenceActivity = {
      id: generateId("intel-activity"),
      sessionId,
      type,
      description,
      metadata: metadata ?? {},
      timestamp: new Date().toISOString(),
    }
    activities.set(activity.id, activity)
    return activity
  },

  async getActivitiesBySession(sessionId: string): Promise<IntelligenceActivity[]> {
    return Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async getActivitiesByType(sessionId: string, type: IntelligenceActivityType): Promise<IntelligenceActivity[]> {
    return Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId && a.type === type)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async getActivitiesByTimeRange(sessionId: string, startTime: string, endTime: string): Promise<IntelligenceActivity[]> {
    const start = new Date(startTime).getTime()
    const end = new Date(endTime).getTime()
    return Array.from(activities.values())
      .filter((a) => {
        const ts = new Date(a.timestamp).getTime()
        return a.sessionId === sessionId && ts >= start && ts <= end
      })
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
  },

  async getRecentActivities(sessionId: string, limit: number): Promise<IntelligenceActivity[]> {
    const sessionActivities = Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId)
      .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
    return sessionActivities.slice(0, limit)
  },

  async countBySession(sessionId: string): Promise<number> {
    return Array.from(activities.values()).filter((a) => a.sessionId === sessionId).length
  },

  async countByType(sessionId: string, type: IntelligenceActivityType): Promise<number> {
    return Array.from(activities.values()).filter((a) => a.sessionId === sessionId && a.type === type).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, activity] of activities.entries()) {
      if (activity.sessionId === sessionId) {
        activities.delete(id)
      }
    }
  },
}
