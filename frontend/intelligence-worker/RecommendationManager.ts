import type { Recommendation, RecommendationPriority, RecommendationStatus, Evidence, Insight } from "./types"
import { generateId } from "@/worker-framework/shared"

const recommendationsMap = new Map<string, Recommendation>()

const PRIORITY_SCORES: Record<RecommendationPriority, number> = {
  critical: 100,
  high: 75,
  medium: 50,
  low: 25,
}

export const RecommendationManager = {
  async generateRecommendation(
    sessionId: string,
    insightIds: string[],
    evidenceIds: string[],
    title: string,
    description: string,
    rationale: string,
    impact: string,
    effort: string,
    priority: RecommendationPriority = "medium",
  ): Promise<Recommendation> {
    const recommendation: Recommendation = {
      id: generateId("intel-recommendation"),
      sessionId,
      insightIds: [...insightIds],
      evidenceIds: [...evidenceIds],
      title,
      description,
      rationale,
      priority,
      status: "proposed",
      impact,
      effort,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    recommendationsMap.set(recommendation.id, recommendation)
    return recommendation
  },

  async generateFromEvidence(
    sessionId: string,
    evidence: Evidence[],
    insights: Insight[],
  ): Promise<Recommendation[]> {
    const recommendations: Recommendation[] = []

    const criticalInsights = insights.filter((i) => i.priority === "critical" || i.priority === "high")

    for (const insight of criticalInsights) {
      const relatedEvidence = evidence.filter((e) => insight.evidenceIds.includes(e.id))
      const avgConfidence = relatedEvidence.length > 0
        ? relatedEvidence.reduce((sum, e) => sum + e.confidenceScore, 0) / relatedEvidence.length
        : 0

      let priority: RecommendationPriority = "medium"
      if (insight.priority === "critical" && avgConfidence >= 0.8) priority = "critical"
      else if (insight.priority === "high" && avgConfidence >= 0.6) priority = "high"
      else if (avgConfidence < 0.4) priority = "low"

      const rec = await this.generateRecommendation(
        sessionId,
        [insight.id],
        relatedEvidence.map((e) => e.id),
        `Recommendation based on: ${insight.title}`,
        `Derived from insight with ${Math.round(avgConfidence * 100)}% confidence across ${relatedEvidence.length} evidence sources`,
        `Based on insight "${insight.title}" supported by ${relatedEvidence.length} evidence items with average confidence ${Math.round(avgConfidence * 100)}%`,
        "TBD - requires further analysis",
        "TBD - requires further analysis",
        priority,
      )
      recommendations.push(rec)
    }

    return recommendations
  },

  async getRecommendation(recId: string): Promise<Recommendation | null> {
    return recommendationsMap.get(recId) ?? null
  },

  async updateStatus(recId: string, status: RecommendationStatus): Promise<void> {
    const rec = recommendationsMap.get(recId)
    if (!rec) throw new Error(`Recommendation ${recId} not found`)
    rec.status = status
    rec.updatedAt = new Date().toISOString()
  },

  async prioritize(recId: string, priority: RecommendationPriority): Promise<void> {
    const rec = recommendationsMap.get(recId)
    if (!rec) throw new Error(`Recommendation ${recId} not found`)
    rec.priority = priority
    rec.updatedAt = new Date().toISOString()
  },

  async getRecommendationsBySession(sessionId: string): Promise<Recommendation[]> {
    return Array.from(recommendationsMap.values())
      .filter((r) => r.sessionId === sessionId)
      .sort((a, b) => {
        const scoreA = PRIORITY_SCORES[a.priority]
        const scoreB = PRIORITY_SCORES[b.priority]
        return scoreB - scoreA
      })
  },

  async getRecommendationsByStatus(sessionId: string, status: RecommendationStatus): Promise<Recommendation[]> {
    return Array.from(recommendationsMap.values())
      .filter((r) => r.sessionId === sessionId && r.status === status)
      .sort((a, b) => {
        const scoreA = PRIORITY_SCORES[a.priority]
        const scoreB = PRIORITY_SCORES[b.priority]
        return scoreB - scoreA
      })
  },

  async getRecommendationsByPriority(sessionId: string, priority: RecommendationPriority): Promise<Recommendation[]> {
    return Array.from(recommendationsMap.values())
      .filter((r) => r.sessionId === sessionId && r.priority === priority)
  },

  async countBySession(sessionId: string): Promise<number> {
    return Array.from(recommendationsMap.values()).filter((r) => r.sessionId === sessionId).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, rec] of recommendationsMap.entries()) {
      if (rec.sessionId === sessionId) {
        recommendationsMap.delete(id)
      }
    }
  },
}
