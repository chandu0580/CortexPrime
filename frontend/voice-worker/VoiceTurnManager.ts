import type { VoiceTurn, VoiceInput, VoiceOutput, VoiceActivity } from "./types"
import { generateId } from "@/worker-framework/shared"

const turns = new Map<string, VoiceTurn>()

export const VoiceTurnManager = {
  async createTurn(sessionId: string, turnNumber: number, input: VoiceInput): Promise<VoiceTurn> {
    const turn: VoiceTurn = {
      id: generateId("voice-turn"),
      sessionId,
      turnNumber,
      input: { ...input },
      output: null,
      state: "processing",
      startedAt: new Date().toISOString(),
      completedAt: null,
      durationMs: null,
      activities: [],
      interrupted: false,
    }
    turns.set(turn.id, turn)
    return turn
  },

  async completeTurn(turnId: string, output: VoiceOutput): Promise<VoiceTurn> {
    const turn = turns.get(turnId)
    if (!turn) {
      throw new Error(`Voice turn ${turnId} not found`)
    }
    const now = new Date().toISOString()
    const start = new Date(turn.startedAt).getTime()
    turn.output = { ...output }
    turn.state = "idle"
    turn.completedAt = now
    turn.durationMs = Date.now() - start
    return turn
  },

  async interruptTurn(turnId: string, reason: string): Promise<VoiceTurn> {
    const turn = turns.get(turnId)
    if (!turn) {
      throw new Error(`Voice turn ${turnId} not found`)
    }
    turn.interrupted = true
    turn.interruptionReason = reason
    turn.state = "idle"
    turn.completedAt = new Date().toISOString()
    turn.durationMs = Date.now() - new Date(turn.startedAt).getTime()
    return turn
  },

  async getTurn(turnId: string): Promise<VoiceTurn | null> {
    return turns.get(turnId) ?? null
  },

  async getTurnsBySession(sessionId: string): Promise<VoiceTurn[]> {
    return Array.from(turns.values())
      .filter((t) => t.sessionId === sessionId)
      .sort((a, b) => a.turnNumber - b.turnNumber)
  },

  async addActivity(turnId: string, activity: VoiceActivity): Promise<void> {
    const turn = turns.get(turnId)
    if (!turn) {
      throw new Error(`Voice turn ${turnId} not found`)
    }
    turn.activities.push(activity)
  },

  async transitionState(turnId: string, state: VoiceTurn["state"]): Promise<void> {
    const turn = turns.get(turnId)
    if (!turn) {
      throw new Error(`Voice turn ${turnId} not found`)
    }
    turn.state = state
  },

  async getLatestTurn(sessionId: string): Promise<VoiceTurn | null> {
    const sessionTurns = await this.getTurnsBySession(sessionId)
    return sessionTurns.length > 0 ? sessionTurns[sessionTurns.length - 1] : null
  },

  async getInterruptedTurns(sessionId: string): Promise<VoiceTurn[]> {
    return Array.from(turns.values())
      .filter((t) => t.sessionId === sessionId && t.interrupted)
      .sort((a, b) => a.turnNumber - b.turnNumber)
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, turn] of turns.entries()) {
      if (turn.sessionId === sessionId) {
        turns.delete(id)
      }
    }
  },
}
