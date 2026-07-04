import type { IntelligenceMetrics } from "./types"

const workerMetrics = new Map<string, {
  totalSessions: number
  totalPlans: number
  totalObjectives: number
  totalEvidence: number
  totalInsights: number
  totalRecommendations: number
  totalSummaries: number
  totalActivities: number
  totalErrors: number
  planDurations: number[]
  evidenceCounts: number[]
  insightCounts: number[]
  startedAt: string
}>()

export const IntelligenceMetricsCollector = {
  async initialize(workerId: string): Promise<void> {
    if (workerMetrics.has(workerId)) return
    workerMetrics.set(workerId, {
      totalSessions: 0,
      totalPlans: 0,
      totalObjectives: 0,
      totalEvidence: 0,
      totalInsights: 0,
      totalRecommendations: 0,
      totalSummaries: 0,
      totalActivities: 0,
      totalErrors: 0,
      planDurations: [],
      evidenceCounts: [],
      insightCounts: [],
      startedAt: new Date().toISOString(),
    })
  },

  async recordSessionCreated(workerId: string): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalSessions++
  },

  async recordPlan(workerId: string): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalPlans++
  },

  async recordObjective(workerId: string, count: number): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalObjectives += count
  },

  async recordEvidence(workerId: string, count: number): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) {
      m.totalEvidence += count
      m.evidenceCounts.push(count)
    }
  },

  async recordInsight(workerId: string, count: number): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) {
      m.totalInsights += count
      m.insightCounts.push(count)
    }
  },

  async recordRecommendation(workerId: string, count: number): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalRecommendations += count
  },

  async recordSummary(workerId: string): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalSummaries++
  },

  async recordActivity(workerId: string): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalActivities++
  },

  async recordError(workerId: string): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.totalErrors++
  },

  async recordPlanDuration(workerId: string, durationMs: number): Promise<void> {
    const m = workerMetrics.get(workerId)
    if (m) m.planDurations.push(durationMs)
  },

  async collect(workerId: string, activeSessions: number): Promise<IntelligenceMetrics> {
    const m = workerMetrics.get(workerId)
    if (!m) {
      return {
        workerId,
        totalSessions: 0,
        activeSessions: 0,
        totalPlans: 0,
        totalObjectives: 0,
        totalEvidence: 0,
        totalInsights: 0,
        totalRecommendations: 0,
        totalSummaries: 0,
        totalActivities: 0,
        totalErrors: 0,
        averagePlanCompletionMs: 0,
        averageEvidencePerSession: 0,
        averageInsightsPerSession: 0,
        uptimeMs: 0,
        collectedAt: new Date().toISOString(),
      }
    }

    const avg = (arr: number[]): number => arr.length > 0 ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0
    const avgEvidence = m.evidenceCounts.length > 0 ? Math.round(m.evidenceCounts.reduce((a, b) => a + b, 0) / m.evidenceCounts.length) : 0
    const avgInsights = m.insightCounts.length > 0 ? Math.round(m.insightCounts.reduce((a, b) => a + b, 0) / m.insightCounts.length) : 0
    const uptime = Date.now() - new Date(m.startedAt).getTime()

    return {
      workerId,
      totalSessions: m.totalSessions,
      activeSessions,
      totalPlans: m.totalPlans,
      totalObjectives: m.totalObjectives,
      totalEvidence: m.totalEvidence,
      totalInsights: m.totalInsights,
      totalRecommendations: m.totalRecommendations,
      totalSummaries: m.totalSummaries,
      totalActivities: m.totalActivities,
      totalErrors: m.totalErrors,
      averagePlanCompletionMs: avg(m.planDurations),
      averageEvidencePerSession: avgEvidence,
      averageInsightsPerSession: avgInsights,
      uptimeMs: uptime,
      collectedAt: new Date().toISOString(),
    }
  },

  async reset(workerId: string): Promise<void> {
    workerMetrics.delete(workerId)
  },
}
