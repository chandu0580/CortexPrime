import type { Trace, TraceState } from "./types"
import { generateId } from "./shared"

const traces = new Map<string, Trace>()

export const TraceManager = {
  async createTrace(name: string, service: string, tags: Record<string, string> = {}, attributes: Record<string, unknown> = {}): Promise<Trace> {
    const id = generateId("trace")
    const trace: Trace = {
      id,
      traceId: id,
      name,
      service,
      state: "active",
      startedAt: new Date().toISOString(),
      endedAt: null,
      spanCount: 0,
      tags,
      attributes,
    }
    traces.set(id, trace)
    return trace
  },

  async closeTrace(traceId: string, finalState: "completed" | "failed"): Promise<Trace> {
    const trace = traces.get(traceId)
    if (!trace) throw new Error(`Trace not found: ${traceId}`)
    const updated: Trace = {
      ...trace,
      state: finalState,
      endedAt: new Date().toISOString(),
    }
    traces.set(traceId, updated)
    return updated
  },

  async getTrace(traceId: string): Promise<Trace | null> {
    return traces.get(traceId) ?? null
  },

  async listTraces(filter?: { state?: TraceState; service?: string }): Promise<Trace[]> {
    let result = Array.from(traces.values())
    if (filter?.state) result = result.filter((t) => t.state === filter.state)
    if (filter?.service) result = result.filter((t) => t.service === filter.service)
    return result.sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime())
  },

  async getTraceCount(): Promise<number> {
    return traces.size
  },
}
