import type { StateValidation, StateConflict, StateEntry } from "./types"
import { WorldStateManager } from "./WorldStateManager"

export const StateValidationEngine = {
  async validate(): Promise<StateValidation> {
    const entries = await WorldStateManager.getAllEntries()
    const activeEntries = entries.filter((e) => e.status === "active")
    const expiredEntries = entries.filter((e) => {
      if (!e.expiresAt) return false
      return new Date(e.expiresAt).getTime() <= Date.now()
    })

    const conflicts = await this.detectConflicts()
    const missingReferences = await this.detectMissingState(activeEntries)
    const invalidReferences = await this.detectInvalidReferences(activeEntries)

    const totalChecked = activeEntries.length
    const totalIssues = conflicts.length + missingReferences.length + invalidReferences.length
    const consistencyScore = totalChecked > 0
      ? Math.round(((totalChecked - totalIssues) / totalChecked) * 100)
      : 100

    return {
      valid: totalIssues === 0,
      totalEntries: entries.length,
      activeEntries: activeEntries.length,
      conflicts,
      missingReferences,
      invalidReferences,
      expiredEntries: expiredEntries.length,
      consistencyScore,
      validatedAt: new Date().toISOString(),
    }
  },

  async detectConflicts(): Promise<StateConflict[]> {
    const entries = await WorldStateManager.getAllEntries()
    const conflicts: StateConflict[] = []
    const seen = new Map<string, StateEntry[]>()

    for (const entry of entries) {
      if (entry.status !== "active") continue
      const existing = seen.get(entry.key) ?? []
      existing.push(entry)
      seen.set(entry.key, existing)
    }

    for (const [, keyEntries] of seen) {
      if (keyEntries.length <= 1) continue
      if (keyEntries.every((e) => JSON.stringify(e.value) === JSON.stringify(keyEntries[0].value))) continue

      const values = keyEntries.map((e) => ({ version: e.version, value: e.value }))
      conflicts.push({
        id: `conflict-${keyEntries[0].key}-${Date.now()}`,
        entryKey: keyEntries[0].key,
        domain: keyEntries[0].domain,
        severity: "major",
        description: `Multiple versions of state entry '${keyEntries[0].key}' have conflicting values`,
        conflictingValues: values,
        detectedAt: new Date().toISOString(),
      })
    }

    return conflicts
  },

  async detectMissingState(activeEntries: StateEntry[]): Promise<string[]> {
    const missing: string[] = []
    for (const entry of activeEntries) {
      for (const ref of entry.references) {
        const exists = activeEntries.some((e) => e.key === ref.targetKey && e.domain === ref.targetDomain)
        if (!exists) {
          missing.push(`Referenced state '${ref.targetKey}' in domain '${ref.targetDomain}' not found (required by '${entry.key}')`)
        }
      }
    }
    return missing
  },

  async detectInvalidReferences(activeEntries: StateEntry[]): Promise<string[]> {
    const invalid: string[] = []
    const entryMap = new Map(activeEntries.map((e) => [`${e.domain}:${e.key}`, e]))

    for (const entry of activeEntries) {
      for (const ref of entry.references) {
        const target = entryMap.get(`${ref.targetDomain}:${ref.targetKey}`)
        if (target && target.status !== "active" && ref.required) {
          invalid.push(`Required reference '${ref.targetKey}' in domain '${ref.targetDomain}' has status '${target.status}'`)
        }
      }
    }

    return invalid
  },

  async detectStaleEntries(staleThresholdMs: number = 300_000): Promise<string[]> {
    const entries = await WorldStateManager.getAllEntries()
    const now = Date.now()
    return entries
      .filter((e) => e.status === "active" && (now - new Date(e.updatedAt).getTime()) > staleThresholdMs)
      .map((e) => e.key)
  },

  async detectOrphanEntries(): Promise<string[]> {
    const entries = await WorldStateManager.getAllEntries()
    const referencedKeys = new Set<string>()

    for (const entry of entries) {
      for (const ref of entry.references) {
        referencedKeys.add(ref.targetKey)
      }
    }

    return entries
      .filter((e) => e.status === "active" && !referencedKeys.has(e.key) && e.references.length === 0)
      .map((e) => e.key)
  },
}
