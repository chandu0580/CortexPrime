import type { MissionExecutionGraph } from "@/mission-orchestrator/types"
import type {
  ReadinessCheck,
  ExecutionBlocker,
  ExecutionWindow,
  ReadinessStatus,
} from "./types"
import { generateId } from "./shared"

export const ReadinessAssessmentEngine = {
  async assessReadiness(
    graph: MissionExecutionGraph,
    checks: ReadinessCheck[],
  ): Promise<{
    overallStatus: ReadinessStatus
    blockers: ExecutionBlocker[]
    window: ExecutionWindow
    passingChecks: number
    totalChecks: number
    summary: string
  }> {
    const failedChecks = checks.filter((c) => c.result === "fail")
    const warningChecks = checks.filter((c) => c.result === "warning")
    const infoChecks = checks.filter((c) => c.result === "info")
    const passingChecks = checks.filter((c) => c.result === "pass").length
    const totalChecks = checks.length

    const blockers: ExecutionBlocker[] = failedChecks.map((check) => ({
      id: generateId("blocker"),
      checkId: check.id,
      reason: check.details,
      severity: check.type === "dependency" || check.type === "authorization" ? "critical" : "major",
      autoResolvable: check.type === "capability",
      resolutionHint: check.type === "dependency"
        ? "Resolve outstanding dependencies before proceeding"
        : check.type === "capability"
          ? "Assign capabilities to unassigned nodes"
          : check.type === "policy"
            ? "Address failed policy evaluations"
            : check.type === "authorization"
              ? "Obtain required authorization level"
              : "Review and resolve blocker",
    }))

    const overallStatus: ReadinessStatus = determineOverallStatus(failedChecks.length, warningChecks.length, infoChecks.length)

    const window: ExecutionWindow = {
      id: generateId("window"),
      openAt: null,
      closeAt: null,
      duration: "7 days",
      recurring: false,
      schedule: null,
      withinWindow: overallStatus === "READY",
    }

    const summary = buildSummary(overallStatus, passingChecks, totalChecks, failedChecks, warningChecks, blockers)

    return { overallStatus, blockers, window, passingChecks, totalChecks, summary }
  },
}

function determineOverallStatus(
  failedCount: number,
  warningCount: number,
  infoCount: number,
): ReadinessStatus {
  if (failedCount > 0) {
    const criticalBlockers = Math.random() > 0.5
    return criticalBlockers ? "BLOCKED" : "REQUIRES_INTERVENTION"
  }
  if (warningCount > 0 && warningCount <= 2) return "REQUIRES_REVIEW"
  if (warningCount > 2) return "REQUIRES_INTERVENTION"
  if (infoCount === 0) return "READY"
  return "WAITING"
}

function buildSummary(
  status: ReadinessStatus,
  passing: number,
  total: number,
  failed: ReadinessCheck[],
  warnings: ReadinessCheck[],
  blockers: ExecutionBlocker[],
): string {
  const parts: string[] = [
    `Readiness: ${status}`,
    `${passing}/${total} checks passing`,
  ]
  if (failed.length > 0) parts.push(`${failed.length} failures`)
  if (warnings.length > 0) parts.push(`${warnings.length} warnings`)
  if (blockers.length > 0) parts.push(`${blockers.length} blockers identified`)

  switch (status) {
    case "READY":
      parts.push("GO — execution may proceed")
      break
    case "WAITING":
      parts.push("Incomplete information — awaiting additional data")
      break
    case "BLOCKED":
      parts.push("Cannot proceed — blockers must be resolved")
      break
    case "REQUIRES_REVIEW":
      parts.push("Review recommended before execution")
      break
    case "REQUIRES_INTERVENTION":
      parts.push("Intervention required — conditions not met for safe execution")
      break
  }

  return parts.join(". ")
}
