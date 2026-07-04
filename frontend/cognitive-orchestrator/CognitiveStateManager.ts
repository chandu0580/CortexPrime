import type { CognitiveTransition, CognitiveSnapshot, CognitiveSession, CognitiveStage, CognitiveStatus, CognitiveContext, CognitiveStageDef } from "./types"
import { generateId } from "@/worker-framework/shared"
import { CognitiveSessionManager } from "./CognitiveSessionManager"

const transitions = new Map<string, CognitiveTransition>()
const snapshots = new Map<string, CognitiveSnapshot>()

const TRANSITION_RULES: Record<CognitiveStatus, CognitiveStatus[]> = {
  pending: ["active"],
  active: ["paused", "completed", "failed"],
  paused: ["active", "failed"],
  completed: [],
  failed: [],
  rolled_back: ["pending", "active"],
}

export const CognitiveStateManager = {
  async transition(
    sessionId: string,
    fromStage: CognitiveStage,
    toStage: CognitiveStage,
    fromStatus: CognitiveStatus,
    toStatus: CognitiveStatus,
    reason: string,
  ): Promise<CognitiveTransition> {
    const allowed = TRANSITION_RULES[fromStatus]
    if (!allowed.includes(toStatus)) {
      throw new Error(`Invalid status transition: ${fromStatus} -> ${toStatus}`)
    }

    const now = new Date().toISOString()
    const transition: CognitiveTransition = {
      id: generateId("cog-transition"),
      sessionId,
      fromStage,
      toStage,
      fromStatus,
      toStatus,
      reason,
      timestamp: now,
      durationMs: 0,
    }
    transitions.set(transition.id, transition)
    return transition
  },

  async rollback(sessionId: string, targetStage: CognitiveStage): Promise<CognitiveSession> {
    const session = await CognitiveSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session ${sessionId} not found`)

    const transition = await this.transition(sessionId, session.currentStage, targetStage, session.status, "rolled_back", `Rollback to ${targetStage}`)
    transition.durationMs = Date.now() - new Date(transition.timestamp).getTime()

    const targetIndex = session.stages.findIndex((s) => s.name === targetStage)
    const rolledStages: CognitiveStageDef[] = session.stages.map((s, i) => {
      if (i >= targetIndex) {
        return { ...s, status: "pending" as CognitiveStatus, startedAt: null, completedAt: null, durationMs: null, error: null, retryCount: 0 }
      }
      return s
    })

    await CognitiveSessionManager.updateSession(sessionId, {
      status: "active",
      currentStage: targetStage,
      stages: rolledStages,
    })
    return CognitiveSessionManager.getSession(sessionId) as Promise<CognitiveSession>
  },

  async snapshot(sessionId: string, context: CognitiveContext | null): Promise<CognitiveSnapshot> {
    const session = await CognitiveSessionManager.getSession(sessionId)
    if (!session) throw new Error(`Session ${sessionId} not found`)

    const snapshot: CognitiveSnapshot = {
      id: generateId("cog-snapshot"),
      sessionId,
      context: context ? { ...context } : null,
      stages: session.stages.map((s) => ({ ...s })),
      status: session.status,
      capturedAt: new Date().toISOString(),
    }
    snapshots.set(snapshot.id, snapshot)
    return snapshot
  },

  async restore(snapshotId: string): Promise<CognitiveSession> {
    const snapshot = snapshots.get(snapshotId)
    if (!snapshot) throw new Error(`Snapshot ${snapshotId} not found`)

    await CognitiveSessionManager.updateSession(snapshot.sessionId, {
      stages: snapshot.stages.map((s) => ({ ...s })),
      status: snapshot.status,
    })
    return CognitiveSessionManager.getSession(snapshot.sessionId) as Promise<CognitiveSession>
  },

  async getTransitions(sessionId: string): Promise<CognitiveTransition[]> {
    return Array.from(transitions.values()).filter((t) => t.sessionId === sessionId)
  },

  async getSnapshots(sessionId: string): Promise<CognitiveSnapshot[]> {
    return Array.from(snapshots.values()).filter((s) => s.sessionId === sessionId)
  },

  async getTransitionCount(sessionId: string): Promise<number> {
    return Array.from(transitions.values()).filter((t) => t.sessionId === sessionId).length
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
