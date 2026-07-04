import type { StateHealth, StateHealthStatus } from "./types"

const healthStates = new Map<string, {
  consistencyScore: number
  staleEntries: number
  orphanEntries: number
  invalidReferences: number
  conflictCount: number
  synchronizationBacklog: number
  consecutiveFailures: number
  lastCheckAt: string | null
}>()

export const StateHealthManager = {
  async initialize(systemId: string): Promise<void> {
    if (healthStates.has(systemId)) return
    healthStates.set(systemId, {
      consistencyScore: 100,
      staleEntries: 0,
      orphanEntries: 0,
      invalidReferences: 0,
      conflictCount: 0,
      synchronizationBacklog: 0,
      consecutiveFailures: 0,
      lastCheckAt: null,
    })
  },

  async recordIntegrity(systemId: string, data: {
    consistencyScore: number
    staleEntries: number
    orphanEntries: number
    invalidReferences: number
    conflictCount: number
    synchronizationBacklog: number
  }): Promise<void> {
    const state = healthStates.get(systemId)
    if (!state) return
    state.consistencyScore = data.consistencyScore
    state.staleEntries = data.staleEntries
    state.orphanEntries = data.orphanEntries
    state.invalidReferences = data.invalidReferences
    state.conflictCount = data.conflictCount
    state.synchronizationBacklog = data.synchronizationBacklog
    state.lastCheckAt = new Date().toISOString()
  },

  async recordFailure(systemId: string): Promise<void> {
    const state = healthStates.get(systemId)
    if (state) state.consecutiveFailures++
  },

  async recordSuccess(systemId: string): Promise<void> {
    const state = healthStates.get(systemId)
    if (state) state.consecutiveFailures = 0
  },

  async check(systemId: string): Promise<StateHealth> {
    const state = healthStates.get(systemId)
    if (!state) {
      return {
        systemId, status: "unknown", consistencyScore: 100, staleEntries: 0,
        orphanEntries: 0, invalidReferences: 0, conflictCount: 0,
        synchronizationBacklog: 0, recoveryReady: false,
        message: "Health state not initialized", timestamp: new Date().toISOString(),
      }
    }

    let status: StateHealthStatus = "healthy"
    let message = "World state system is operating normally"
    let recoveryReady = false

    if (state.consecutiveFailures >= 5) {
      status = "unhealthy"
      message = `${state.consecutiveFailures} consecutive failures detected`
      recoveryReady = true
    } else if (state.consecutiveFailures >= 3) {
      status = "degraded"
      message = `${state.consecutiveFailures} consecutive failures detected`
      recoveryReady = true
    }

    if (status !== "unhealthy") {
      if (state.consistencyScore < 70) {
        status = "degraded"
        message = `Consistency score ${state.consistencyScore}% is below threshold`
        recoveryReady = true
      } else if (state.conflictCount > 5) {
        status = "degraded"
        message = `${state.conflictCount} unresolved conflicts detected`
        recoveryReady = true
      } else if (state.invalidReferences > 10) {
        status = "degraded"
        message = `${state.invalidReferences} invalid references detected`
        recoveryReady = true
      } else if (state.synchronizationBacklog > 20) {
        status = "degraded"
        message = `Synchronization backlog of ${state.synchronizationBacklog} entries`
        recoveryReady = true
      } else if (state.staleEntries > 50) {
        status = "degraded"
        message = `${state.staleEntries} stale entries detected`
        recoveryReady = true
      }
    }

    return {
      systemId, status, consistencyScore: state.consistencyScore,
      staleEntries: state.staleEntries, orphanEntries: state.orphanEntries,
      invalidReferences: state.invalidReferences, conflictCount: state.conflictCount,
      synchronizationBacklog: state.synchronizationBacklog, recoveryReady,
      message, timestamp: new Date().toISOString(),
    }
  },

  async getConsecutiveFailures(systemId: string): Promise<number> {
    return healthStates.get(systemId)?.consecutiveFailures ?? 0
  },

  async reset(systemId: string): Promise<void> {
    healthStates.delete(systemId)
  },
}
