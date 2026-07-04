import type { MissionSession } from "@/cortex-kernel/types"
import type { ExecutionSession, ExecutionTask, ExecutionCheckpoint, ExecutionState } from "./types"
import { generateId } from "./shared"

const sessions = new Map<string, ExecutionSession>()

export const ExecutionSessionManager = {
  async createSession(kernelSession: MissionSession): Promise<ExecutionSession> {
    const id = generateId("exec-session")
    const session: ExecutionSession = {
      id,
      kernelSessionId: kernelSession.id,
      kernelSession,
      state: "CREATED",
      workerId: null,
      worker: null,
      tasks: [],
      checkpoints: [],
      assignment: null,
      heartbeats: [],
      retryPolicies: [],
      failures: [],
      events: [],
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
    }
    sessions.set(id, session)
    return session
  },

  async getSession(sessionId: string): Promise<ExecutionSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<ExecutionSession>): Promise<ExecutionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)
    const updated: ExecutionSession = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async addTask(sessionId: string, task: ExecutionTask): Promise<ExecutionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)
    const updated: ExecutionSession = {
      ...session,
      tasks: [...session.tasks, task],
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async addCheckpoint(sessionId: string, checkpoint: ExecutionCheckpoint): Promise<ExecutionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)
    const updated: ExecutionSession = {
      ...session,
      checkpoints: [...session.checkpoints, checkpoint],
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async closeSession(sessionId: string, finalState: "COMPLETED" | "FAILED" | "CANCELLED"): Promise<ExecutionSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`Execution session not found: ${sessionId}`)
    const updated: ExecutionSession = {
      ...session,
      state: finalState,
      completedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    sessions.set(sessionId, updated)
    return updated
  },

  async getActiveSessions(): Promise<ExecutionSession[]> {
    return Array.from(sessions.values()).filter(
      (s) => s.state !== "COMPLETED" && s.state !== "FAILED" && s.state !== "CANCELLED",
    )
  },

  async sessionCount(): Promise<{ active: number; total: number }> {
    const all = Array.from(sessions.values())
    const active = all.filter(
      (s) => s.state !== "COMPLETED" && s.state !== "FAILED" && s.state !== "CANCELLED",
    )
    return { active: active.length, total: all.length }
  },
}
