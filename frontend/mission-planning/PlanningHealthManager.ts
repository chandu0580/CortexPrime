import type { PlanningHealth } from "./types"
import { PlanningSessionManager } from "./PlanningSessionManager"
import { PlanningPolicyEngine } from "./PlanningPolicyEngine"

interface IntegrityRecord {
  activeSessions: number
  planningFailures: number
  dependencyIssues: number
  resourceConflicts: number
  optimizationFailures: number
  policyViolations: number
  recoveryReady: boolean
}

const healthStore = new Map<string, IntegrityRecord>()

export const PlanningHealthManager = {
  async initialize(systemId: string): Promise<void> {
    healthStore.set(systemId, {
      activeSessions: 0,
      planningFailures: 0,
      dependencyIssues: 0,
      resourceConflicts: 0,
      optimizationFailures: 0,
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

  async recordPlanningFailure(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.planningFailures++
  },

  async recordDependencyIssue(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.dependencyIssues++
  },

  async recordResourceConflict(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.resourceConflicts++
  },

  async recordOptimizationFailure(systemId: string): Promise<void> {
    const h = healthStore.get(systemId)
    if (h) h.optimizationFailures++
  },

  async check(systemId: string): Promise<PlanningHealth> {
    const h = healthStore.get(systemId)
    if (!h) throw new Error(`Health not initialized for system ${systemId}`)

    const sessions = await PlanningSessionManager.getAll()
    const activeSessions = sessions.filter((s) =>
      s.status === "draft" || s.status === "planning" || s.status === "analyzing" || s.status === "optimizing" || s.status === "validating",
    ).length
    const failedSessions = sessions.filter((s) => s.status === "failed").length
    const policyViolations = await PlanningPolicyEngine.countViolations()

    let status: PlanningHealth["status"] = "healthy"
    if (failedSessions > 0 || h.dependencyIssues > 0 || h.resourceConflicts > 0) {
      status = "degraded"
    }
    if (failedSessions > 3 || h.optimizationFailures > 5 || policyViolations > 10) {
      status = "unhealthy"
    }

    const issues: string[] = []
    if (h.planningFailures > 0) issues.push(`${h.planningFailures} planning failure(s)`)
    if (h.dependencyIssues > 0) issues.push(`${h.dependencyIssues} dependency issue(s)`)
    if (h.resourceConflicts > 0) issues.push(`${h.resourceConflicts} resource conflict(s)`)
    if (h.optimizationFailures > 0) issues.push(`${h.optimizationFailures} optimization failure(s)`)
    if (policyViolations > 0) issues.push(`${policyViolations} policy violation(s)`)

    await this.recordIntegrity(systemId, {
      activeSessions,
      policyViolations: policyViolations,
    })

    return {
      status,
      activeSessions,
      planningFailures: h.planningFailures,
      dependencyIssues: h.dependencyIssues,
      resourceConflicts: h.resourceConflicts,
      optimizationFailures: h.optimizationFailures,
      recoveryReady: status !== "unhealthy",
      lastCheckAt: new Date().toISOString(),
      issues,
    }
  },
}
