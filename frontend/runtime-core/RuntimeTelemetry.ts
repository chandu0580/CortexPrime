import type { RuntimeEvent, RuntimeMetrics } from "./types"
import { generateId } from "./shared"

const events: RuntimeEvent[] = []
const startedAt: string = new Date().toISOString()

export const RuntimeTelemetry = {
  async emitEvent(
    sessionId: string,
    type: string,
    name: string,
    details: string,
    metadata: Record<string, string> | null = null,
  ): Promise<RuntimeEvent> {
    const event: RuntimeEvent = {
      id: generateId("rtevent"),
      sessionId,
      type,
      name,
      details,
      timestamp: new Date().toISOString(),
      metadata,
    }
    events.push(event)
    return event
  },

  async getSessionEvents(sessionId: string): Promise<RuntimeEvent[]> {
    return events.filter((e) => e.sessionId === sessionId)
  },

  async getAllEvents(): Promise<RuntimeEvent[]> {
    return [...events]
  },

  async getEventCount(): Promise<number> {
    return events.length
  },

  async getMetrics(
    activeSessions: number,
    totalSessions: number,
    activeWorkers: number,
    idleWorkers: number,
    totalWorkers: number,
    tasksCompleted: number,
    tasksFailed: number,
    tasksRunning: number,
    totalHeartbeats: number,
  ): Promise<RuntimeMetrics> {
    return {
      activeSessions,
      totalSessions,
      activeWorkers,
      idleWorkers,
      totalWorkers,
      tasksCompleted,
      tasksFailed,
      tasksRunning,
      totalHeartbeats,
      totalEvents: events.length,
      uptimeMs: Date.now() - new Date(startedAt).getTime(),
    }
  },
}
