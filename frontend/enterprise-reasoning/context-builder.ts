import type { ReasoningContext, ReasonedMemoryEntry, ReasonedRelationship } from "./types"
import type { CognitiveMemory } from "@/cognitive-memory/CognitiveMemory"
import type { KnowledgeGraph } from "@/knowledge-graph/KnowledgeGraph"
import type { MemoryScope } from "@/cognitive-memory/types"

const conversationHistory: Map<string, string[]> = new Map()
let cognitiveMemoryRef: CognitiveMemory | null = null
let knowledgeGraphRef: KnowledgeGraph | null = null

export const ReasoningContextBuilder = {
  async setCognitiveMemory(memory: CognitiveMemory): Promise<void> {
    cognitiveMemoryRef = memory
  },

  async setKnowledgeGraph(graph: KnowledgeGraph): Promise<void> {
    knowledgeGraphRef = graph
  },

  async build(sessionId: string, missionId: string, missionObjective: string, missionPriority: string, additional: Record<string, unknown> = {}): Promise<ReasoningContext> {
    const history = conversationHistory.get(sessionId) ?? []
    const memoryEntries = await this.retrieveMemory(sessionId, missionId)
    const relationships = await this.retrieveKnowledgeGraph(missionId)
    const connectorState = (additional.connectorState as Record<string, unknown>) ?? {}
    const workerState = (additional.workerState as Record<string, unknown>) ?? {}

    return {
      missionId,
      missionObjective,
      missionPriority: missionPriority as "low" | "medium" | "high" | "critical",
      conversationHistory: history,
      memoryEntries,
      knowledgeRelationships: relationships,
      connectorState,
      workerState,
      additionalContext: additional,
    }
  },

  async retrieveMemory(sessionId: string, missionId: string): Promise<ReasonedMemoryEntry[]> {
    const entries: ReasonedMemoryEntry[] = []

    if (cognitiveMemoryRef) {
      try {
        const memSessionId = `mission-${missionId}`
        const recallResult = await cognitiveMemoryRef.recall({
          sessionId: memSessionId,
          query: missionId,
          types: ["working", "episodic", "semantic"],
          strategy: "recent",
          maxResults: 20,
          minConfidence: 0,
          scope: "session" as MemoryScope,
          timeRangeMs: null,
        })

        for (const entry of recallResult.entries) {
          entries.push({
            id: entry.id,
            content: entry.type === "working"
              ? `${(entry as unknown as { key: string }).key}: ${JSON.stringify((entry as unknown as { value: unknown }).value)}`
              : (entry as unknown as { summary?: string }).summary ?? entry.id,
            relevance: 1.0,
            timestamp: entry.createdAt,
          })
        }
      } catch {
        // memory unavailable
      }
    }

    return entries
  },

  async retrieveKnowledgeGraph(missionId: string): Promise<ReasonedRelationship[]> {
    const relationships: ReasonedRelationship[] = []

    if (knowledgeGraphRef) {
      try {
        const entities = await knowledgeGraphRef.queryEntities({ field: "missionId", value: missionId })
        for (const entity of entities) {
          const rels = await knowledgeGraphRef.findRelationships(entity.id)
          for (const rel of rels) {
            relationships.push({
              source: rel.sourceId,
              target: rel.targetId,
              relationship: rel.type,
              strength: rel.weight ?? 0.5,
            })
          }
        }
      } catch {
        // graph unavailable
      }
    }

    return relationships
  },

  async addToHistory(sessionId: string, entry: string): Promise<void> {
    const history = conversationHistory.get(sessionId) ?? []
    history.push(entry)
    if (history.length > 50) history.shift()
    conversationHistory.set(sessionId, history)
  },

  async enrichWithRedisMemory(entries: ReasonedMemoryEntry[], redisEntries: Array<{ id: string; content: string; score: number; timestamp: string }>): Promise<ReasonedMemoryEntry[]> {
    for (const re of redisEntries) {
      if (!entries.find((e) => e.id === re.id)) {
        entries.push({ id: re.id, content: re.content, relevance: re.score, timestamp: re.timestamp })
      }
    }
    return entries.sort((a, b) => b.relevance - a.relevance).slice(0, 20)
  },

  async enrichWithNeo4jRelationships(relationships: ReasonedRelationship[], neo4jRels: Array<{ source: string; target: string; relationship: string; strength: number }>): Promise<ReasonedRelationship[]> {
    for (const rel of neo4jRels) {
      if (!relationships.find((r) => r.source === rel.source && r.target === rel.target && r.relationship === rel.relationship)) {
        relationships.push(rel)
      }
    }
    return relationships.sort((a, b) => b.strength - a.strength).slice(0, 30)
  },

  async clearSession(sessionId: string): Promise<void> {
    conversationHistory.delete(sessionId)
  },
}