import type { ProceduralMemoryEntry, MemoryProcedureStep, MemoryPriority, MemoryScope } from "./types"
import { generateId } from "@/worker-framework/shared"
import { RedisClient } from "./RedisClient"

const ENTRY_KEY = "procedural:entry"
const SESSION_INDEX_KEY = "procedural:session"
const TYPE_INDEX_KEY = "procedural:type"

function serializeEntry(entry: ProceduralMemoryEntry): Record<string, string> {
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
    procedureName: entry.procedureName,
    procedureType: entry.procedureType,
    steps: JSON.stringify(entry.steps),
    inputs: JSON.stringify(entry.inputs),
    outputs: JSON.stringify(entry.outputs),
    conditions: JSON.stringify(entry.conditions),
    version: entry.version,
  }
}

function deserializeEntry(data: Record<string, string>): ProceduralMemoryEntry {
  return {
    id: data.id,
    sessionId: data.sessionId,
    type: "procedural",
    state: data.state as ProceduralMemoryEntry["state"],
    priority: data.priority as MemoryPriority,
    scope: data.scope as MemoryScope,
    tags: JSON.parse(data.tags || "[]"),
    metadata: JSON.parse(data.metadata || "{}"),
    createdAt: data.createdAt,
    updatedAt: data.updatedAt,
    expiresAt: data.expiresAt || null,
    procedureName: data.procedureName,
    procedureType: data.procedureType,
    steps: JSON.parse(data.steps || "[]"),
    inputs: JSON.parse(data.inputs || "[]"),
    outputs: JSON.parse(data.outputs || "[]"),
    conditions: JSON.parse(data.conditions || "[]"),
    version: data.version,
  }
}

export const ProceduralMemory = {
  async storeProcedure(
    sessionId: string,
    procedureName: string,
    procedureType: string,
    steps: Omit<MemoryProcedureStep, "id">[],
    inputs: string[],
    outputs: string[],
    conditions: string[],
    version: string = "1.0.0",
    priority?: MemoryPriority,
    scope?: MemoryScope,
    tags?: string[],
    metadata?: Record<string, string>,
  ): Promise<ProceduralMemoryEntry> {
    const now = new Date().toISOString()
    const procedureSteps: MemoryProcedureStep[] = steps.map((s, i) => ({
      ...s,
      id: generateId("mem-step"),
      order: i + 1,
    }))

    const entry: ProceduralMemoryEntry = {
      id: generateId("mem-procedural"),
      sessionId,
      type: "procedural",
      state: "active",
      priority: priority ?? "medium",
      scope: scope ?? "session",
      tags: tags ?? [],
      metadata: metadata ?? {},
      createdAt: now,
      updatedAt: now,
      expiresAt: null,
      procedureName,
      procedureType,
      steps: procedureSteps,
      inputs: [...inputs],
      outputs: [...outputs],
      conditions: [...conditions],
      version,
    }

    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${entry.id}`, serializeEntry(entry))
      await client.zadd(`${SESSION_INDEX_KEY}:${sessionId}`, Date.now(), entry.id)
      await client.zadd(`${TYPE_INDEX_KEY}:${procedureType}`, Date.now(), entry.id)
    }
    return entry
  },

  async retrieveProcedure(procedureId: string): Promise<ProceduralMemoryEntry | null> {
    const client = RedisClient.getClient()
    if (!client) return null
    const data = await client.hgetall(`${ENTRY_KEY}:${procedureId}`)
    if (!data || Object.keys(data).length === 0) return null
    return deserializeEntry(data)
  },

  async findProceduresByName(sessionId: string, name: string): Promise<ProceduralMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: ProceduralMemoryEntry[] = []
    const q = name.toLowerCase()
    for (const id of ids) {
      const entry = await this.retrieveProcedure(id)
      if (entry && entry.state === "active" && entry.procedureName.toLowerCase().includes(q)) {
        entries.push(entry)
      }
    }
    return entries
  },

  async findProceduresByType(sessionId: string, procedureType: string): Promise<ProceduralMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: ProceduralMemoryEntry[] = []
    for (const id of ids) {
      const entry = await this.retrieveProcedure(id)
      if (entry && entry.state === "active" && entry.procedureType === procedureType) {
        entries.push(entry)
      }
    }
    return entries
  },

  async findProceduresByTag(sessionId: string, tag: string): Promise<ProceduralMemoryEntry[]> {
    const client = RedisClient.getClient()
    if (!client) return []
    const ids = await client.zrange(`${SESSION_INDEX_KEY}:${sessionId}`, 0, -1)
    const entries: ProceduralMemoryEntry[] = []
    for (const id of ids) {
      const entry = await this.retrieveProcedure(id)
      if (entry && entry.state === "active" && entry.tags.includes(tag)) {
        entries.push(entry)
      }
    }
    return entries
  },

  async addStep(procedureId: string, step: Omit<MemoryProcedureStep, "id" | "order">): Promise<MemoryProcedureStep> {
    const procedure = await this.retrieveProcedure(procedureId)
    if (!procedure) throw new Error(`Procedure ${procedureId} not found`)

    const client = RedisClient.getClient()
    const newStep: MemoryProcedureStep = {
      ...step,
      id: generateId("mem-step"),
      order: procedure.steps.length + 1,
    }
    procedure.steps.push(newStep)
    procedure.updatedAt = new Date().toISOString()

    if (client) {
      await client.hset(`${ENTRY_KEY}:${procedure.id}`, serializeEntry(procedure))
    }
    return newStep
  },

  async reorderSteps(procedureId: string, stepIds: string[]): Promise<void> {
    const procedure = await this.retrieveProcedure(procedureId)
    if (!procedure) throw new Error(`Procedure ${procedureId} not found`)

    const stepMap = new Map(procedure.steps.map((s) => [s.id, s]))
    const reordered: MemoryProcedureStep[] = []

    for (let i = 0; i < stepIds.length; i++) {
      const step = stepMap.get(stepIds[i])
      if (!step) throw new Error(`Step ${stepIds[i]} not found in procedure ${procedureId}`)
      reordered.push({ ...step, order: i + 1 })
    }

    procedure.steps = reordered
    procedure.updatedAt = new Date().toISOString()

    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${procedure.id}`, serializeEntry(procedure))
    }
  },

  async removeStep(procedureId: string, stepId: string): Promise<void> {
    const procedure = await this.retrieveProcedure(procedureId)
    if (!procedure) throw new Error(`Procedure ${procedureId} not found`)

    procedure.steps = procedure.steps.filter((s) => s.id !== stepId)
    procedure.steps.forEach((s, i) => (s.order = i + 1))
    procedure.updatedAt = new Date().toISOString()

    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${procedure.id}`, serializeEntry(procedure))
    }
  },

  async updateVersion(procedureId: string, version: string): Promise<void> {
    const procedure = await this.retrieveProcedure(procedureId)
    if (!procedure) throw new Error(`Procedure ${procedureId} not found`)

    procedure.version = version
    procedure.updatedAt = new Date().toISOString()

    const client = RedisClient.getClient()
    if (client) {
      await client.hset(`${ENTRY_KEY}:${procedure.id}`, serializeEntry(procedure))
    }
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
    const entries = await this.findProceduresByTag(sessionId, "")
    return entries.length
  },

  async clearAll(): Promise<void> {
    const client = RedisClient.getClient()
    if (!client) return
    await RedisClient.flushPrefix("procedural:")
  },
}
