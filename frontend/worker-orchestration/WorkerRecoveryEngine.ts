import type { WorkerRecovery, WorkerSnapshot } from "./types"
import { generateId } from "@/worker-framework/shared"
import { WorkerSessionManager } from "./WorkerSessionManager"
import { WorkerCoordinator } from "./WorkerCoordinator"
import { WorkerAssignmentEngine } from "./WorkerAssignmentEngine"

const recoveries = new Map<string, WorkerRecovery>()
const snapshots = new Map<string, WorkerSnapshot>()

export const WorkerRecoveryEngine = {
  async captureSnapshot(sessionId: string): Promise<WorkerSnapshot> {
    const session = await WorkerSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session ${sessionId} not found`)

    const executions = await WorkerCoordinator.getExecutionsBySession(sessionId)
    const assignments = await WorkerAssignmentEngine.getAssignmentsBySession(sessionId)

    const snapshot: WorkerSnapshot = {
      id: generateId("wo-snapshot"),
      sessionId,
      executions: [...executions],
      assignments: [...assignments],
      groups: [],
      status: session.status,
      capturedAt: new Date().toISOString(),
    }
    snapshots.set(snapshot.id, snapshot)
    return snapshot
  },

  async getSnapshot(snapshotId: string): Promise<WorkerSnapshot | null> {
    return snapshots.get(snapshotId) ?? null
  },

  async restoreSnapshot(snapshotId: string): Promise<void> {
    const snapshot = snapshots.get(snapshotId)
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`)

    for (const exec of snapshot.executions) {
      await WorkerCoordinator.updateExecution(exec.id, { status: exec.status, lifecycleState: exec.lifecycleState })
    }
    await WorkerSessionManager.updateSession(snapshot.sessionId, { status: snapshot.status })
  },

  async recordRecovery(
    sessionId: string, workerId: string, failureType: string,
    error: string, maxRetries: number,
  ): Promise<WorkerRecovery> {
    const recovery: WorkerRecovery = {
      id: generateId("wo-recovery"),
      sessionId,
      workerId,
      failureType,
      error,
      retryCount: 0,
      maxRetries,
      recovered: false,
      strategy: "retry",
      createdAt: new Date().toISOString(),
      recoveredAt: null,
    }
    recoveries.set(recovery.id, recovery)
    return recovery
  },

  async attemptRecovery(recoveryId: string): Promise<boolean> {
    const recovery = recoveries.get(recoveryId)
    if (!recovery) throw new Error(`Recovery ${recoveryId} not found`)

    if (recovery.recovered) return true
    if (recovery.retryCount >= recovery.maxRetries) return false

    recovery.retryCount++

    if (recovery.retryCount >= recovery.maxRetries) {
      if (recovery.strategy === "retry") {
        recovery.strategy = "restart"
      } else if (recovery.strategy === "restart") {
        recovery.strategy = "reassign"
      } else if (recovery.strategy === "reassign") {
        recovery.strategy = "rollback"
      }
    }

    const recovered = recovery.retryCount < recovery.maxRetries || recovery.strategy === "restart"
    if (recovered) {
      recovery.recovered = true
      recovery.recoveredAt = new Date().toISOString()
    }
    return recovered
  },

  async getRecovery(recoveryId: string): Promise<WorkerRecovery | null> {
    return recoveries.get(recoveryId) ?? null
  },

  async getRecoveriesBySession(sessionId: string): Promise<WorkerRecovery[]> {
    return Array.from(recoveries.values()).filter((r) => r.sessionId === sessionId)
  },

  async countFailed(): Promise<number> {
    return Array.from(recoveries.values()).filter((r) => !r.recovered).length
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, r] of recoveries.entries()) {
      if (r.sessionId === sessionId) recoveries.delete(id)
    }
  },
}
