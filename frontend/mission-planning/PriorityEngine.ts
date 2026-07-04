import type { PlanningPriority, PlanningPriorityScore, MissionPlan } from "./types"
import { generateId } from "@/worker-framework/shared"
import { MissionPlanner } from "./MissionPlanner"

const scores = new Map<string, PlanningPriorityScore>()

const URGENCY_FACTORS: Record<PlanningPriority, number> = {
  critical: 1.0,
  high: 0.75,
  medium: 0.5,
  low: 0.25,
  backlog: 0.1,
}

export const PriorityEngine = {
  async calculatePriority(missionId: string, sessionId: string, level: PlanningPriority = "medium"): Promise<PlanningPriorityScore> {
    const baseScore = URGENCY_FACTORS[level]
    const score: PlanningPriorityScore = {
      id: generateId("plan-priority"),
      missionId,
      sessionId,
      level,
      score: baseScore,
      urgency: baseScore,
      impact: Math.round(baseScore * 100),
      effort: Math.round((1 - baseScore) * 100),
      calculatedAt: new Date().toISOString(),
    }
    scores.set(score.id, score)
    return score
  },

  async reorderPlans(sessionId: string): Promise<MissionPlan[]> {
    const plans = await MissionPlanner.getPlansBySession(sessionId)
    const plansWithScores = await Promise.all(
      plans.map(async (p) => {
        const score = await this.getScore(p.id, sessionId)
        return { plan: p, score: score?.score ?? 0.5 }
      }),
    )
    plansWithScores.sort((a, b) => b.score - a.score)
    return plansWithScores.map((ps) => ps.plan)
  },

  async rebalancePriorities(sessionId: string): Promise<PlanningPriorityScore[]> {
    const sessionScores = Array.from(scores.values()).filter((s) => s.sessionId === sessionId)
    const maxScore = Math.max(...sessionScores.map((s) => s.score), 0.1)
    const minScore = Math.min(...sessionScores.map((s) => s.score), 0)

    return sessionScores.map((s) => {
      const normalized = maxScore > minScore ? (s.score - minScore) / (maxScore - minScore) : 0.5
      s.score = Math.round(normalized * 100) / 100
      s.urgency = Math.round(normalized * 100) / 100
      s.impact = Math.round(normalized * 100)
      s.effort = Math.round((1 - normalized) * 100)
      s.calculatedAt = new Date().toISOString()
      return s
    })
  },

  async evaluateUrgency(missionId: string, sessionId: string, deadlineMs: number, currentTimeMs: number): Promise<PlanningPriority> {
    const remainingMs = deadlineMs - currentTimeMs
    if (remainingMs <= 0) return "critical"
    if (remainingMs <= 3600000) return "high"
    if (remainingMs <= 86400000) return "medium"
    if (remainingMs <= 604800000) return "low"
    return "backlog"
  },

  async getScore(missionId: string, sessionId: string): Promise<PlanningPriorityScore | null> {
    return Array.from(scores.values()).find(
      (s) => s.missionId === missionId && s.sessionId === sessionId,
    ) ?? null
  },

  async getScoresBySession(sessionId: string): Promise<PlanningPriorityScore[]> {
    return Array.from(scores.values()).filter((s) => s.sessionId === sessionId)
  },
}
