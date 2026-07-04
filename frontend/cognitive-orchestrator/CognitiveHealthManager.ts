import type { CognitiveHealth } from "./types"
import { CognitiveSessionManager } from "./CognitiveSessionManager"
import { CognitivePolicyEngine } from "./CognitivePolicyEngine"

interface IntegrityRecord {
  activeSessions: number
  stalledSessions: number
  failedStages: number
  recoveryReady: boolean
  policyViolations: number
}

const healthStore = new Map<string, IntegrityRecord>()

export const CognitiveHealthManager = {
  async initialize(systemId: string): Promise<void> {
    healthStore.set(systemId, {
      activeSessions: 0,
      stalledSessions: 0,
      failedStages: 0,
      recoveryReady: true,
      policyViolations: 0,
    })
  },

  async recordIntegrity(systemId: string, record: Partial<IntegrityRecord>): Promise<void> {
    const current = healthStore.get(systemId)
    if (current) {
      healthStore.set(systemId, { ...current, ...record })
    }
  },

  async recordStalledSession(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.stalledSessions++
  },

  async recordFailedStage(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.failedStages++
  },

  async recordRecovery(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) {
      h.recoveryReady = true
      h.stalledSessions = Math.max(0, h.stalledSessions - 1)
      h.failedStages = Math.max(0, h.failedStages - 1)
    }
  },

  async check(systemId: string): Promise<CognitiveHealth> {
    const h = healthStore.get(systemId)
    if (!h) throw new Error(`Health not initialized for system ${systemId}`)

    const sessions = await CognitiveSessionManager.getAll()
    const activeSessions = sessions.filter((s) => s.status === "active" || s.status === "pending").length
    const stalledSessions = sessions.filter((s) => s.status === "active" && s.currentStage !== "completion").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length

    const failedStages = sessions.reduce((count, s) => {
      return count + s.stages.filter((st) => st.status === "failed").length
    }, 0)

    const policyViolations = await CognitivePolicyEngine.countViolations()

    let status: CognitiveHealth["status"] = "healthy"
    if (failedSessions > 0 || stalledSessions > 0 || failedStages > 0) {
      status = "degraded"
    }
    if (failedSessions > 5 || policyViolations > 10) {
      status = "unhealthy"
    }

    const issues: string[] = []
    if (stalledSessions > 0) issues.push(`${stalledSessions} stalled session(s)`)
    if (failedStages > 0) issues.push(`${failedStages} failed stage(s)`)
    if (policyViolations > 0) issues.push(`${policyViolations} policy violation(s)`)

    await this.recordIntegrity(systemId, {
      activeSessions,
      stalledSessions,
      failedStages,
      recoveryReady: status !== "unhealthy",
      policyViolations,
    })

    return {
      status,
      activeSessions,
      stalledSessions,
      failedStages,
      recoveryReady: status !== "unhealthy",
      policyViolations,
      lastCheckAt: new Date().toISOString(),
      issues,
    }
  },
}
