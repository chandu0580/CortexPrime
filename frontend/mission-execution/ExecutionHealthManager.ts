import type { ExecutionHealth } from "./types"
import { ExecutionSessionManager } from "./ExecutionSessionManager"
import { ExecutionPolicyEngine } from "./ExecutionPolicyEngine"

interface IntegrityRecord {
  activeSessions: number
  stalledExecutions: number
  failedAssignments: number
  dependencyFailures: number
  policyViolations: number
  recoveryReady: boolean
}

const healthStore = new Map<string, IntegrityRecord>()

export const ExecutionHealthManager = {
  async initialize(systemId: string): Promise<void> {
    healthStore.set(systemId, {
      activeSessions: 0,
      stalledExecutions: 0,
      failedAssignments: 0,
      dependencyFailures: 0,
      policyViolations: 0,
      recoveryReady: true,
    })
  },

  async recordIntegrity(systemId: string, record: Partial<IntegrityRecord>): Promise<void> {
    const current = healthStore.get(systemId)
    if (current) {
      healthStore.set(systemId, { ...current, ...record })
    }
  },

  async recordStalledExecution(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.stalledExecutions++
  },

  async recordFailedAssignment(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.failedAssignments++
  },

  async recordDependencyFailure(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.dependencyFailures++
  },

  async check(systemId: string): Promise<ExecutionHealth> {
    const h = healthStore.get(systemId)
    if (!h) throw new Error(`Health not initialized for system ${systemId}`)

    const sessions = await ExecutionSessionManager.getAll()
    const activeSessions = sessions.filter((s) =>
      s.status === "planning" || s.status === "distributing" || s.status === "executing",
    ).length
    const stalledSessions = sessions.filter((s) => s.status === "executing").length
    const failedSessions = sessions.filter((s) => s.status === "failed").length
    const policyViolations = await ExecutionPolicyEngine.countViolations()

    let status: ExecutionHealth["status"] = "healthy"
    if (failedSessions > 0 || stalledSessions > 0 || h.failedAssignments > 0) {
      status = "degraded"
    }
    if (failedSessions > 3 || policyViolations > 10 || h.dependencyFailures > 5) {
      status = "unhealthy"
    }

    const issues: string[] = []
    if (stalledSessions > 0) issues.push(`${stalledSessions} stalled execution(s)`)
    if (h.failedAssignments > 0) issues.push(`${h.failedAssignments} failed assignment(s)`)
    if (h.dependencyFailures > 0) issues.push(`${h.dependencyFailures} dependency failure(s)`)
    if (policyViolations > 0) issues.push(`${policyViolations} policy violation(s)`)

    await this.recordIntegrity(systemId, {
      activeSessions,
      stalledExecutions: stalledSessions,
      policyViolations,
    })

    return {
      status,
      activeSessions,
      stalledExecutions: stalledSessions,
      failedAssignments: h.failedAssignments,
      dependencyFailures: h.dependencyFailures,
      policyViolations,
      recoveryReady: status !== "unhealthy",
      lastCheckAt: new Date().toISOString(),
      issues,
    }
  },
}
