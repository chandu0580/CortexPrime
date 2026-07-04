import type { CapabilityResolution, CapabilityRequirement, CapabilityCandidate, ResolutionStatus } from "./types"
import type { CapabilityMatch } from "./types"
import type { ExecutionWorker } from "@/runtime-core/types"
import type { CapabilityDescriptor } from "./types"
import { CapabilityCatalog } from "./CapabilityCatalog"
import { CapabilityMatcher } from "./CapabilityMatcher"
import { CapabilityScoringEngine } from "./CapabilityScoringEngine"
import { CapabilityPolicyEngine } from "./CapabilityPolicyEngine"
import { CapabilityAvailabilityManager } from "./CapabilityAvailabilityManager"
import { CapabilityRankingEngine } from "./CapabilityRankingEngine"
import { generateId } from "./shared"

export const CapabilityResolver = {
  async resolve(
    requirement: CapabilityRequirement,
    workers: ExecutionWorker[],
    descriptors: CapabilityDescriptor[],
  ): Promise<CapabilityResolution> {
    const candidates: CapabilityCandidate[] = []

    for (const descriptor of descriptors) {
      if (descriptor.capability !== requirement.requiredCapability) continue

      for (const worker of workers) {
        const match = await CapabilityMatcher.match(requirement, descriptor)
        const matchWithWorkerId: CapabilityMatch = { ...match, workerId: worker.id }

        const score = await CapabilityScoringEngine.scoreCandidate(worker, matchWithWorkerId, requirement, descriptor.maxConcurrency)
        const availability = await CapabilityAvailabilityManager.checkAvailability(descriptor, worker)

        candidates.push({
          id: generateId("candidate"),
          worker,
          descriptor,
          match: matchWithWorkerId,
          score: { ...score, candidateId: generateId("score") },
          available: availability.status !== "unavailable",
          rank: 0,
        })
      }
    }

    const { allowed, denied, warnings } = await CapabilityPolicyEngine.evaluate(requirement, candidates)

    if (allowed.length === 0 && denied.length > 0) {
      return {
        id: generateId("resolution"),
        requirement,
        candidates,
        selectedCandidate: null,
        status: "unresolved",
        reasoning: `All ${denied.length} candidates denied by policy. ${warnings.length} warnings.`,
      }
    }

    const ranked = await CapabilityRankingEngine.rankCandidates(allowed)
    const best = await CapabilityRankingEngine.selectBest(allowed)

    const status: ResolutionStatus = best
      ? "resolved"
      : allowed.length > 0
        ? "partial"
        : "unresolved"

    return {
      id: generateId("resolution"),
      requirement,
      candidates,
      selectedCandidate: best,
      status,
      reasoning: buildReasoning(best, ranked.length, denied.length, warnings.length),
    }
  },
}

function buildReasoning(
  best: CapabilityCandidate | null,
  allowedCount: number,
  deniedCount: number,
  warningCount: number,
): string {
  if (!best) {
    return `No suitable candidate found. ${allowedCount} allowed, ${deniedCount} denied by policy, ${warningCount} warnings.`
  }
  return `Selected ${best.worker.name} (${best.match.precision} match, ${(best.score.totalScore * 100).toFixed(0)}% score). ${allowedCount} candidates evaluated, ${deniedCount} filtered by policy.`
}
