import type { StateMetrics } from "./types"

const systemMetrics = new Map<string, {
  totalEntries: number
  activeEntries: number
  archivedEntries: number
  deletedEntries: number
  totalTransitions: number
  totalSnapshots: number
  totalSynchronizations: number
  totalValidations: number
  totalConflicts: number
  totalResolutions: number
  registeredTypes: number
  transitionDurations: number[]
  syncDurations: number[]
  staleEntries: number
  startedAt: string
}>()

export const StateMetricsCollector = {
  async initialize(systemId: string): Promise<void> {
    if (systemMetrics.has(systemId)) return
    systemMetrics.set(systemId, {
      totalEntries: 0, activeEntries: 0, archivedEntries: 0, deletedEntries: 0,
      totalTransitions: 0, totalSnapshots: 0, totalSynchronizations: 0,
      totalValidations: 0, totalConflicts: 0, totalResolutions: 0,
      registeredTypes: 0, transitionDurations: [], syncDurations: [],
      staleEntries: 0, startedAt: new Date().toISOString(),
    })
  },

  async recordEntry(systemId: string, status: string): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (!m) return
    m.totalEntries++
    if (status === "active") m.activeEntries++
    else if (status === "archived") m.archivedEntries++
    else if (status === "deleted") m.deletedEntries++
  },

  async recordTransition(systemId: string, durationMs: number): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) {
      m.totalTransitions++
      m.transitionDurations.push(durationMs)
    }
  },

  async recordSnapshot(systemId: string): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.totalSnapshots++
  },

  async recordSynchronization(systemId: string, durationMs: number): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) {
      m.totalSynchronizations++
      m.syncDurations.push(durationMs)
    }
  },

  async recordValidation(systemId: string): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.totalValidations++
  },

  async recordConflict(systemId: string, count: number = 1): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.totalConflicts += count
  },

  async recordResolution(systemId: string, count: number = 1): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.totalResolutions += count
  },

  async setRegisteredTypes(systemId: string, count: number): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.registeredTypes = count
  },

  async setStaleEntries(systemId: string, count: number): Promise<void> {
    const m = systemMetrics.get(systemId)
    if (m) m.staleEntries = count
  },

  async collect(systemId: string, consistencyScore: number): Promise<StateMetrics> {
    const m = systemMetrics.get(systemId)
    if (!m) {
      return {
        systemId, totalEntries: 0, activeEntries: 0, archivedEntries: 0, deletedEntries: 0,
        totalTransitions: 0, totalSnapshots: 0, totalSynchronizations: 0, totalValidations: 0,
        totalConflicts: 0, totalResolutions: 0, registeredTypes: 0, consistencyScore: 100,
        avgTransitionDurationMs: 0, avgSyncDurationMs: 0, staleEntries: 0,
        collectedAt: new Date().toISOString(),
      }
    }

    const avgTransition = m.transitionDurations.length > 0
      ? Math.round(m.transitionDurations.reduce((a, b) => a + b, 0) / m.transitionDurations.length) : 0
    const avgSync = m.syncDurations.length > 0
      ? Math.round(m.syncDurations.reduce((a, b) => a + b, 0) / m.syncDurations.length) : 0

    return {
      systemId,
      totalEntries: m.totalEntries, activeEntries: m.activeEntries,
      archivedEntries: m.archivedEntries, deletedEntries: m.deletedEntries,
      totalTransitions: m.totalTransitions, totalSnapshots: m.totalSnapshots,
      totalSynchronizations: m.totalSynchronizations, totalValidations: m.totalValidations,
      totalConflicts: m.totalConflicts, totalResolutions: m.totalResolutions,
      registeredTypes: m.registeredTypes, consistencyScore,
      avgTransitionDurationMs: avgTransition, avgSyncDurationMs: avgSync,
      staleEntries: m.staleEntries,
      collectedAt: new Date().toISOString(),
    }
  },

  async reset(systemId: string): Promise<void> {
    systemMetrics.delete(systemId)
  },
}
