import type { Span, SpanLog, SpanStatus } from "./types"
import { generateId } from "./shared"

const spans = new Map<string, Span>()

export const SpanManager = {
  async startSpan(
    traceId: string,
    name: string,
    service: string,
    operation: string,
    parentSpanId: string | null = null,
    kind: string = "internal",
    tags: Record<string, string> = {},
    attributes: Record<string, unknown> = {},
  ): Promise<Span> {
    const id = generateId("span")
    const span: Span = {
      id,
      traceId,
      parentSpanId,
      name,
      state: "started",
      kind,
      startedAt: new Date().toISOString(),
      endedAt: null,
      durationMs: null,
      service,
      operation,
      tags,
      attributes,
      logs: [],
      status: null,
    }
    spans.set(id, span)
    return span
  },

  async finishSpan(spanId: string, status?: SpanStatus): Promise<Span> {
    const span = spans.get(spanId)
    if (!span) throw new Error(`Span not found: ${spanId}`)
    const endedAt = new Date().toISOString()
    const durationMs = new Date(endedAt).getTime() - new Date(span.startedAt).getTime()
    const updated: Span = {
      ...span,
      state: "completed",
      endedAt,
      durationMs,
      status: status ?? span.status,
    }
    spans.set(spanId, updated)
    return updated
  },

  async failSpan(spanId: string, message: string, code: number = 1): Promise<Span> {
    const span = spans.get(spanId)
    if (!span) throw new Error(`Span not found: ${spanId}`)
    const endedAt = new Date().toISOString()
    const durationMs = new Date(endedAt).getTime() - new Date(span.startedAt).getTime()
    const updated: Span = {
      ...span,
      state: "failed",
      endedAt,
      durationMs,
      status: { code, message },
    }
    spans.set(spanId, updated)
    return updated
  },

  async childSpan(
    parentSpanId: string,
    name: string,
    service: string,
    operation: string,
    kind: string = "internal",
    tags: Record<string, string> = {},
    attributes: Record<string, unknown> = {},
  ): Promise<Span> {
    const parent = spans.get(parentSpanId)
    if (!parent) throw new Error(`Parent span not found: ${parentSpanId}`)
    return SpanManager.startSpan(parent.traceId, name, service, operation, parentSpanId, kind, tags, attributes)
  },

  async getSpan(spanId: string): Promise<Span | null> {
    return spans.get(spanId) ?? null
  },

  async getSpansByTrace(traceId: string): Promise<Span[]> {
    return Array.from(spans.values()).filter((s) => s.traceId === traceId)
  },

  async addLog(spanId: string, message: string, attributes: Record<string, unknown> = {}): Promise<Span> {
    const span = spans.get(spanId)
    if (!span) throw new Error(`Span not found: ${spanId}`)
    const log: SpanLog = {
      timestamp: new Date().toISOString(),
      message,
      attributes,
    }
    const updated: Span = {
      ...span,
      logs: [...span.logs, log],
    }
    spans.set(spanId, updated)
    return updated
  },

  async getSpanCount(): Promise<number> {
    return spans.size
  },
}
