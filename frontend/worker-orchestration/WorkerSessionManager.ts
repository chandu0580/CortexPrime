import type { WorkerSession } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, WorkerSession>()

export const WorkerSessionManager = {
  async createSession(orchestrationId: string, missionId: string): Promise<WorkerSession> {
    const now = new Date().toISOString()
    const session: WorkerSession = {
      id: generateId("wo-session"),
      orchestrationId,
      missionId,
      status: "pending",
      workers: [],
      currentGroupId: null,
      startedAt: now,
      updatedAt: now,
      completedAt: null,
      error: null,
    }
    sessions.set(session.id, session)
    return session
  },

  async getSession(sessionId: string): Promise<WorkerSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async updateSession(sessionId: string, updates: Partial<WorkerSession>): Promise<WorkerSession> {
    const session = sessions.get(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    const updated: WorkerSession = { ...session, ...updates, updatedAt: new Date().toISOString() }
    sessions.set(sessionId, updated)
    return updated
  },

  async pauseSession(sessionId: string): Promise<WorkerSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    if (session.status !== "executing" && session.status !== "ready") {
      throw new Error(`Cannot pause session in status ${session.status}`)
    }
    return this.updateSession(sessionId, { status: "paused" })
  },

  async resumeSession(sessionId: string): Promise<WorkerSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    if (session.status !== "paused") throw new Error(`Cannot resume session in status ${session.status}`)
    return this.updateSession(sessionId, { status: "executing" })
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    await this.updateSession(sessionId, { status: "completed", completedAt: new Date().toISOString() })
  },

  async failSession(sessionId: string, error: string): Promise<WorkerSession> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    return this.updateSession(sessionId, { status: "failed", error, completedAt: new Date().toISOString() })
  },

  async addWorker(sessionId: string, workerId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`WorkerSession ${sessionId} not found`)
    if (!session.workers.includes(workerId)) {
      session.workers.push(workerId)
      await this.updateSession(sessionId, { workers: session.workers })
    }
  },

  async updateGroup(sessionId: string, groupId: string): Promise<void> {
    await this.updateSession(sessionId, { currentGroupId: groupId })
  },

  async getActiveSessions(): Promise<WorkerSession[]> {
    return Array.from(sessions.values()).filter((s) => s.status === "ready" || s.status === "executing")
  },

  async getAll(): Promise<WorkerSession[]> {
    return Array.from(sessions.values())
  },
}
