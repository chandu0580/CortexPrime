import { VoiceSessionManager } from "./VoiceSessionManager"
import { LiveKitManager } from "./LiveKitManager"
import { DeepgramManager } from "./DeepgramManager"
import { ElevenLabsManager } from "./ElevenLabsManager"

export type VoiceHealthStatus = "healthy" | "degraded" | "unhealthy" | "unknown"

export interface VoiceHealthReport {
  workerId: string
  status: VoiceHealthStatus
  sessionCount: number
  erroredSessions: number
  activeTurns: number
  lastActivityAt: string | null
  message: string
  timestamp: string
  livekitConnected: boolean
  deepgramConnected: boolean
  elevenlabsConnected: boolean
  activeStreams: number
  recoveryReady: boolean
}

const healthStates = new Map<string, {
  lastActivityAt: string | null
  consecutiveFailures: number
  errorCount: number
  lastRecoveryAttempt: string | null
}>()

export const VoiceHealthManager = {
  async initialize(workerId: string): Promise<void> {
    if (healthStates.has(workerId)) return
    healthStates.set(workerId, {
      lastActivityAt: null,
      consecutiveFailures: 0,
      errorCount: 0,
      lastRecoveryAttempt: null,
    })
  },

  async recordActivity(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.lastActivityAt = new Date().toISOString()
      state.consecutiveFailures = 0
    }
  },

  async recordError(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.consecutiveFailures++
      state.errorCount++
    }
  },

  async recordRecoveryAttempt(workerId: string): Promise<void> {
    const state = healthStates.get(workerId)
    if (state) {
      state.lastRecoveryAttempt = new Date().toISOString()
    }
  },

  async check(workerId: string): Promise<VoiceHealthReport> {
    const state = healthStates.get(workerId)
    if (!state) {
      return {
        workerId,
        status: "unknown",
        sessionCount: 0,
        erroredSessions: 0,
        activeTurns: 0,
        lastActivityAt: null,
        message: "Health state not initialized",
        timestamp: new Date().toISOString(),
        livekitConnected: false,
        deepgramConnected: false,
        elevenlabsConnected: false,
        activeStreams: 0,
        recoveryReady: false,
      }
    }

    const sessions = await VoiceSessionManager.getActiveSessions()
    const erroredSessions = await this.countErroredSessions()
    const activeRooms = await LiveKitManager.getActiveRooms()
    const activeDeepgramSessions = await DeepgramManager.getActiveSessions()
    const activeElevenLabsSessions = await ElevenLabsManager.getActiveSessions()
    const activeStreams = await this.countActiveStreams()

    const livekitConnected = activeRooms.length > 0
    const deepgramConnected = activeDeepgramSessions.length > 0
    const elevenlabsConnected = activeElevenLabsSessions.length > 0

    let status: VoiceHealthStatus = "healthy"
    let message = "Voice worker is operating normally"

    if (state.consecutiveFailures >= 5) {
      status = "unhealthy"
      message = `Voice worker has ${state.consecutiveFailures} consecutive failures`
    } else if (state.consecutiveFailures >= 3) {
      status = "degraded"
      message = `Voice worker experiencing errors: ${state.consecutiveFailures} consecutive failures`
    } else if (erroredSessions > 0) {
      status = "degraded"
      message = `${erroredSessions} voice session(s) in error state`
    } else if (!livekitConnected && !deepgramConnected && !elevenlabsConnected && sessions.length > 0) {
      status = "degraded"
      message = "No external service connections active"
    }

    const recoveryReady = state.consecutiveFailures > 0 && state.consecutiveFailures < 5

    return {
      workerId,
      status,
      sessionCount: sessions.length,
      erroredSessions,
      activeTurns: sessions.reduce((sum, s) => sum + s.turnCount, 0),
      lastActivityAt: state.lastActivityAt,
      message,
      timestamp: new Date().toISOString(),
      livekitConnected,
      deepgramConnected,
      elevenlabsConnected,
      activeStreams,
      recoveryReady,
    }
  },

  async countErroredSessions(): Promise<number> {
    const sessions = await VoiceSessionManager.getActiveSessions()
    return sessions.filter((s) => s.state === "error").length
  },

  async countActiveStreams(): Promise<number> {
    const streams = await import("./VoiceStreamManager").then((m) => m.VoiceStreamManager.getActiveStreams())
    return streams.length
  },

  async getConsecutiveFailures(workerId: string): Promise<number> {
    return healthStates.get(workerId)?.consecutiveFailures ?? 0
  },

  async getErrorCount(workerId: string): Promise<number> {
    return healthStates.get(workerId)?.errorCount ?? 0
  },

  async reset(workerId: string): Promise<void> {
    healthStates.delete(workerId)
  },
}
