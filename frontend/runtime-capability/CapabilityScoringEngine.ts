import type { CapabilityCandidate, CapabilityMatch, CapabilityScore, CapabilityRequirement } from "./types"
import type { ExecutionWorker } from "@/runtime-core/types"

const MATCH_WEIGHT = 0.35
const AVAILABILITY_WEIGHT = 0.20
const HEALTH_WEIGHT = 0.20
const LOAD_WEIGHT = 0.15
const PRIORITY_WEIGHT = 0.10

export const CapabilityScoringEngine = {
  async scoreCandidate(
    worker: ExecutionWorker,
    match: CapabilityMatch,
    requirement: CapabilityRequirement,
    maxLoad: number,
  ): Promise<CapabilityScore> {
    const matchScore = calculateMatchScore(match)
    const availabilityScore = calculateAvailabilityScore(worker)
    const healthScore = calculateHealthScore(worker)
    const loadScore = calculateLoadScore(worker, maxLoad)
    const priorityScore = calculatePriorityScore(requirement.priority)

    const totalScore =
      matchScore * MATCH_WEIGHT +
      availabilityScore * AVAILABILITY_WEIGHT +
      healthScore * HEALTH_WEIGHT +
      loadScore * LOAD_WEIGHT +
      priorityScore * PRIORITY_WEIGHT

    const breakdown = `match=${Math.round(matchScore * 100)}%×${MATCH_WEIGHT} + avail=${Math.round(availabilityScore * 100)}%×${AVAILABILITY_WEIGHT} + health=${Math.round(healthScore * 100)}%×${HEALTH_WEIGHT} + load=${Math.round(loadScore * 100)}%×${LOAD_WEIGHT} + priority=${Math.round(priorityScore * 100)}%×${PRIORITY_WEIGHT} = ${Math.round(totalScore * 100)}%`

    return {
      candidateId: "",
      workerId: worker.id,
      matchScore,
      availabilityScore,
      healthScore,
      loadScore,
      priorityScore,
      totalScore,
      breakdown,
    }
  },
}

function calculateMatchScore(match: CapabilityMatch): number {
  switch (match.precision) {
    case "exact":
      return match.versionCompatible ? 1.0 : 0.8
    case "partial":
      return match.versionCompatible
        ? 0.5 + (match.matchedFeatures.length / Math.max(match.matchedFeatures.length + match.unmatchedFeatures.length, 1)) * 0.4
        : 0.3
    case "cross_train":
      return 0.2
    case "none":
      return 0.0
  }
}

function calculateAvailabilityScore(worker: ExecutionWorker): number {
  return worker.status === "idle" ? 1.0
    : worker.status === "busy" ? 0.3
    : worker.status === "error" ? 0.0
    : 0.0
}

function calculateHealthScore(worker: ExecutionWorker): number {
  if (!worker.lastHeartbeat) return 0.5
  const elapsed = Date.now() - new Date(worker.lastHeartbeat).getTime()
  const MAX_HEARTBEAT_AGE = 120000

  if (elapsed < MAX_HEARTBEAT_AGE) return 1.0
  if (elapsed < MAX_HEARTBEAT_AGE * 2) return 0.5
  if (worker.totalTasksFailed > worker.totalTasksCompleted && worker.totalTasksCompleted > 0) return 0.3
  return 0.2
}

function calculateLoadScore(worker: ExecutionWorker, maxLoad: number): number {
  if (worker.status === "idle") return 1.0
  if (worker.status === "busy") return 0.3
  return 0.0
}

function calculatePriorityScore(priority: number): number {
  return Math.min(priority / 10, 1.0)
}
