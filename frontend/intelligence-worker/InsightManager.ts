import type { Insight, InsightPriority } from "./types"
import { generateId } from "@/worker-framework/shared"

const insightsMap = new Map<string, Insight>()

export const InsightManager = {
  async createInsight(
    sessionId: string,
    evidenceIds: string[],
    title: string,
    description: string,
    priority: InsightPriority = "medium",
  ): Promise<Insight> {
    const insight: Insight = {
      id: generateId("intel-insight"),
      sessionId,
      evidenceIds: [...evidenceIds],
      title,
      description,
      priority,
      groupKey: null,
      validated: false,
      validationReasons: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    insightsMap.set(insight.id, insight)
    return insight
  },

  async getInsight(insightId: string): Promise<Insight | null> {
    return insightsMap.get(insightId) ?? null
  },

  async updateInsight(insightId: string, updates: Partial<Pick<Insight, "title" | "description" | "priority" | "evidenceIds">>): Promise<Insight> {
    const insight = insightsMap.get(insightId)
    if (!insight) throw new Error(`Insight ${insightId} not found`)

    if (updates.title !== undefined) insight.title = updates.title
    if (updates.description !== undefined) insight.description = updates.description
    if (updates.priority !== undefined) insight.priority = updates.priority
    if (updates.evidenceIds !== undefined) insight.evidenceIds = [...updates.evidenceIds]
    insight.updatedAt = new Date().toISOString()

    return insight
  },

  async groupInsights(sessionId: string): Promise<Insight[][]> {
    const sessionInsights = Array.from(insightsMap.values()).filter((i) => i.sessionId === sessionId)
    const groups = new Map<string, Insight[]>()

    for (const insight of sessionInsights) {
      const key = insight.groupKey ?? "ungrouped"
      if (!groups.has(key)) groups.set(key, [])
      groups.get(key)!.push(insight)
    }

    return Array.from(groups.values())
  },

  async setGroupKey(insightId: string, groupKey: string): Promise<void> {
    const insight = insightsMap.get(insightId)
    if (!insight) throw new Error(`Insight ${insightId} not found`)
    insight.groupKey = groupKey
    insight.updatedAt = new Date().toISOString()
  },

  async prioritizeInsight(insightId: string, priority: InsightPriority): Promise<void> {
    const insight = insightsMap.get(insightId)
    if (!insight) throw new Error(`Insight ${insightId} not found`)
    insight.priority = priority
    insight.updatedAt = new Date().toISOString()
  },

  async validateInsight(insightId: string): Promise<{ valid: boolean; reasons: string[] }> {
    const insight = insightsMap.get(insightId)
    if (!insight) throw new Error(`Insight ${insightId} not found`)

    const reasons: string[] = []
    let valid = true

    if (!insight.title || insight.title.trim().length === 0) {
      reasons.push("Insight title is required")
      valid = false
    }
    if (!insight.description || insight.description.trim().length < 20) {
      reasons.push("Insight description must be at least 20 characters")
      valid = false
    }
    if (insight.evidenceIds.length === 0) {
      reasons.push("Insight must reference at least one piece of evidence")
      valid = false
    }

    insight.validated = valid
    insight.validationReasons = reasons
    return { valid, reasons }
  },

  async getInsightsBySession(sessionId: string): Promise<Insight[]> {
    return Array.from(insightsMap.values())
      .filter((i) => i.sessionId === sessionId)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async getInsightsByPriority(sessionId: string, priority: InsightPriority): Promise<Insight[]> {
    return Array.from(insightsMap.values())
      .filter((i) => i.sessionId === sessionId && i.priority === priority)
      .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async getInsightsByEvidence(evidenceId: string): Promise<Insight[]> {
    return Array.from(insightsMap.values()).filter((i) => i.evidenceIds.includes(evidenceId))
  },

  async countBySession(sessionId: string): Promise<number> {
    return Array.from(insightsMap.values()).filter((i) => i.sessionId === sessionId).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, insight] of insightsMap.entries()) {
      if (insight.sessionId === sessionId) {
        insightsMap.delete(id)
      }
    }
  },
}
