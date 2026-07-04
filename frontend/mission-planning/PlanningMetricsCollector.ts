import type { PlanningMetrics } from "./types"
import { PlanningSessionManager } from "./PlanningSessionManager"
import { DependencyPlanner } from "./DependencyPlanner"
import { PortfolioPlanner } from "./PortfolioPlanner"

interface CollectedMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  plansCreated: number
  plansFinalized: number
  totalDependencies: number
  resolvedDependencies: number
  resourceEstimates: number
  portfolioCount: number
  avgPlanningDurationMs: number
}

const metricsStore = new Map<string, CollectedMetrics>()

export const PlanningMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    metricsStore.set(systemId, {
      activeSessions: 0,
      completedSessions: 0,
      failedSessions: 0,
      plansCreated: 0,
      plansFinalized: 0,
      totalDependencies: 0,
      resolvedDependencies: 0,
      resourceEstimates: 0,
      portfolioCount: 0,
      avgPlanningDurationMs: 0,
    })
  },

  async recordSessionCreated(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.activeSessions++
  },

  async recordSessionCompleted(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) {
      m.activeSessions = Math.max(0, m.activeSessions - 1)
      m.completedSessions++
    }
  },

  async recordSessionFailed(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) {
      m.activeSessions = Math.max(0, m.activeSessions - 1)
      m.failedSessions++
    }
  },

  async recordPlanCreated(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.plansCreated++
  },

  async recordPlanFinalized(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.plansFinalized++
  },

  async recordResourceEstimate(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.resourceEstimates++
  },

  async recordDependency(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.totalDependencies++
  },

  async collect(systemId: string): Promise<PlanningMetrics> {
    const m = metricsStore.get(systemId)
    if (!m) throw new Error(`Metrics not initialized for system ${systemId}`)

    const sessions = await PlanningSessionManager.getAll()
    const activeSessions = sessions.filter((s) =>
      s.status === "draft" || s.status === "planning" || s.status === "analyzing" || s.status === "optimizing" || s.status === "validating",
    ).length
    const completedSessions = sessions.filter((s) => s.status === "finalized").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length

    const completed = sessions.filter((s) => s.completedAt !== null && s.status === "finalized")
    const avgDuration = completed.length > 0
      ? completed.reduce((sum, s) => sum + (new Date(s.completedAt!).getTime() - new Date(s.startedAt).getTime()), 0) / completed.length
      : 0

    const depCount = await DependencyPlanner.countBySession("")
    const portfolioCount = await PortfolioPlanner.count()

    return {
      activeSessions,
      completedSessions,
      failedSessions,
      plansCreated: m.plansCreated,
      plansFinalized: m.plansFinalized,
      totalDependencies: depCount,
      resolvedDependencies: 0,
      resourceEstimates: m.resourceEstimates,
      portfolioCount,
      avgPlanningDurationMs: Math.round(avgDuration),
      updatedAt: new Date().toISOString(),
    }
  },
}
