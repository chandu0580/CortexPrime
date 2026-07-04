import type { ExecutionWorker, WorkerCapability } from "@/runtime-core/types"
import type {
  CapabilityDescriptor,
  CapabilityRequirement,
  CapabilityCandidate,
  CapabilityScore,
  CapabilityAvailability,
  CapabilityRoutingReport,
  CapabilityResolution,
} from "./types"
import { CapabilityCatalog } from "./CapabilityCatalog"
import { CapabilityMatcher } from "./CapabilityMatcher"
import { CapabilityScoringEngine } from "./CapabilityScoringEngine"
import { CapabilityPolicyEngine } from "./CapabilityPolicyEngine"
import { CapabilityResolver } from "./CapabilityResolver"
import { CapabilityAvailabilityManager } from "./CapabilityAvailabilityManager"
import { CapabilityRankingEngine } from "./CapabilityRankingEngine"
import { generateId } from "./shared"

export const capabilityResolutionEngine = {
  async registerCapability(descriptor: Omit<CapabilityDescriptor, "id">): Promise<CapabilityDescriptor> {
    return CapabilityCatalog.registerCapability(descriptor)
  },

  async matchCapability(requirement: CapabilityRequirement, workers: ExecutionWorker[]): Promise<CapabilityCandidate[]> {
    const descriptors = await CapabilityCatalog.findCapabilities(requirement.requiredCapability)
    const candidates: CapabilityCandidate[] = []

    for (const descriptor of descriptors) {
      for (const worker of workers) {
        const match = await CapabilityMatcher.match(requirement, descriptor)
        const matchWithWorker = { ...match, workerId: worker.id }

        const score = await CapabilityScoringEngine.scoreCandidate(worker, matchWithWorker, requirement, descriptor.maxConcurrency)
        const availability = await CapabilityAvailabilityManager.checkAvailability(descriptor, worker)

        const candidate: CapabilityCandidate = {
          id: generateId("candidate"),
          worker,
          descriptor,
          match: matchWithWorker,
          score: { ...score, candidateId: generateId("score") },
          available: availability.status !== "unavailable",
          rank: 0,
        }

        candidates.push(candidate)
      }
    }

    return CapabilityRankingEngine.rankCandidates(candidates)
  },

  async scoreCandidates(candidates: CapabilityCandidate[]): Promise<CapabilityCandidate[]> {
    return CapabilityRankingEngine.rankCandidates(candidates)
  },

  async filterUnavailable(candidates: CapabilityCandidate[]): Promise<CapabilityCandidate[]> {
    return candidates.filter((c) => c.available)
  },

  async rankCandidates(candidates: CapabilityCandidate[]): Promise<CapabilityCandidate[]> {
    return CapabilityRankingEngine.rankCandidates(candidates)
  },

  async resolveBestWorker(requirement: CapabilityRequirement, workers: ExecutionWorker[]): Promise<CapabilityResolution> {
    const descriptors = await CapabilityCatalog.findCapabilities(requirement.requiredCapability)
    return CapabilityResolver.resolve(requirement, workers, descriptors)
  },

  async generateRoutingReport(requirement: CapabilityRequirement, workers: ExecutionWorker[]): Promise<CapabilityRoutingReport> {
    const descriptors = await CapabilityCatalog.findCapabilities(requirement.requiredCapability)
    const resolution = await CapabilityResolver.resolve(requirement, workers, descriptors)
    const ranked = await CapabilityRankingEngine.rankCandidates(resolution.candidates)

    const totalCandidates = ranked.length
    const totalAvailable = ranked.filter((c) => c.available).length
    const totalUnavailable = totalCandidates - totalAvailable

    return {
      id: generateId("report"),
      requirement,
      resolutions: [resolution],
      totalCandidates,
      totalAvailable,
      totalUnavailable,
      bestCandidate: resolution.selectedCandidate,
      summary: buildSummary(resolution, totalCandidates, totalAvailable),
      timestamp: new Date().toISOString(),
    }
  },
}

function buildSummary(resolution: CapabilityResolution, total: number, available: number): string {
  if (resolution.selectedCandidate) {
    const c = resolution.selectedCandidate
    return `Resolved: ${c.worker.name} (${c.match.precision} match, rank #${c.rank}). ${available}/${total} workers available. Score: ${(c.score.totalScore * 100).toFixed(0)}%.`
  }
  return `Unresolved: No suitable candidate. ${available}/${total} workers available. ${resolution.candidates.length} candidates evaluated.`
}
