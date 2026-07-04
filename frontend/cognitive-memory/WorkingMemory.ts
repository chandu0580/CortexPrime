import type { WorkingMemoryEntry, MemoryPriority, MemoryScope } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const ENTRY_KEY = "working:entry"
const SESSION_INDEX_KEY = "working:session"

function serializeEntry(entry: WorkingMemoryEntry): Record<string, string> {
  return {
    id: entry.id,
    sessionId: entry.sessionId,
    type: entry.type,
    state: entry.state,
    priority: entry.priority,
    scope: entry.scope,
    tags: JSON.stringify(entry.tags),
    metadata: JSON.stringify(entry.metadata),
    createdAt: entry.createdAt,
    updatedAt: entry.updatedAt,
    expiresAt: entry.expiresAt ?? "",
    key: entry.key,
    value: JSON.stringify(entry.value),
    ttl: String(entry.ttl),
  }
}

function deserializeEntry(data: Record<string, string>): WorkingMemoryEntry {
  return {
    id: data.id,
    sessionId: data.sessionId,
    type: "working",
    state: data.state as WorkingMemoryEntry["state"],
    priority: data.priority as MemoryPriority,
    scope: data.scope as MemoryScope,
    tags: JSON.parse(data.tags || "[]"),
    metadata: JSON.parse(data.metadata || "{}"),
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
    expiresAt: data.expiresAt || null,
    key: data.key,
    value: JSON.parse(data.value || "null"),
    ttl: parseInt(data.ttl, 10) || 300_000,
  }
}

export const WorkingMemory = {
  async createEntry(
    sessionId: string,
    key: string,
    value: unknown,
    ttl: number = 300_000,
    priority: MemoryPriority = "medium",
    scope: MemoryScope = "session",
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<WorkingMemoryEntry> {
    const now = new Date().toISOString()
    const entry: WorkingMemoryEntry = {
      id: generateId("mem-working"),
      sessionId,
      type: "working",
      state: "active",
      priority,
      scope,
      tags: tags ?? [],
      metadata: metadata ?? {},
      createdAt: now,
      updatedAt: now,
      expiresAt: new Date(Date.now() + ttl).toISOString(),
      key,
      value,
      ttl,
    }
    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      await client.zadd(`${SESSION_INDEX_KEY}:${sessionId}`, Date.now(), entry.id)
      const ttlSeconds = Math.ceil(ttl / 1000)
      await client.expire(`${ENTRY_KEY}:${entry.id}`, ttlSeconds)
    }
    return entry
  },

  async updateEntry(entryId: string, value: unknown): Promise<WorkingMemoryEntry> {
    const entry = await this.retrieveById(entryId)
    if (!entry) throw new Error(`Working memory entry ${entryId} not found`)
    const client = RedisClient.getClient()
    if (client) {
      entry.value = value
      entry.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
    }
    return entry
  },

  async retrieve(sessionId: string, key: string): Promise<WorkingMemoryEntry | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    for (const id of ids) {
      const data = await client.hgetall(`${ENTRY_KEY}:${id}`)
      if (!data || Object.keys(data).length === 0) continue
      const entry = deserializeEntry(data)
      if (entry.key === key && entry.state === "active") {
        if (entry.expiresAt && new Date(entry.expiresAt).getTime() <= Date.now()) {
          entry.state = "expired"
          await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
          return null
        }
        return entry
      }
    }
    return null
  },

  async retrieveById(entryId: string): Promise<WorkingMemoryEntry | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${ENTRY_KEY}:${entryId}`)
    if (!data || Object.keys(data).length === 0) return null
    const entry = deserializeEntry(data)
    if (entry.state !== "active") return null
    if (entry.expiresAt && new Date(entry.expiresAt).getTime() <= Date.now()) {
      entry.state = "expired"
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      return null
    }
    return entry
  },

  async getSessionEntries(sessionId: string): Promise<WorkingMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const now = Date.now()
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: WorkingMemoryEntry[] = []
    for (const id of ids) {
      const data = await client.hgetall(`${ENTRY_KEY}:${id}`)
      if (!data || Object.keys(data).length === 0) continue
      const entry = deserializeEntry(data)
      if (entry.expiresAt && new Date(entry.expiresAt).getTime() <= now) {
        entry.state = "expired"
        await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
        continue
      }
      if (entry.state === "active") {
        entries.push(entry)
      }
    }
    return entries
  },

  async expire(sessionId: string): Promise<string[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const now = Date.now()
    const expired: string[] = []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    for (const id of ids) {
      const data = await client.hgetall(`${ENTRY_KEY}:${id}`)
      if (!data || Object.keys(data).length === 0) continue
      const entry = deserializeEntry(data)
      if (entry.expiresAt && new Date(entry.expiresAt).getTime() <= now) {
        entry.state = "expired"
        await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
        expired.push(id)
      }
    }
    return expired
  },

  async clearSession(sessionId: string): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    for (const id of ids) {
      await client.del(`${ENTRY_KEY}:${id}`)
    }
    await client.del(`${SESSION_INDEX_KEY}:${sessionId}`)
  },

  async archiveEntry(entryId: string): Promise<void> {
    const entry = await this.retrieveById(entryId)
    if (!entry) throw new Error(`Working memory entry ${entryId} not found`)
    const client = RedisClient.getClient()
    if (client) {
      entry.state = "archived"
      entry.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
    }
  },

  async countBySession(sessionId: string): Promise<number> {
    const entries = await this.getSessionEntries(sessionId)
    return entries.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("working:")
  },
}
