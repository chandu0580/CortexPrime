import type { StateSnapshot, StateDiff } from "./types"
import { WorldStateManager } from "./WorldStateManager"

const snapshots = new Map<string, StateSnapshot>()
const MAX_SNAPSHOTS = 50

export const StateSnapshotManager = {
  async createSnapshot(label: string, metadata?: Record<string, string>): Promise<StateSnapshot> {
    const state = await WorldStateManager.getState()
    if (!state) throw new Error("World state not initialized.")

    const snapshot: StateSnapshot = {
      id: `snapshot-${Date.now()}`,
      label,
      entries: await WorldStateManager.getSnapshotData(),
      entryKeys: Object.keys(state.entries),
      metadata: metadata ?? {},
      capturedAt: new Date().toISOString(),
      version: state.version,
    }

    if (snapshots.size >= MAX_SNAPSHOTS) {
      const oldest = Array.from(snapshots.entries())
        .sort(([, a], [, b]) => new Date(a.capturedAt).getTime() - new Date(b.capturedAt).getTime())[0]
      snapshots.delete(oldest[0])
    }

    snapshots.set(snapshot.id, snapshot)
    return { ...snapshot }
  },

  async restoreSnapshot(snapshotId: string): Promise<void> {
    const snapshot = snapshots.get(snapshotId)
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found.`)
    await WorldStateManager.restoreFromData(snapshot.entries)
  },

  async compareSnapshots(snapshotId1: string, snapshotId2: string): Promise<StateDiff[]> {
    const s1 = snapshots.get(snapshotId1)
    const s2 = snapshots.get(snapshotId2)
    if (!s1) throw new Error(`Snapshot ${snapshotId1} not found.`)
    if (!s2) throw new Error(`Snapshot ${snapshotId2} not found.`)

    const diffs: StateDiff[] = []
    const allKeys = new Set([...s1.entryKeys, ...s2.entryKeys])

    for (const key of allKeys) {
      const v1 = s1.entries[key]
      const v2 = s2.entries[key]
      if (JSON.stringify(v1) !== JSON.stringify(v2)) {
        diffs.push({ entryKey: key, from: v1 ?? null, to: v2 ?? null, changed: true })
      }
    }

    return diffs
  },

  async listSnapshots(): Promise<StateSnapshot[]> {
    return Array.from(snapshots.values())
      .sort((a, b) => new Date(b.capturedAt).getTime() - new Date(a.capturedAt).getTime())
      .map((s) => ({ ...s }))
  },

  async getSnapshot(snapshotId: string): Promise<StateSnapshot | null> {
    const snapshot = snapshots.get(snapshotId)
    return snapshot ? { ...snapshot } : null
  },

  async count(): Promise<number> {
    return snapshots.size
  },

  async clear(): Promise<void> {
    snapshots.clear()
  },
}
