import type { ExecutionMetrics } from "./types"
import { ExecutionSessionManager } from "./ExecutionSessionManager"
import { ExecutionDependencyManager } from "./ExecutionDependencyManager"
import { TaskDistributionEngine } from "./TaskDistributionEngine"

interface CollectedMetrics {
  activeSessions: number
  completedSessions: number
  failedSessions: number
  totalTasksDistributed: number
  totalTasksCompleted: number
  totalTasksFailed: number
  assignmentUtilization: Record<string, number>
  dependencyCount: number
  validationPasses: number
  validationFailures: number
  avgSessionDurationMs: number
}

const metricsStore = new Map<string, CollectedMetrics>()

export const ExecutionMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    metricsStore.set(systemId, {
      activeSessions: 0,
      completedSessions: 0,
      failedSessions: 0,
      totalTasksDistributed: 0,
      totalTasksCompleted: 0,
      totalTasksFailed: 0,
      assignmentUtilization: {},
      dependencyCount: 0,
      validationPasses: 0,
      validationFailures: 0,
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
    }
  },

  async recordTasksDistributed(systemId: string, count: number): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.totalTasksDistributed += count
  },

  async recordTaskCompleted(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.totalTasksCompleted++
  },

  async recordTaskFailed(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.totalTasksFailed++
  },

  async recordValidationPass(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.validationPasses++
  },

  async recordValidationFailure(systemId: string): Promise<void> {
    const m = metricsStore.get(systemId)
    if (m) m.validationFailures++
  },

  async collect(systemId: string): Promise<ExecutionMetrics> {
    const m = metricsStore.get(systemId)
    if (!m) throw new Error(`Metrics not initialized for system ${systemId}`)

    const sessions = await ExecutionSessionManager.getAll()
    const activeSessions = sessions.filter((s) =>
      s.status === "planning" || s.status === "distributing" || s.status === "executing",
    ).length
    const completedSessions = sessions.filter((s) => s.status === "completed").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length

    const completed = sessions.filter((s) => s.completedAt !== null && s.status === "completed")
    const avgDuration = completed.length > 0
      ? completed.reduce((sum, s) => sum + (new Date(s.completedAt!).getTime() - new Date(s.startedAt).getTime()), 0) / completed.length
      : 0

    const depCount = await ExecutionDependencyManager.countBySession("")
    const util = await TaskDistributionEngine.getUtilization()

    return {
      activeSessions,
      completedSessions,
      failedSessions,
      totalTasksDistributed: m.totalTasksDistributed,
      totalTasksCompleted: m.totalTasksCompleted,
      totalTasksFailed: m.totalTasksFailed,
      assignmentUtilization: { ...util },
      dependencyCount: depCount,
      validationPasses: m.validationPasses,
      validationFailures: m.validationFailures,
      avgSessionDurationMs: Math.round(avgDuration),
      updatedAt: new Date().toISOString(),
    }
  },
}
