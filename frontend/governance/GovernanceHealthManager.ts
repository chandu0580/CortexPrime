import type { GovernanceHealth, HealthSnapshot } from "./types"
import { generateId } from "./shared"

const healthSnapshots: HealthSnapshot[] = []

let failedEvaluations = 0
let policyViolations = 0
let approvalFailures = 0
let complianceFailures = 0

export const GovernanceHealthManager = {
  async recordFailedEvaluation(): Promise<void> {
    failedEvaluations++
  },

  async recordPolicyViolation(): Promise<void> {
    policyViolations++
  },

  async recordApprovalFailure(): Promise<void> {
    approvalFailures++
  },

  async recordComplianceFailure(): Promise<void> {
    complianceFailures++
  },

  async snapshot(component: string, metrics: Record<string, number>, details: string = ""): Promise<HealthSnapshot> {
    const totalFailures = failedEvaluations + policyViolations + approvalFailures + complianceFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    const snapshot: HealthSnapshot = {
      timestamp: new Date().toISOString(),
      component,
      status,
      metrics,
      details,
    }
    healthSnapshots.push(snapshot)
    return snapshot
  },

  async getHealth(): Promise<GovernanceHealth> {
    const totalFailures = failedEvaluations + policyViolations + approvalFailures + complianceFailures
    const status: "healthy" | "degraded" | "unhealthy" = totalFailures === 0 ? "healthy" : totalFailures > 10 ? "unhealthy" : "degraded"

    return {
      status,
      failedEvaluations,
      policyViolations,
      approvalFailures,
      complianceFailures,
      recoveryReady: totalFailures < 5,
      lastSnapshot: healthSnapshots.length > 0 ? healthSnapshots[healthSnapshots.length - 1].timestamp : null,
    }
  },

  async getSnapshots(component?: string, limit: number = 50): Promise<HealthSnapshot[]> {
    let result = [...healthSnapshots]
    if (component) result = result.filter((s) => s.component === component)
    return result.slice(-limit).reverse()
  },

  async resetCounters(): Promise<void> {
    failedEvaluations = 0
    policyViolations = 0
    approvalFailures = 0
    complianceFailures = 0
  },
}
