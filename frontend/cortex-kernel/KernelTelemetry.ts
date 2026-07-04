import type { TelemetryEvent, KernelMetadata, MissionSession } from "./types"
import { generateId } from "./shared"

const telemetryEvents: TelemetryEvent[] = []

let kernelStartedAt: string | null = null
let kernelState: "initializing" | "running" | "degraded" | "stopped" | "error" = "initializing"

export const KernelTelemetry = {
  async emitEvent(
    sessionId: string,
    type: string,
    name: string,
    details: string,
    durationMs: number | null = null,
    metadata: Record<string, string> | null = null,
  ): Promise<TelemetryEvent> {
    const event: TelemetryEvent = {
      id: generateId("telem"),
      sessionId,
      type,
      name,
      details,
      timestamp: new Date().toISOString(),
      durationMs,
      metadata,
    }
    telemetryEvents.push(event)
    return event
  },

  async getSessionEvents(sessionId: string): Promise<TelemetryEvent[]> {
    return telemetryEvents.filter((e) => e.sessionId === sessionId)
  },

  async getAllEvents(): Promise<TelemetryEvent[]> {
    return [...telemetryEvents]
  },

  async getEventCount(): Promise<number> {
    return telemetryEvents.length
  },

  async recordInvocationTelemetry(
    sessionId: string,
    engineName: string,
    durationMs: number,
    success: boolean,
  ): Promise<TelemetryEvent> {
    return KernelTelemetry.emitEvent(
      sessionId,
      "invocation",
      `engine.${engineName}.${success ? "completed" : "failed"}`,
      `Engine ${engineName} ${success ? "completed" : "failed"} in ${durationMs}ms`,
      durationMs,
      { engine: engineName, success: String(success) },
    )
  },

  async setKernelState(state: "initializing" | "running" | "degraded" | "stopped" | "error"): Promise<void> {
    kernelState = state
    if (!kernelStartedAt) kernelStartedAt = new Date().toISOString()
  },

  async getMetadata(activeSessionCount: number): Promise<KernelMetadata> {
    const started = kernelStartedAt ?? new Date().toISOString()
    return {
      version: "1.0.0",
      kernelState,
      startedAt: started,
      uptimeMs: Date.now() - new Date(started).getTime(),
      registeredEngineCount: 0,
      activeSessionCount,
      totalInvocations: telemetryEvents.filter((e) => e.type === "invocation").length,
      totalErrors: telemetryEvents.filter((e) => e.name.includes("failed") || e.name.includes("error")).length,
    }
  },
}
