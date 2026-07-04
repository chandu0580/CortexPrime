import type { CapabilityCandidate } from "./types"

export const CapabilityRankingEngine = {
  async rankCandidates(candidates: CapabilityCandidate[]): Promise<CapabilityCandidate[]> {
    const sorted = [...candidates].sort((a, b) => {
      const scoreDiff = b.score.totalScore - a.score.totalScore
      if (scoreDiff !== 0) return scoreDiff

      const availDiff = (a.available ? 1 : 0) - (b.available ? 1 : 0)
      if (availDiff !== 0) return availDiff

      const matchDiff = b.score.matchScore - a.score.matchScore
      if (matchDiff !== 0) return matchDiff

      const healthDiff = b.score.healthScore - a.score.healthScore
      if (healthDiff !== 0) return healthDiff

      return a.worker.name.localeCompare(b.worker.name)
    })

    return sorted.map((c, i) => ({ ...c, rank: i + 1 }))
  },

  async selectBest(candidates: CapabilityCandidate[]): Promise<CapabilityCandidate | null> {
    const ranked = await CapabilityRankingEngine.rankCandidates(candidates)
    return ranked.length > 0 && ranked[0].available ? ranked[0] : null
  },
}
