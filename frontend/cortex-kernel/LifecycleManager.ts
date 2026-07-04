import type { MissionSession, KernelLifecycle, MissionState } from "./types"
import { generateId } from "./shared"

const lifecycleEvents: KernelLifecycle[] = []

export const LifecycleManager = {
  async recordEvent(
    event: string,
    description: string,
    sessionId: string | null = null,
    metadata: Record<string, string> | null = null,
  ): Promise<KernelLifecycle> {
    const entry: KernelLifecycle = {
      id: generateId("lifecycle"),
      event,
      description,
      timestamp: new Date().toISOString(),
      sessionId,
      metadata,
    }
    lifecycleEvents.push(entry)
    return entry
  },

  async getSessionLifecycle(sessionId: string): Promise<KernelLifecycle[]> {
    return lifecycleEvents.filter((e) => e.sessionId === sessionId)
  },

  async getAllLifecycleEvents(): Promise<KernelLifecycle[]> {
    return [...lifecycleEvents]
  },

  async getLifecycleCount(): Promise<number> {
    return lifecycleEvents.length
  },

  async initializeSession(session: MissionSession): Promise<KernelLifecycle> {
    return LifecycleManager.recordEvent(
      "session.created",
      `Mission session ${session.id} created with state: ${session.state}`,
      session.id,
      { state: session.state, pipelineStage: session.pipelineStage },
    )
  },

  async transitionSession(session: MissionSession, fromState: MissionState, toState: MissionState): Promise<KernelLifecycle> {
    return LifecycleManager.recordEvent(
      "session.transition",
      `Session ${session.id} transitioned: ${fromState} → ${toState}`,
      session.id,
      { from: fromState, to: toState },
    )
  },

  async closeSession(session: MissionSession, finalState: MissionState): Promise<KernelLifecycle> {
    return LifecycleManager.recordEvent(
      "session.closed",
      `Mission session ${session.id} closed with state: ${finalState}`,
      session.id,
      { state: finalState, duration: session.completedAt ? `${(new Date(session.completedAt).getTime() - new Date(session.createdAt).getTime())}ms` : "unknown" },
    )
  },
}
