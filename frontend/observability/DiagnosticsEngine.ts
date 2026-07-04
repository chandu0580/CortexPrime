import type { DiagnosticResult, Span } from "./types"
import { generateId } from "./shared"

const diagnostics = new Map<string, DiagnosticResult>()

export const DiagnosticsEngine = {
  async analyzeTrace(traceId: string, spans: Span[]): Promise<DiagnosticResult[]> {
    const results: DiagnosticResult[] = []

    const latencyResults = await DiagnosticsEngine.detectLatency(traceId, spans)
    results.push(...latencyResults)

    const failureResults = await DiagnosticsEngine.detectFailures(traceId, spans)
    results.push(...failureResults)

    const customResults = await DiagnosticsEngine.buildDiagnostics(traceId, spans)
    results.push(...customResults)

    for (const result of results) {
      diagnostics.set(result.id, result)
    }

    return results
  },

  async detectLatency(traceId: string, spans: Span[]): Promise<DiagnosticResult[]> {
    const results: DiagnosticResult[] = []
    const threshold = 1000

    for (const span of spans) {
      if (span.durationMs !== null && span.durationMs > threshold) {
        const result: DiagnosticResult = {
          id: generateId("diag"),
          traceId,
          type: "latency",
          severity: span.durationMs > threshold * 5 ? "critical" : "warning",
          message: `Span "${span.name}" exceeded latency threshold: ${span.durationMs}ms (max ${threshold}ms)`,
          details: {
            spanId: span.id,
            operation: span.operation,
            service: span.service,
            durationMs: span.durationMs,
            threshold,
          },
          timestamp: new Date().toISOString(),
          source: "DiagnosticsEngine",
        }
        results.push(result)
      }
    }
    return results
  },

  async detectFailures(traceId: string, spans: Span[]): Promise<DiagnosticResult[]> {
    const results: DiagnosticResult[] = []

    for (const span of spans) {
      if (span.state === "failed") {
        const result: DiagnosticResult = {
          id: generateId("diag"),
          traceId,
          type: "failure",
          severity: "error",
          message: `Span "${span.name}" failed in service "${span.service}"`,
          details: {
            spanId: span.id,
            operation: span.operation,
            service: span.service,
            status: span.status,
          },
          timestamp: new Date().toISOString(),
          source: "DiagnosticsEngine",
        }
        results.push(result)
      }
    }
    return results
  },

  async buildDiagnostics(traceId: string, spans: Span[]): Promise<DiagnosticResult[]> {
    const results: DiagnosticResult[] = []

    if (spans.length === 0) {
      const result: DiagnosticResult = {
        id: generateId("diag"),
        traceId,
        type: "integrity",
        severity: "warning",
        message: `Trace "${traceId}" has no spans`,
        details: { traceId, spanCount: 0 },
        timestamp: new Date().toISOString(),
        source: "DiagnosticsEngine",
      }
      results.push(result)
    }

    const missingDuration = spans.filter((s) => s.durationMs === null && s.state !== "started")
    if (missingDuration.length > 0) {
      const result: DiagnosticResult = {
        id: generateId("diag"),
        traceId,
        type: "integrity",
        severity: "warning",
        message: `${missingDuration.length} completed spans have no duration`,
        details: {
          traceId,
          spanIds: missingDuration.map((s) => s.id),
        },
        timestamp: new Date().toISOString(),
        source: "DiagnosticsEngine",
      }
      results.push(result)
    }

    return results
  },

  async getDiagnostics(traceId: string): Promise<DiagnosticResult[]> {
    return Array.from(diagnostics.values()).filter((d) => d.traceId === traceId)
  },

  async getAllDiagnostics(): Promise<DiagnosticResult[]> {
    return Array.from(diagnostics.values())
  },
}
