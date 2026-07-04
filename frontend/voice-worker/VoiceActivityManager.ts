import type { VoiceActivity, VoiceActivityType } from "./types"
import { generateId } from "@/worker-framework/shared"

const activities = new Map<string, VoiceActivity>()

export const VoiceActivityManager = {
  async recordActivity(
    sessionId: string,
    type: VoiceActivityType,
    turnId: string | null,
    metadata?: Record<string, string>,
  ): Promise<VoiceActivity> {
    const activity: VoiceActivity = {
      id: generateId("voice-activity"),
      sessionId,
      turnId,
      type,
      startedAt: new Date().toISOString(),
      completedAt: null,
      durationMs: null,
      metadata: metadata ?? {},
    }
    activities.set(activity.id, activity)
    return activity
  },

  async completeActivity(activityId: string): Promise<VoiceActivity> {
    const activity = activities.get(activityId)
    if (!activity) {
      throw new Error(`Voice activity ${activityId} not found`)
    }
    const now = new Date().toISOString()
    const start = new Date(activity.startedAt).getTime()
    activity.completedAt = now
    activity.durationMs = Date.now() - start
    return activity
  },

  async getActivitiesBySession(sessionId: string): Promise<VoiceActivity[]> {
    return Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId)
      .sort((a, b) => new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime())
  },

  async getActivitiesByTurn(turnId: string): Promise<VoiceActivity[]> {
    return Array.from(activities.values())
      .filter((a) => a.turnId === turnId)
      .sort((a, b) => new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime())
  },

  async getActivitiesByType(sessionId: string, type: VoiceActivityType): Promise<VoiceActivity[]> {
    return Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId && a.type === type)
      .sort((a, b) => new Date(a.startedAt).getTime() - new Date(b.startedAt).getTime())
  },

  async getRecentActivities(sessionId: string, limit: number): Promise<VoiceActivity[]> {
    const sessionActivities = Array.from(activities.values())
      .filter((a) => a.sessionId === sessionId)
      .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())
    return sessionActivities.slice(0, limit)
  },

  async countBySession(sessionId: string): Promise<number> {
    return Array.from(activities.values()).filter((a) => a.sessionId === sessionId).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, activity] of activities.entries()) {
      if (activity.sessionId === sessionId) {
        activities.delete(id)
      }
    }
  },
}
