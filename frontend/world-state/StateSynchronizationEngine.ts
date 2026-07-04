import type { StateSynchronization, StateSynchronizationStrategy, StateScope, StateConflict, StateResolution } from "./types"
import { WorldStateManager } from "./WorldStateManager"
import { StateValidationEngine } from "./StateValidationEngine"
import { generateId } from "@/worker-framework/shared"

const syncHistory: StateSynchronization[] = []
const resolutions: StateResolution[] = []

export const StateSynchronizationEngine = {
  async synchronize(
    strategy: StateSynchronizationStrategy = "full",
    sourceScope?: StateScope,
    targetScope?: StateScope,
  ): Promise<StateSynchronization> {
    const startTime = Date.now()
    const entries = await WorldStateManager.getAllEntries()
    const conflicts = await StateValidationEngine.detectConflicts()

    let entriesToSync = entries
    if (sourceScope) entriesToSync = entries.filter((e) => e.scope === sourceScope)

    let resolvedCount = 0
    for (const conflict of conflicts) {
      const resolution = await this.autoResolveConflict(conflict)
      if (resolution) resolvedCount++
    }

    const sync: StateSynchronization = {
      id: generateId("state-sync"),
      strategy,
      sourceScope: sourceScope ?? "global",
      targetScope: targetScope ?? "global",
      entriesSynchronized: entriesToSync.length,
      conflictsDetected: conflicts.length,
      conflictsResolved: resolvedCount,
      durationMs: Date.now() - startTime,
      timestamp: new Date().toISOString(),
    }

    if (syncHistory.length >= 100) syncHistory.shift()
    syncHistory.push(sync)

    return { ...sync }
  },

  async merge(sourceScope: StateScope): Promise<number> {
    const sourceEntries = await WorldStateManager.queryByScope(sourceScope)
    let mergedCount = 0

    for (const entry of sourceEntries) {
      const existing = await WorldStateManager.getEntry(entry.key)
      if (!existing || existing.version < entry.version) {
        await WorldStateManager.updateState(entry.key, entry.value, {
          mergedFrom: sourceScope,
          originalDomain: entry.domain,
        })
        mergedCount++
      }
    }

    return mergedCount
  },

  async reconcile(): Promise<{ reconciled: number; remainingConflicts: number }> {
    const conflicts = await StateValidationEngine.detectConflicts()
    let reconciled = 0

    for (const conflict of conflicts) {
      const resolution = await this.autoResolveConflict(conflict)
      if (resolution) reconciled++
    }

    return { reconciled, remainingConflicts: conflicts.length - reconciled }
  },

  async autoResolveConflict(conflict: StateConflict): Promise<StateResolution | null> {
    if (conflict.conflictingValues.length < 2) return null

    const sorted = [...conflict.conflictingValues].sort(
      (a, b) => (b.version as number) - (a.version as number),
    )

    const resolvedValue = sorted[0].value
    const resolution: StateResolution = {
      id: generateId("state-resolution"),
      conflictId: conflict.id,
      entryKey: conflict.entryKey,
      resolution: `Auto-resolved by selecting highest version (v${sorted[0].version})`,
      resolvedValue,
      resolvedBy: "system",
      resolvedAt: new Date().toISOString(),
    }

    await WorldStateManager.updateState(conflict.entryKey, resolvedValue, {
      resolvedConflict: conflict.id,
      resolutionStrategy: "highest_version",
    })

    resolutions.push(resolution)
    return resolution
  },

  async resolveConflict(
    conflictId: string,
    resolvedValue: unknown,
    resolvedBy: string,
    resolution: string,
  ): Promise<StateResolution> {
    const conflicts = await StateValidationEngine.detectConflicts()
    const conflict = conflicts.find((c) => c.id === conflictId)
    if (!conflict) throw new Error(`Conflict ${conflictId} not found.`)

    const stateResolution: StateResolution = {
      id: generateId("state-resolution"),
      conflictId,
      entryKey: conflict.entryKey,
      resolution,
      resolvedValue,
      resolvedBy,
      resolvedAt: new Date().toISOString(),
    }

    await WorldStateManager.updateState(conflict.entryKey, resolvedValue, {
      resolvedConflict: conflictId,
      resolutionStrategy: "manual",
      resolvedBy,
    })

    resolutions.push(stateResolution)
    return stateResolution
  },

  async getSyncHistory(): Promise<StateSynchronization[]> {
    return [...syncHistory].reverse().map((s) => ({ ...s }))
  },

  async getResolutions(): Promise<StateResolution[]> {
    return [...resolutions].map((r) => ({ ...r }))
  },

  async countSyncs(): Promise<number> {
    return syncHistory.length
  },

  async countResolutions(): Promise<number> {
    return resolutions.length
  },

  async clear(): Promise<void> {
    syncHistory.length = 0
    resolutions.length = 0
  },
}
