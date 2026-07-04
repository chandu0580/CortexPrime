import type { DesktopSession, DesktopSessionStatus, DesktopHealthStatusResult } from "./types"
import { generateId } from "@/worker-framework/shared"

const sessions = new Map<string, DesktopSession>()

export const DesktopSessionManager = {
  createSession(metadata: Record<string, string> = {}): DesktopSession {
    const session: DesktopSession = {
      id: generateId("desktop-session"),
      status: "created",
      createdAt: new Date().toISOString(),
      lastActivityAt: new Date().toISOString(),
      actionCount: 0,
      errorCount: 0,
      metadata,
    }
    sessions.set(session.id, session)
    return session
  },

  getSession(sessionId: string): DesktopSession | undefined {
    return sessions.get(sessionId)
  },

  setStatus(sessionId: string, status: DesktopSessionStatus): boolean {
    const session = sessions.get(sessionId)
    if (!session) return false
    session.status = status
    session.lastActivityAt = new Date().toISOString()
    return true
  },

  recordAction(sessionId: string): boolean {
    const session = sessions.get(sessionId)
    if (!session) return false
    session.actionCount++
    session.lastActivityAt = new Date().toISOString()
    return true
  },

  recordError(sessionId: string): boolean {
    const session = sessions.get(sessionId)
    if (!session) return false
    session.errorCount++
    session.lastActivityAt = new Date().toISOString()
    return true
  },

  closeSession(sessionId: string): boolean {
    return DesktopSessionManager.setStatus(sessionId, "closed")
  },

  getActiveSessions(): DesktopSession[] {
    return Array.from(sessions.values()).filter((s) => s.status === "active" || s.status === "created")
  },

  getAllSessions(): DesktopSession[] {
    return Array.from(sessions.values())
  },

  getHealthStatus(): DesktopHealthStatusResult {
    const all = Array.from(sessions.values())
    const active = all.filter((s) => s.status === "active")
    const failed = all.filter((s) => s.status === "failed")
    const lastAction = all.length > 0 ? all[all.length - 1] : null
    return {
      status: active.length > 0 ? "running" : all.length === 0 ? "idle" : "idle",
      sessions: { total: all.length, active: active.length, failed: failed.length },
      lastAction: lastAction ? `session_${lastAction.id.slice(-8)}` : null,
      lastActionAt: lastAction?.lastActivityAt ?? null,
      uptimeMs: 0,
      consecutiveFailures: failed.length,
    }
  },
}