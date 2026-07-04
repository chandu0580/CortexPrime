import type { MissionExecutionSession, ExecutionState, ExecutionStage } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, MissionExecutionSession>()

export const ExecutionSessionManager = {
  async createSession(missionId: string): Promise<MissionExecutionSession> {
    const now = new Date().toISOString()
    const session: MissionExecutionSession = {
      id: generateId("exec-session"),
      missionId,
      orchestrationSessionId: null,
      status: "pending",
      currentStage: "decomposition",
      planId: null,
      dependencyGraphId: generateId("exec-dep-graph"),
      startedAt: now,
      updatedAt: now,
      completedAt: null,
      error: null,
    }
    sessions.set(session.id, session)
    return session
  },

  async getSession(sessionId: string): Promise<MissionExecutionSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<MissionExecutionSession>): Promise<MissionExecutionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`ExecutionSession ${sessionId} not found`)
    const updated: MissionExecutionSession = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`ExecutionSession ${sessionId} not found`)
    await this.updateSession(sessionId, { status: "completed", completedAt: new Date().toISOString() })
  },

  async pauseSession(sessionId: string): Promise<MissionExecutionSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`ExecutionSession ${sessionId} not found`)
    if (session.status !== "executing" && session.status !== "planning" && session.status !== "distributing") {
      throw new Error(`Cannot pause session in status ${session.status}`)
    }
    return this.updateSession(sessionId, { status: "paused" })
  },

  async resumeSession(sessionId: string): Promise<MissionExecutionSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`ExecutionSession ${sessionId} not found`)
    if (session.status !== "paused") throw new Error(`Cannot resume session in status ${session.status}`)
    return this.updateSession(sessionId, { status: session.currentStage === "decomposition" ? "planning" : "executing" })
  },

  async failSession(sessionId: string, error: string): Promise<MissionExecutionSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`ExecutionSession ${sessionId} not found`)
    return this.updateSession(sessionId, { status: "failed", error, completedAt: new Date().toISOString() })
  },

  async updateStage(sessionId: string, stage: ExecutionStage): Promise<MissionExecutionSession> {
    return this.updateSession(sessionId, { currentStage: stage })
  },

  async updateStatus(sessionId: string, status: ExecutionState): Promise<MissionExecutionSession> {
    return this.updateSession(sessionId, { status })
  },

  async linkOrchestration(sessionId: string, orchestrationSessionId: string): Promise<void> {
    await this.updateSession(sessionId, { orchestrationSessionId })
  },

  async linkPlan(sessionId: string, planId: string): Promise<void> {
    await this.updateSession(sessionId, { planId })
  },

  async getActiveSessions(): Promise<MissionExecutionSession[]> {
    return Array.from(sessions.values()).filter((s) =>
      s.status === "planning" || s.status === "distributing" || s.status === "executing",
    )
  },

  async countByStatus(status: ExecutionState): Promise<number> {
    return Array.from(sessions.values()).filter((s) => s.status === status).length
  },

  async getAll(): Promise<MissionExecutionSession[]> {
    return Array.from(sessions.values())
  },
}
