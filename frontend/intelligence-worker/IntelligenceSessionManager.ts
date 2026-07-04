import type { PlatformError } from "@/platform/contracts"
import type { IntelligenceSession, IntelligenceSessionStatus, IntelligenceState, IntelligenceRequest } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, IntelligenceSession>()

export const IntelligenceSessionManager = {
  async createSession(request: IntelligenceRequest): Promise<IntelligenceSession> {
    const session: IntelligenceSession = {
      id: generateId("intel-session"),
      status: "created",
      state: "idle",
      request: { ...request },
      planId: null,
      summaryId: null,
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      error: null,
    }
    sessions.set(session.id, session)
    await this.transitionStatus(session.id, "active")
    return session
  },

  async getSession(sessionId: string): Promise<IntelligenceSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async pauseSession(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    await this.transitionStatus(sessionId, "paused")
    await this.transitionState(sessionId, "idle")
  },

  async resumeSession(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    await this.transitionStatus(sessionId, "active")
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    await this.transitionStatus(sessionId, "completed")
    session.completedAt = new Date().toISOString()
    sessions.delete(sessionId)
  },

  async markFailed(sessionId: string, error: PlatformError): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    session.error = error
    await this.transitionStatus(sessionId, "failed")
    session.completedAt = new Date().toISOString()
  },

  async getActiveSessions(): Promise<IntelligenceSession[]> {
    return Array.from(sessions.values()).filter((s) => s.status === "active")
  },

  async sessionCount(): Promise<number> {
    return sessions.size
  },

  async cleanupExpired(timeoutMs: number): Promise<string[]> {
    const now = Date.now()
    const expired: string[] = []
    for (const [id, session] of sessions.entries()) {
      const lastActivity = new Date(session.updatedAt).getTime()
      if (now - lastActivity > timeoutMs) {
        expired.push(id)
        sessions.delete(id)
      }
    }
    return expired
  },

  async setPlan(sessionId: string, planId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    session.planId = planId
    session.updatedAt = new Date().toISOString()
  },

  async setSummary(sessionId: string, summaryId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    session.summaryId = summaryId
    session.updatedAt = new Date().toISOString()
  },

  async transitionState(sessionId: string, target: IntelligenceState): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    const valid = this.getValidStateTransitions(session.state)
    if (!valid.includes(target)) {
      throw new Error(`Invalid intelligence state transition: ${session.state} → ${target}`)
    }
    session.state = target
    session.updatedAt = new Date().toISOString()
  },

  async transitionStatus(sessionId: string, target: IntelligenceSessionStatus): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Intelligence session ${sessionId} not found`)
    const valid = this.getValidStatusTransitions(session.status)
    if (!valid.includes(target)) {
      throw new Error(`Invalid intelligence session status transition: ${session.status} → ${target}`)
    }
    session.status = target
    session.updatedAt = new Date().toISOString()
  },

  getValidStatusTransitions(current: IntelligenceSessionStatus): IntelligenceSessionStatus[] {
    const map: Record<IntelligenceSessionStatus, IntelligenceSessionStatus[]> = {
      created: ["active"],
      active: ["paused", "completed", "failed", "cancelled"],
      paused: ["active", "completed", "failed", "cancelled"],
      completed: [],
      failed: ["active"],
      cancelled: [],
    }
    return map[current]
  },

  getValidStateTransitions(current: IntelligenceState): IntelligenceState[] {
    const map: Record<IntelligenceState, IntelligenceState[]> = {
      idle: ["planning", "error"],
      planning: ["collecting", "idle", "error"],
      collecting: ["analyzing", "idle", "error"],
      analyzing: ["generating", "idle", "error"],
      generating: ["summarizing", "idle", "error"],
      summarizing: ["completed", "error"],
      completed: ["idle"],
      error: ["idle", "planning"],
    }
    return map[current]
  },
}
