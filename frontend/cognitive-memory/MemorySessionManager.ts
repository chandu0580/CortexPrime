import type { MemorySession, MemoryScope } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const SESSION_KEY = "session"
const SESSION_SET_KEY = "sessions:all"

function serializeSession(session: MemorySession): Record<string, string> {
  return {
    id: session.id,
    contextId: session.contextId,
    userId: session.userId ?? "",
    organizationId: session.organizationId ?? "",
    status: session.status,
    scope: session.scope,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
    closedAt: session.closedAt ?? "",
    entryCount: String(session.entryCount),
  }
}

function deserializeSession(data: Record<string, string>): MemorySession {
  return {
    id: data.id,
    contextId: data.contextId,
    userId: data.userId || null,
    organizationId: data.organizationId || null,
    status: data.status as MemorySession["status"],
    scope: data.scope as MemoryScope,
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
    closedAt: data.closedAt || null,
    entryCount: parseInt(data.entryCount, 10) || 0,
  }
}

export const MemorySessionManager = {
  async createSession(
    contextId: string,
    scope: MemoryScope = "session",
    userId?: string | null,
    organizationId?: string | null,
  ): Promise<MemorySession> {
    const session: MemorySession = {
      id: generateId("mem-session"),
      contextId,
      userId: userId ?? null,
      organizationId: organizationId ?? null,
      status: "active",
      scope,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      closedAt: null,
      entryCount: 0,
    }
    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${SESSION_KEY}:${session.id}`, serializeSession(session))
      await client.sadd(SESSION_SET_KEY, session.id)
      await client.sadd("sessions:active", session.id)
    }
    return session
  },

  async getSession(sessionId: string): Promise<MemorySession | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${SESSION_KEY}:${sessionId}`)
    if (!data || Object.keys(data).length === 0) return null
    return deserializeSession(data)
  },

  async closeSession(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`Memory session ${sessionId} not found`)
    const client = RedisClient.getClient()
    if (!client) return
    session.status = "closed"
    session.closedAt = new Date().toISOString()
    session.updatedAt = new Date().toISOString()
    await client.hset(`${SESSION_KEY}:${sessionId}`, serializeSession(session))
    await client.srem("sessions:active", sessionId)
  },

  async markExpired(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`Memory session ${sessionId} not found`)
    const client = RedisClient.getClient()
    if (!client) return
    session.status = "expired"
    session.updatedAt = new Date().toISOString()
    await client.hset(`${SESSION_KEY}:${sessionId}`, serializeSession(session))
    await client.srem("sessions:active", sessionId)
  },

  async getActiveSessions(): Promise<MemorySession[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.smembers("sessions:active")
    const sessions: MemorySession[] = []
    for (const id of ids) {
      const session = await this.getSession(id)
      if (session && session.status === "active") {
        sessions.push(session)
      } else {
        await client.srem("sessions:active", id)
      }
    }
    return sessions
  },

  async incrementEntryCount(sessionId: string): Promise<void> {
    const session = await this.getSession(sessionId)
    if (!session) throw new Error(`Memory session ${sessionId} not found`)
    const client = RedisClient.getClient()
    if (!client) return
    session.entryCount++
    session.updatedAt = new Date().toISOString()
    await client.hset(`${SESSION_KEY}:${sessionId}`, serializeSession(session))
  },

  async cleanupExpiredSessions(timeoutMs: number): Promise<string[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const now = Date.now()
    const expired: string[] = []
    const allIds = await client.smembers(SESSION_SET_KEY)
    for (const id of allIds) {
      const session = await this.getSession(id)
      if (!session) {
        await client.srem(SESSION_SET_KEY, id)
        continue
      }
      if (session.status !== "active") {
        expired.push(id)
        await client.srem(SESSION_SET_KEY, id)
        await client.srem("sessions:active", id)
        await client.del(`${SESSION_KEY}:${id}`)
        continue
      }
      const lastActivity = new Date(session.updatedAt).getTime()
      if (now - lastActivity > timeoutMs) {
        await this.markExpired(id)
        expired.push(id)
        await client.srem(SESSION_SET_KEY, id)
        await client.del(`${SESSION_KEY}:${id}`)
      }
    }
    return expired
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("session:")
    await client.del(SESSION_SET_KEY, "sessions:active")
  },
}
