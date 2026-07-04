import type { CoordinationSession, CoordinationStage, CoordinationCheckpoint, CoordinationTransition, CoordinationState, CoordinationStrategy } from "./types"
import { generateId } from "./shared"

const sessions = new Map<string, CoordinationSession>()
const transitions: CoordinationTransition[] = []

export const CoordinationSessionManager = {
  async createSession(missionId: string, name: string, strategy: CoordinationStrategy = "sequential", metadata: Record<string, unknown> = {}): Promise<CoordinationSession> {
    const id = generateId("co-sess")
    const now = new Date().toISOString()
    const session: CoordinationSession = {
      id,
      missionId,
      name,
      state: "active",
      strategy,
      stages: [],
      checkpoints: [],
      createdAt: now,
      updatedAt: now,
      completedAt: null,
      metadata,
    }
    sessions.set(id, session)
    return session
  },

  async pauseSession(sessionId: string): Promise<CoordinationSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const updated: CoordinationSession = { ...session, state: "paused", updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    transitions.push({ id: generateId("tran"), sessionId, fromState: session.state, toState: "paused", timestamp: new Date().toISOString(), reason: "Session paused" })
    return updated
  },

  async resumeSession(sessionId: string): Promise<CoordinationSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const updated: CoordinationSession = { ...session, state: "active", updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    transitions.push({ id: generateId("tran"), sessionId, fromState: session.state, toState: "active", timestamp: new Date().toISOString(), reason: "Session resumed" })
    return updated
  },

  async closeSession(sessionId: string): Promise<CoordinationSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const updated: CoordinationSession = {
      ...session,
      state: "completed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    transitions.push({ id: generateId("tran"), sessionId, fromState: session.state, toState: "completed", timestamp: new Date().toISOString(), reason: "Session closed" })
    return updated
  },

  async failSession(sessionId: string, reason: string): Promise<CoordinationSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const updated: CoordinationSession = {
      ...session,
      state: "failed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      metadata: { ...session.metadata, failureReason: reason },
    }
    sessions.set(sessionId, updated)
    transitions.push({ id: generateId("tran"), sessionId, fromState: session.state, toState: "failed", timestamp: new Date().toISOString(), reason })
    return updated
  },

  async addStage(sessionId: string, name: string, sequence: number): Promise<CoordinationStage> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const stage: CoordinationStage = {
      id: generateId("stage"),
      name,
      sequence,
      tasks: [],
      state: "active",
      startedAt: new Date().toISOString(),
      completedAt: null,
    }
    const updated: CoordinationSession = {
      ...session,
      stages: [...session.stages, stage],
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return stage
  },

  async addCheckpoint(sessionId: string, stage: string, status: "pending" | "passed" | "failed" | "skipped", details: string = ""): Promise<CoordinationCheckpoint> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Coordination session not found: ${sessionId}`)
    const checkpoint: CoordinationCheckpoint = {
      id: generateId("co-chk"),
      sessionId,
      stage,
      status,
      checkedAt: new Date().toISOString(),
      details,
    }
    sessions.set(sessionId, { ...session, updatedAt: new Date().toISOString() })
    return checkpoint
  },

  async getSession(sessionId: string): Promise<CoordinationSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async listSessions(missionId?: string): Promise<CoordinationSession[]> {
    let result = Array.from(sessions.values())
    if (missionId) result = result.filter((s) => s.missionId === missionId)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async getTransitions(sessionId?: string): Promise<CoordinationTransition[]> {
    let result = [...transitions]
    if (sessionId) result = result.filter((t) => t.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
  },

  async sessionCount(): Promise<number> {
    return sessions.size
  },
}
