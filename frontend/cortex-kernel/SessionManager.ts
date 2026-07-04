import type { MissionSession, KernelContext, PipelineStage } from "./types"
import { generateId } from "./shared"

const sessions = new Map<string, MissionSession>()

export const SessionManager = {
  async createSession(userIntent: string): Promise<MissionSession> {
    const id = generateId("session")
    const correlationId = generateId("corr")

    const context: KernelContext = {
      missionId: id,
      sessionId: id,
      correlationId,
      userIntent,
      data: { originalIntent: userIntent },
      errors: [],
      warnings: [],
      propagatedFrom: null,
      propagatedAt: null,
    }

    const session: MissionSession = {
      id,
      externalId: `mission-${Date.now()}`,
      state: "created",
      pipelineStage: "user_intent",
      context,
      correlationId,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      invocations: [],
      telemetry: [],
    }

    sessions.set(id, session)
    return session
  },

  async getSession(sessionId: string): Promise<MissionSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<MissionSession>): Promise<MissionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)
    const updated = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async closeSession(sessionId: string, state: "completed" | "failed" | "cancelled"): Promise<MissionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Session not found: ${sessionId}`)
    const updated: MissionSession = {
      ...session,
      state,
      pipelineStage: "runtime" as PipelineStage,
      completedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async getActiveSessions(): Promise<MissionSession[]> {
    return Array.from(sessions.values()).filter(
      (s) => s.state !== "completed" && s.state !== "failed" && s.state !== "cancelled",
    )
  },

  async sessionCount(): Promise<number> {
    return sessions.size
  },
}
