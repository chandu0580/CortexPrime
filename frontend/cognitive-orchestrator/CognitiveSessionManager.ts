import type { CognitiveSession, CognitiveStatus, CognitiveStage } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, CognitiveSession>()

export const CognitiveSessionManager = {
  async createSession(requestId: string, pipelineId: string, contextId: string, stages: CognitiveStage[]): Promise<CognitiveSession> {
    const now = new Date().toISOString()
    const session: CognitiveSession = {
      id: generateId("cog-session"),
      requestId,
      status: "pending",
      currentStage: stages[0] ?? "intake",
      pipelineId,
      contextId,
      stages: stages.map((s, i) => ({
        id: generateId("cog-stage"),
        name: s,
        order: i + 1,
        status: "pending" as CognitiveStatus,
        startedAt: null,
        completedAt: null,
        durationMs: null,
        error: null,
        retryCount: 0,
      })),
      startedAt: now,
      updatedAt: now,
      completedAt: null,
      error: null,
    }
    sessions.set(session.id, session)
    return session
  },

  async getSession(sessionId: string): Promise<CognitiveSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<CognitiveSession>): Promise<CognitiveSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    const updated: CognitiveSession = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    await this.updateSession(sessionId, { status: "completed", completedAt: new Date().toISOString() })
  },

  async pauseSession(sessionId: string): Promise<CognitiveSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    if (session.status !== "active") throw new Error(`Cannot pause session in status ${session.status}`)
    return this.updateSession(sessionId, { status: "paused" })
  },

  async resumeSession(sessionId: string): Promise<CognitiveSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    if (session.status !== "paused") throw new Error(`Cannot resume session in status ${session.status}`)
    return this.updateSession(sessionId, { status: "active" })
  },

  async failSession(sessionId: string, error: string): Promise<CognitiveSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    return this.updateSession(sessionId, { status: "failed", error, completedAt: new Date().toISOString() })
  },

  async updateStage(sessionId: string, stageOrder: number, updates: Partial<CognitiveSession["stages"][0]>): Promise<CognitiveSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`CognitiveSession ${sessionId} not found`)
    const stages = session.stages.map((s) => s.order === stageOrder ? { ...s, ...updates } : s)
    return this.updateSession(sessionId, { stages })
  },

  async updateCurrentStage(sessionId: string, stage: CognitiveStage): Promise<CognitiveSession> {
    return this.updateSession(sessionId, { currentStage: stage })
  },

  async getActiveSessions(): Promise<CognitiveSession[]> {
    return Array.from(sessions.values()).filter((s) => s.status === "active" || s.status === "pending")
  },

  async countByStatus(status: CognitiveStatus): Promise<number> {
    return Array.from(sessions.values()).filter((s) => s.status === status).length
  },

  async getAll(): Promise<CognitiveSession[]> {
    return Array.from(sessions.values())
  },
}
