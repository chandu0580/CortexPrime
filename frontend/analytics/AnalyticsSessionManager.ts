import type { AnalyticsSession, AnalyticsCheckpoint, AnalyticsState } from "./types"
import { generateId } from "./shared"

const sessions = new Map<string, AnalyticsSession>()

export const AnalyticsSessionManager = {
  async createSession(name: string, metricIds: string[] = [], metadata: Record<string, unknown> = {}): Promise<AnalyticsSession> {
    const id = generateId("an-sess")
    const session: AnalyticsSession = {
      id,
      name,
      state: "active",
      metricIds,
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      metadata,
    }
    sessions.set(id, session)
    return session
  },

  async pauseSession(sessionId: string): Promise<AnalyticsSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Analytics session not found: ${sessionId}`)
    const updated: AnalyticsSession = { ...session, state: "paused", updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async resumeSession(sessionId: string): Promise<AnalyticsSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Analytics session not found: ${sessionId}`)
    const updated: AnalyticsSession = { ...session, state: "active", updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async closeSession(sessionId: string): Promise<AnalyticsSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Analytics session not found: ${sessionId}`)
    const updated: AnalyticsSession = {
      ...session,
      state: "completed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async failSession(sessionId: string, reason: string): Promise<AnalyticsSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Analytics session not found: ${sessionId}`)
    const updated: AnalyticsSession = {
      ...session,
      state: "failed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      metadata: { ...session.metadata, failureReason: reason },
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async addCheckpoint(sessionId: string, stage: string, status: "pending" | "passed" | "failed" | "skipped", details: string = ""): Promise<AnalyticsCheckpoint> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Analytics session not found: ${sessionId}`)
    const checkpoint: AnalyticsCheckpoint = {
      id: generateId("an-chk"),
      sessionId,
      stage,
      status,
      checkedAt: new Date().toISOString(),
      details,
    }
    sessions.set(sessionId, { ...session, updatedAt: new Date().toISOString() })
    return checkpoint
  },

  async getSession(sessionId: string): Promise<AnalyticsSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async listSessions(state?: AnalyticsState): Promise<AnalyticsSession[]> {
    let result = Array.from(sessions.values())
    if (state) result = result.filter((s) => s.state === state)
    return result.sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())
  },

  async sessionCount(): Promise<number> {
    return sessions.size
  },
}
