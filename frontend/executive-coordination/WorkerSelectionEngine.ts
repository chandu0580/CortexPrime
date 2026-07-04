import type { WorkerCandidate, WorkerSelection } from "./types"
import { generateId } from "./shared"

const selections = new Map<string, WorkerSelection>()

export const WorkerSelectionEngine = {
  async discoverWorkers(): Promise<WorkerCandidate[]> {
    return []
  },

  async rankWorkers(candidates: WorkerCandidate[]): Promise<WorkerCandidate[]> {
    return [...candidates].sort((a, b) => {
      if (a.available !== b.available) return a.available ? -1 : 1
      if (b.score !== a.score) return b.score - a.score
      return a.load - b.load
    })
  },

  async scoreWorkers(candidates: WorkerCandidate[], requiredCapabilities: string[]): Promise<WorkerCandidate[]> {
    return candidates.map((worker) => {
      let score = 0
      const capabilityMatch = requiredCapabilities.filter((c) => worker.capabilities.includes(c)).length
      score += capabilityMatch * 30
      if (worker.available) score += 25
      score += Math.max(0, 25 - worker.load * 5)
      score += worker.lastHeartbeat ? 10 : 0
      return { ...worker, score }
    })
  },

  async chooseWorker(candidates: WorkerCandidate[], requiredCapabilities: string[]): Promise<{ selection: WorkerSelection; worker: WorkerCandidate | null }> {
    const scored = await WorkerSelectionEngine.scoreWorkers(candidates, requiredCapabilities)
    const ranked = await WorkerSelectionEngine.rankWorkers(scored)

    if (ranked.length === 0 || !ranked[0].available) {
      return { selection: null as unknown as WorkerSelection, worker: null }
    }

    const chosen = ranked[0]
    const selection: WorkerSelection = {
      id: generateId("ws"),
      sessionId: "",
      taskId: "",
      workerId: chosen.workerId,
      score: chosen.score,
      reason: `Worker "${chosen.name}" selected with score ${chosen.score} (capabilities: ${capabilityMatches(chosen.capabilities, requiredCapabilities)}, available: ${chosen.available})`,
      selectedAt: new Date().toISOString(),
    }
    selections.set(selection.id, selection)
    return { selection, worker: chosen }
  },

  async explainSelection(selectionId: string): Promise<string> {
    const sel = selections.get(selectionId)
    if (!sel) throw new Error(`Selection not found: ${selectionId}`)
    return `Worker ${sel.workerId} selected for task ${sel.taskId}: ${sel.reason}`
  },

  async getSelections(sessionId?: string): Promise<WorkerSelection[]> {
    let result = Array.from(selections.values())
    if (sessionId) result = result.filter((s) => s.sessionId === sessionId)
    return result.sort((a, b) => new Date(b.selectedAt).getTime() - new Date(a.selectedAt).getTime())
  },
}

function capabilityMatches(available: string[], required: string[]): string {
  const matched = required.filter((r) => available.includes(r))
  return matched.length > 0 ? matched.join(", ") : "none"
}
