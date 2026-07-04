import type { PlanningSession, PlanningState, PlanningStrategy, PlanningPolicy } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, PlanningSession>()

export const PlanningSessionManager = {
  async createSession(missionId: string, strategy: PlanningStrategy = "iterative", policy: PlanningPolicy = "balanced"): Promise<PlanningSession> {
    const now = new Date().toISOString()
    const session: PlanningSession = {
      id: generateId("plan-session"),
      missionId,
      status: "draft",
      planId: null,
      strategy,
      policy,
      startedAt: now,
      updatedAt: now,
      completedAt: null,
      error: null,
    }
    sessions.set(session.id, session)
    return session
  },

  async getSession(sessionId: string): Promise<PlanningSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<PlanningSession>): Promise<PlanningSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`PlanningSession ${sessionId} not found`)
    const updated: PlanningSession = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async pauseSession(sessionId: string): Promise<PlanningSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`PlanningSession ${sessionId} not found`)
    if (session.status === "finalized" || session.status === "failed" || session.status === "cancelled") {
      throw new Error(`Cannot pause session in status ${session.status}`)
    }
    return this.updateSession(sessionId, { status: "paused" })
  },

  async resumeSession(sessionId: string): Promise<PlanningSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`PlanningSession ${sessionId} not found`)
    if (session.status !== "paused") throw new Error(`Cannot resume session in status ${session.status}`)
    return this.updateSession(sessionId, { status: "planning" })
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`PlanningSession ${sessionId} not found`)
    await this.updateSession(sessionId, { status: "finalized", completedAt: new Date().toISOString() })
  },

  async failSession(sessionId: string, error: string): Promise<PlanningSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`PlanningSession ${sessionId} not found`)
    return this.updateSession(sessionId, { status: "failed", error, completedAt: new Date().toISOString() })
  },

  async linkPlan(sessionId: string, planId: string): Promise<void> {
    await this.updateSession(sessionId, { planId })
  },

  async getActiveSessions(): Promise<PlanningSession[]> {
    return Array.from(sessions.values()).filter((s) =>
      s.status === "draft" || s.status === "planning" || s.status === "analyzing" || s.status === "optimizing" || s.status === "validating",
    )
  },

  async countByStatus(status: PlanningState): Promise<number> {
    return Array.from(sessions.values()).filter((s) => s.status === status).length
  },

  async getAll(): Promise<PlanningSession[]> {
    return Array.from(sessions.values())
  },
}
