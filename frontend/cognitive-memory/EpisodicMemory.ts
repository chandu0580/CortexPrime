import type { EpisodicMemoryEntry, MemoryEpisodeEvent, MemoryPriority, MemoryScope } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const ENTRY_KEY = "episodic:entry"
const SESSION_INDEX_KEY = "episodic:session"
const MISSION_INDEX_KEY = "episodic:mission"

function serializeEntry(entry: EpisodicMemoryEntry): Record<string, string> {
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
    missionId: entry.missionId,
    episodeNumber: String(entry.episodeNumber),
    summary: entry.summary,
    events: JSON.stringify(entry.events),
    durationMs: String(entry.durationMs),
    outcome: entry.outcome ?? "",
    linkedEpisodeIds: JSON.stringify(entry.linkedEpisodeIds),
  }
}

function deserializeEntry(data: Record<string, string>): EpisodicMemoryEntry {
  return {
    id: data.id,
    sessionId: data.sessionId,
    type: "episodic",
    state: data.state as EpisodicMemoryEntry["state"],
    priority: data.priority as MemoryPriority,
    scope: data.scope as MemoryScope,
    tags: JSON.parse(data.tags || "[]"),
    metadata: JSON.parse(data.metadata || "{}"),
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
    expiresAt: data.expiresAt || null,
    missionId: data.missionId,
    episodeNumber: parseInt(data.episodeNumber, 10) || 0,
    summary: data.summary,
    events: JSON.parse(data.events || "[]"),
    durationMs: parseInt(data.durationMs, 10) || 0,
    outcome: data.outcome || null,
    linkedEpisodeIds: JSON.parse(data.linkedEpisodeIds || "[]"),
  }
}

export const EpisodicMemory = {
  async storeEpisode(
    sessionId: string,
    missionId: string,
    summary: string,
    events: MemoryEpisodeEvent[],
    durationMs: number,
    priority: MemoryPriority = "medium",
    scope: MemoryScope = "session",
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<EpisodicMemoryEntry> {
    const client = RedisClient.getClient()
    let episodeNumber = 1
    if (client) {
      const existingIds = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
      episodeNumber = existingIds.length + 1
    }

    const now = new Date().toISOString()
    const entry: EpisodicMemoryEntry = {
      id: generateId("mem-episodic"),
      sessionId,
      type: "episodic",
      state: "active",
      priority,
      scope,
      tags: tags ?? [],
      metadata: metadata ?? {},
      createdAt: now,
      updatedAt: now,
      expiresAt: null,
      missionId,
      episodeNumber,
      summary,
      events: events.map((e) => ({ ...e })),
      durationMs,
      outcome: null,
      linkedEpisodeIds: [],
    }

    if (client) {
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      await client.zadd(`${SESSION_INDEX_KEY}:${sessionId}`, Date.now(), entry.id)
      await client.zadd(`${MISSION_INDEX_KEY}:${missionId}`, Date.now(), entry.id)
    }
    return entry
  },

  async retrieveEpisode(episodeId: string): Promise<EpisodicMemoryEntry | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${ENTRY_KEY}:${episodeId}`)
    if (!data || Object.keys(data).length === 0) return null
    return deserializeEntry(data)
  },

  async getEpisodesBySession(sessionId: string): Promise<EpisodicMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: EpisodicMemoryEntry[] = []
    for (const id of ids) {
      const entry = await this.retrieveEpisode(id)
      if (entry && entry.state === "active") {
        entries.push(entry)
      }
    }
    return entries.sort((a, b) => a.episodeNumber - b.episodeNumber)
  },

  async getEpisodesByMission(missionId: string): Promise<EpisodicMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${MISSION_INDEX_KEY}:${missionId}`, 0, -1)
    const entries: EpisodicMemoryEntry[] = []
    for (const id of ids) {
      const entry = await this.retrieveEpisode(id)
      if (entry && entry.state === "active") {
        entries.push(entry)
      }
    }
    return entries.sort((a, b) => a.episodeNumber - b.episodeNumber)
  },

  async linkEpisodes(episodeId1: string, episodeId2: string): Promise<void> {
    const ep1 = await this.retrieveEpisode(episodeId1)
    const ep2 = await this.retrieveEpisode(episodeId2)
    if (!ep1) throw new Error(`Episode ${episodeId1} not found`)
    if (!ep2) throw new Error(`Episode ${episodeId2} not found`)

    const client = RedisClient.getClient()
    if (!client) return

    if (!ep1.linkedEpisodeIds.includes(episodeId2)) {
      ep1.linkedEpisodeIds.push(episodeId2)
      ep1.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${ep1.id}`, serializeEntry(ep1))
    }
    if (!ep2.linkedEpisodeIds.includes(episodeId1)) {
      ep2.linkedEpisodeIds.push(episodeId1)
      ep2.updatedAt = new Date().toISOString()
      await client.hset(`${ENTRY_KEY}:${ep2.id}`, serializeEntry(ep2))
    }
  },

  async setOutcome(episodeId: string, outcome: string): Promise<void> {
    const episode = await this.retrieveEpisode(episodeId)
    if (!episode) throw new Error(`Episode ${episodeId} not found`)
    const client = RedisClient.getClient()
    if (!client) return
    episode.outcome = outcome
    episode.updatedAt = new Date().toISOString()
    await client.hset(`${ENTRY_KEY}:${episode.id}`, serializeEntry(episode))
  },

  async summarizeSession(sessionId: string): Promise<{
    episodeCount: number
    timeRangeMs: number
    keyEvents: MemoryEpisodeEvent[]
    outcomes: string[]
  }> {
    const sessionEpisodes = await this.getEpisodesBySession(sessionId)
    if (sessionEpisodes.length === 0) {
      return { episodeCount: 0, timeRangeMs: 0, keyEvents: [], outcomes: [] }
    }

    const allEvents = sessionEpisodes.flatMap((e) => e.events)
    const firstTime = new Date(sessionEpisodes[0].createdAt).getTime()
    const lastTime = new Date(sessionEpisodes[sessionEpisodes.length - 1].createdAt).getTime()
    const outcomes = sessionEpisodes.filter((e) => e.outcome).map((e) => e.outcome!)

    return {
      episodeCount: sessionEpisodes.length,
      timeRangeMs: lastTime - firstTime,
      keyEvents: allEvents.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()),
      outcomes,
    }
  },

  async archiveEpisode(episodeId: string): Promise<void> {
    const episode = await this.retrieveEpisode(episodeId)
    if (!episode) throw new Error(`Episode ${episodeId} not found`)
    const client = RedisClient.getClient()
    if (!client) return
    episode.state = "archived"
    episode.updatedAt = new Date().toISOString()
    await client.hset(`${ENTRY_KEY}:${episode.id}`, serializeEntry(episode))
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

  async countBySession(sessionId: string): Promise<number> {
    const entries = await this.getEpisodesBySession(sessionId)
    return entries.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("episodic:")
  },
}
