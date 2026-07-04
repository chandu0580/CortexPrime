import type { VoiceSession, VoiceSessionStatus, VoiceConfiguration, VoiceState } from "./types"
import { generateId } from "@/worker-framework/shared"
import { LiveKitManager } from "./LiveKitManager"

const sessions = new Map<string, VoiceSession>()

export const VoiceSessionManager = {
  async createSession(config: VoiceConfiguration): Promise<VoiceSession> {
    const session: VoiceSession = {
      id: generateId("voice-session"),
      status: "created",
      state: "idle",
      config: { ...config },
      startedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      completedAt: null,
      turnCount: 0,
      currentTurnId: null,
      error: null,
    }
    sessions.set(session.id, session)
    await this.transitionStatus(session.id, "active")
    return session
  },

  async getSession(sessionId: string): Promise<VoiceSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }

    if (session.livekitRoomName) {
      try {
        await LiveKitManager.leaveRoom(session.livekitRoomName, sessionId)
      } catch {
        // Ignore cleanup errors
      }
    }

    await this.transitionStatus(sessionId, "closed")
    session.completedAt = new Date().toISOString()
    sessions.delete(sessionId)
  },

  async transitionState(sessionId: string, target: VoiceState): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }
    const valid = this.getValidStateTransitions(session.state)
    if (!valid.includes(target)) {
      throw new Error(`Invalid voice state transition: ${session.state} → ${target}`)
    }
    session.state = target
    session.updatedAt = new Date().toISOString()
  },

  async incrementTurnCount(sessionId: string, turnId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }
    session.turnCount++
    session.currentTurnId = turnId
    session.updatedAt = new Date().toISOString()
  },

  async getActiveSessions(): Promise<VoiceSession[]> {
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

  async transitionStatus(sessionId: string, target: VoiceSessionStatus): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }
    const valid = this.getValidStatusTransitions(session.status)
    if (!valid.includes(target)) {
      throw new Error(`Invalid voice session status transition: ${session.status} → ${target}`)
    }
    session.status = target
    session.updatedAt = new Date().toISOString()
  },

  async joinLiveKitRoom(sessionId: string, roomName: string, roomSid: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }
    session.livekitRoomName = roomName
    session.livekitRoomSid = roomSid
    session.updatedAt = new Date().toISOString()
  },

  async setDeepgramSessionId(sessionId: string, deepgramSessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Voice session ${sessionId} not found`)
    }
    session.deepgramSessionId = deepgramSessionId
    session.updatedAt = new Date().toISOString()
  },

  getValidStatusTransitions(current: VoiceSessionStatus): VoiceSessionStatus[] {
    const map: Record<VoiceSessionStatus, VoiceSessionStatus[]> = {
      created: ["active"],
      active: ["paused", "closed", "errored"],
      paused: ["active", "closed", "errored"],
      closed: [],
      errored: ["active", "closed"],
    }
    return map[current]
  },

  getValidStateTransitions(current: VoiceState): VoiceState[] {
    const map: Record<VoiceState, VoiceState[]> = {
      idle: ["listening", "error"],
      listening: ["processing", "idle", "paused", "error"],
      processing: ["speaking", "listening", "idle", "error"],
      speaking: ["listening", "idle", "paused", "error"],
      paused: ["listening", "speaking", "idle", "error"],
      error: ["idle", "paused"],
    }
    return map[current]
  },
}
