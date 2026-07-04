import type { GovernanceSession, GovernanceCheckpoint } from "./types"
import { generateId } from "./shared"

const sessions = new Map<string, GovernanceSession>()

export const GovernanceSessionManager = {
  async createSession(missionId: string, policyIds: string[] = [], metadata: Record<string, unknown> = {}): Promise<GovernanceSession> {
    const id = generateId("gov-sess")
    const session: GovernanceSession = {
      id,
      missionId,
      state: "active",
      policyIds,
      checkpoints: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      metadata,
    }
    sessions.set(id, session)
    return session
  },

  async closeSession(sessionId: string): Promise<GovernanceSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)
    const updated: GovernanceSession = {
      ...session,
      state: "completed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async pauseSession(sessionId: string): Promise<GovernanceSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)
    const updated: GovernanceSession = {
      ...session,
      state: "paused",
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async resumeSession(sessionId: string): Promise<GovernanceSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)
    const updated: GovernanceSession = {
      ...session,
      state: "active",
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async failSession(sessionId: string, reason: string): Promise<GovernanceSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)
    const updated: GovernanceSession = {
      ...session,
      state: "failed",
      updatedAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      metadata: { ...session.metadata, failureReason: reason },
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async addCheckpoint(sessionId: string, stage: string, status: "pending" | "passed" | "failed" | "skipped", details: string = ""): Promise<GovernanceCheckpoint> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Governance session not found: ${sessionId}`)
    const checkpoint: GovernanceCheckpoint = {
      id: generateId("gov-chk"),
      sessionId,
      stage,
      status,
      checkedAt: new Date().toISOString(),
      details,
    }
    const updated: GovernanceSession = {
      ...session,
      checkpoints: [...session.checkpoints, checkpoint],
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return checkpoint
  },

  async getSession(sessionId: string): Promise<GovernanceSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async listSessions(missionId?: string): Promise<GovernanceSession[]> {
    let result = Array.from(sessions.values())
    if (missionId) result = result.filter((s) => s.missionId === missionId)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async sessionCount(): Promise<number> {
    return sessions.size
  },
}
