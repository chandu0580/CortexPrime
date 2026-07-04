import type { ObservabilityMetrics } from "./types"
import { TraceManager } from "./TraceManager"
import { SpanManager } from "./SpanManager"
import { AuditManager } from "./AuditManager"
import { MetricsRegistry } from "./MetricsRegistry"
import { ReplayManager } from "./ReplayManager"
import { DiagnosticsEngine } from "./DiagnosticsEngine"
import { CorrelationEngine } from "./CorrelationEngine"

export const ObservabilityMetricsCollector = {
  async collectAll(): Promise<ObservabilityMetrics> {
    const traces = await TraceManager.listTraces()
    const spans = await SpanManager.getSpanCount()
    const audits = await AuditManager.getAuditCount()
    const replays = await ReplayManager.listReplays()
    const diagnostics = await DiagnosticsEngine.getAllDiagnostics()
    const correlations = await CorrelationEngine.getAllCorrelations()

    const allSpans = await Promise.all(traces.map((t) => SpanManager.getSpansByTrace(t.id)))
    const flatSpans = allSpans.flat()
    const failedSpans = flatSpans.filter((s) => s.state === "failed").length

    return {
      totalTraces: traces.length,
      activeTraces: traces.filter((t) => t.state === "active").length,
      totalSpans: spans,
      failedSpans,
      totalAudits: audits,
      totalReplays: replays.length,
      totalDiagnostics: diagnostics.length,
      totalCorrelations: correlations.length,
    }
  },

  async collectTraces(): Promise<number> {
    const traces = await TraceManager.listTraces()
    return traces.length
  },

  async collectSpans(): Promise<{ total: number; failed: number }> {
    const total = await SpanManager.getSpanCount()
    const allTraces = await TraceManager.listTraces()
    const allSpans = await Promise.all(allTraces.map((t) => SpanManager.getSpansByTrace(t.id)))
    const flatSpans = allSpans.flat()
    const failed = flatSpans.filter((s) => s.state === "failed").length
    return { total, failed }
  },

  async collectAudits(): Promise<number> {
    return AuditManager.getAuditCount()
  },

  async collectMetrics(): Promise<number> {
    const series = await MetricsRegistry.queryMetrics()
    return series.reduce((sum, s) => sum + s.samples.length, 0)
  },

  async collectReplays(): Promise<number> {
    const replays = await ReplayManager.listReplays()
    return replays.length
  },

  async collectDiagnostics(): Promise<number> {
    const diags = await DiagnosticsEngine.getAllDiagnostics()
    return diags.length
  },

  async collectCorrelations(): Promise<number> {
    return CorrelationEngine.getCorrelationCount()
  },
}
