import type { CognitiveMetrics } from "./types"
import { CognitiveSessionManager } from "./CognitiveSessionManager"
import { CognitiveRoutingEngine } from "./CognitiveRoutingEngine"
import { WorkerCoordinationEngine } from "./WorkerCoordinationEngine"

interface CollectedMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  totalStagesCompleted: number
  totalStagesFailed: number
  stageDurations: Record<string, number>
  workerUtilization: Record<string, number>
  routingDecisions: number
  retries: number
  failures: number
  avgSessionDurationMs: number
}

const metricsStore = new Map<string, CollectedMetrics>()

export const CognitiveMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    metricsStore.set(systemId, {
      activeSessions: 0,
      completedSessions: 0,
      failedSessions: 0,
      totalStagesCompleted: 0,
      totalStagesFailed: 0,
      stageDurations: {},
      workerUtilization: {},
      routingDecisions: 0,
      retries: 0,
      failures: 0,
      avgSessionDurationMs: 0,
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
      m.failures++
    }
  },

  async recordStageCompleted(systemId: string, stageName: string, durationMs: number): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) {
      m.totalStagesCompleted++
      m.stageDurations[stageName] = (m.stageDurations[stageName] ?? 0) + durationMs
    }
  },

  async recordStageFailed(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) {
      m.totalStagesFailed++
      m.failures++
    }
  },

  async recordRetry(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.retries++
  },

  async recordRoutingDecision(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.routingDecisions++
  },

  async recordWorkerUtilization(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) {
      m.workerUtilization = await WorkerCoordinationEngine.getWorkerUtilization()
    }
  },

  async collect(systemId: string): Promise<CognitiveMetrics> {
    const m = metricsStore.get(systemId)
    if (!m) throw new Error(`Metrics not initialized for system ${systemId}`)

    const sessions = await CognitiveSessionManager.getAll()
    const activeSessions = sessions.filter((s) => s.status === "active" || s.status === "pending").length
    const completedSessions = sessions.filter((s) => s.status === "completed").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length

    const completed = sessions.filter((s) => s.completedAt !== null && s.status === "completed")
    const avgDuration = completed.length > 0
      ? completed.reduce((sum, s) => sum + (new Date(s.completedAt!).getTime() - new Date(s.startedAt).getTime()), 0) / completed.length
      : 0

    const totalDecisions = Array.from(
      (await Promise.all(sessions.map((s) => CognitiveRoutingEngine.getDecisionsBySession(s.id)))).flat(),
    ).length

    return {
      activeSessions,
      completedSessions,
      failedSessions,
      totalStagesCompleted: m.totalStagesCompleted,
      totalStagesFailed: m.totalStagesFailed,
      stageDurations: { ...m.stageDurations },
      workerUtilization: { ...m.workerUtilization },
      routingDecisions: totalDecisions,
      retries: m.retries,
      failures: m.failures,
      avgSessionDurationMs: Math.round(avgDuration),
      updatedAt: new Date().toISOString(),
    }
  },

  async getRaw(systemId: string): Promise<CollectedMetrics | undefined> {
    return metricsStore.get(systemId)
  },
}
