import type { ExecutionTransition, ExecutionSnapshot, ExecutionStage, ExecutionState, ExecutionProgress } from "./types"
import { generateId } from "@/worker-framework/shared"
import { ExecutionSessionManager } from "./ExecutionSessionManager"
import { MissionDecompositionEngine } from "./MissionDecompositionEngine"

const transitions = new Map<string, ExecutionTransition>()
const snapshots = new Map<string, ExecutionSnapshot>()

const TRANSITION_RULES: Record<ExecutionState, ExecutionState[]> = {
  pending: ["planning", "failed"],
  planning: ["distributing", "paused", "failed", "completed"],
  distributing: ["executing", "paused", "failed"],
  executing: ["paused", "completed", "failed"],
  paused: ["planning", "distributing", "executing", "failed"],
  completed: [],
  failed: [],
  rolled_back: ["pending", "planning"],
}

export const ExecutionStateManager = {
  async transition(
    sessionId: string,
    fromStage: ExecutionStage,
    toStage: ExecutionStage,
    fromState: ExecutionState,
    toState: ExecutionState,
    reason: string,
  ): Promise<ExecutionTransition> {
    const allowed = TRANSITION_RULES[fromState]
    if (!allowed.includes(toState)) {
      throw new Error(`Invalid state transition: ${fromState} -> ${toState}`)
    }

    const transition: ExecutionTransition = {
      id: generateId("exec-transition"),
      sessionId,
      fromStage,
      toStage,
      fromState,
      toState,
      reason,
      timestamp: new Date().toISOString(),
    }
    transitions.set(transition.id, transition)
    return transition
  },

  async rollback(sessionId: string, targetStage: ExecutionStage): Promise<void> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session ${sessionId} not found`)

    await this.transition(sessionId, session.currentStage, targetStage, session.status, "rolled_back", `Rollback to ${targetStage}`)
    await ExecutionSessionManager.updateSession(sessionId, { status: "pending", currentStage: targetStage })
  },

  async snapshot(sessionId: string): Promise<ExecutionSnapshot> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session ${sessionId} not found`)

    const plan = session.planId ? await MissionDecompositionEngine.getPlan(session.planId) : null
    const progress = await this.calculateProgress(sessionId)

    const snapshot: ExecutionSnapshot = {
      id: generateId("exec-snapshot"),
      sessionId,
      plan: plan ? { ...plan } : null,
      phases: plan?.phases.map((p) => ({ ...p })) ?? [],
      status: session.status,
      progress,
      capturedAt: new Date().toISOString(),
    }
    snapshots.set(snapshot.id, snapshot)
    return snapshot
  },

  async restore(snapshotId: string): Promise<void> {
    const snapshot = snapshots.get(snapshotId)
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`)
    await ExecutionSessionManager.updateSession(snapshot.sessionId, {
      status: snapshot.status,
    })
  },

  async calculateProgress(sessionId: string): Promise<ExecutionProgress | null> {
    const session = await ExecutionSessionManager.getSession(sessionId)
    if (!session) return null

    const plan = session.planId ? await MissionDecompositionEngine.getPlan(session.planId) : null
    if (!plan) return null

    const phases = plan.phases
    const totalEstimatedMs = phases.length * 60000

    const totalTasks = plan.totalTasks
    const completedTasks = 0
    const failedTasks = 0
    const inProgressTasks = 0

    const percentComplete = totalTasks > 0 ? Math.round((completedTasks / totalTasks) * 100) : 0
    const estimatedRemainingMs = Math.round(totalEstimatedMs * (1 - percentComplete / 100))

    return {
      totalTasks,
      completedTasks,
      failedTasks,
      inProgressTasks,
      pendingTasks: totalTasks - completedTasks - failedTasks - inProgressTasks,
      percentComplete,
      estimatedRemainingMs,
    }
  },

  async getTransitions(sessionId: string): Promise<ExecutionTransition[]> {
    return Array.from(transitions.values()).filter((t) => t.sessionId === sessionId)
  },

  async getSnapshots(sessionId: string): Promise<ExecutionSnapshot[]> {
    return Array.from(snapshots.values()).filter((s) => s.sessionId === sessionId)
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, t] of transitions.entries()) {
      if (t.sessionId === sessionId) transitions.delete(id)
    }
    for (const [id, s] of snapshots.entries()) {
      if (s.sessionId === sessionId) snapshots.delete(id)
    }
  },
}
