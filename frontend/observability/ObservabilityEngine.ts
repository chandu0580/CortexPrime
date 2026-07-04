import type { Trace, Span, AuditRecord, AuditEvent, MetricSample, ReplaySession, ReplayFrame, CorrelationRecord, DiagnosticResult, HealthSnapshot, ValidationResult, ObservabilityPolicy, ObservabilityDecision, ObservabilityMetrics, ObservabilityHealth, ObservabilityCapabilityDefinition } from "./types"
import type { AuditSeverity } from "./types"
import { TraceManager } from "./TraceManager"
import { SpanManager } from "./SpanManager"
import { MetricsRegistry } from "./MetricsRegistry"
import { DiagnosticsEngine } from "./DiagnosticsEngine"
import { AuditManager } from "./AuditManager"
import { ReplayManager } from "./ReplayManager"
import { CorrelationEngine } from "./CorrelationEngine"
import { ObservabilityPolicyEngine } from "./ObservabilityPolicyEngine"
import { ObservabilityValidationEngine } from "./ObservabilityValidationEngine"
import { ObservabilityMetricsCollector } from "./ObservabilityMetricsCollector"
import { ObservabilityHealthManager } from "./ObservabilityHealthManager"
import { ObservabilityCapability } from "./ObservabilityCapability"
import { cortexEventBus } from "@/event-bus/cortexEventBus"

export const ObservabilityEngine = {
  async trace(): Promise<{
    create: typeof TraceManager.createTrace
    close: typeof TraceManager.closeTrace
    get: typeof TraceManager.getTrace
    list: typeof TraceManager.listTraces
    startSpan: typeof SpanManager.startSpan
    finishSpan: typeof SpanManager.finishSpan
    failSpan: typeof SpanManager.failSpan
    childSpan: typeof SpanManager.childSpan
    getSpans: typeof SpanManager.getSpansByTrace
    addLog: typeof SpanManager.addLog
  }> {
    return {
      create: TraceManager.createTrace,
      close: TraceManager.closeTrace,
      get: TraceManager.getTrace,
      list: TraceManager.listTraces,
      startSpan: SpanManager.startSpan,
      finishSpan: SpanManager.finishSpan,
      failSpan: SpanManager.failSpan,
      childSpan: SpanManager.childSpan,
      getSpans: SpanManager.getSpansByTrace,
      addLog: SpanManager.addLog,
    }
  },

  async replay(): Promise<{
    create: typeof ReplayManager.createReplay
    addFrame: typeof ReplayManager.addFrame
    checkpoint: typeof ReplayManager.checkpoint
    replay: typeof ReplayManager.replay
    get: typeof ReplayManager.getReplay
    list: typeof ReplayManager.listReplays
  }> {
    return {
      create: ReplayManager.createReplay,
      addFrame: ReplayManager.addFrame,
      checkpoint: ReplayManager.checkpoint,
      replay: ReplayManager.replay,
      get: ReplayManager.getReplay,
      list: ReplayManager.listReplays,
    }
  },

  async diagnostics(): Promise<{
    analyze: typeof DiagnosticsEngine.analyzeTrace
    detectLatency: typeof DiagnosticsEngine.detectLatency
    detectFailures: typeof DiagnosticsEngine.detectFailures
    build: typeof DiagnosticsEngine.buildDiagnostics
    get: typeof DiagnosticsEngine.getDiagnostics
    getAll: typeof DiagnosticsEngine.getAllDiagnostics
  }> {
    return {
      analyze: DiagnosticsEngine.analyzeTrace,
      detectLatency: DiagnosticsEngine.detectLatency,
      detectFailures: DiagnosticsEngine.detectFailures,
      build: DiagnosticsEngine.buildDiagnostics,
      get: DiagnosticsEngine.getDiagnostics,
      getAll: DiagnosticsEngine.getAllDiagnostics,
    }
  },

  async audit(): Promise<{
    record: typeof AuditManager.recordAudit
    query: typeof AuditManager.queryAudit
    timeline: typeof AuditManager.buildTimeline
    get: typeof AuditManager.getAudit
  }> {
    return {
      record: AuditManager.recordAudit,
      query: AuditManager.queryAudit,
      timeline: AuditManager.buildTimeline,
      get: AuditManager.getAudit,
    }
  },

  async metrics(): Promise<{
    register: typeof MetricsRegistry.registerMetric
    record: typeof MetricsRegistry.recordMetric
    aggregate: typeof MetricsRegistry.aggregateMetrics
    query: typeof MetricsRegistry.queryMetrics
    get: typeof MetricsRegistry.getMetric
  }> {
    return {
      register: MetricsRegistry.registerMetric,
      record: MetricsRegistry.recordMetric,
      aggregate: MetricsRegistry.aggregateMetrics,
      query: MetricsRegistry.queryMetrics,
      get: MetricsRegistry.getMetric,
    }
  },

  async validate(): Promise<{
    traceIntegrity: typeof ObservabilityValidationEngine.validateTraceIntegrity
    replayConsistency: typeof ObservabilityValidationEngine.validateReplayConsistency
    metricCompleteness: typeof ObservabilityValidationEngine.validateMetricCompleteness
    correlationCorrectness: typeof ObservabilityValidationEngine.validateCorrelationCorrectness
    auditIntegrity: typeof ObservabilityValidationEngine.validateAuditIntegrity
    get: typeof ObservabilityValidationEngine.getValidations
  }> {
    return {
      traceIntegrity: ObservabilityValidationEngine.validateTraceIntegrity,
      replayConsistency: ObservabilityValidationEngine.validateReplayConsistency,
      metricCompleteness: ObservabilityValidationEngine.validateMetricCompleteness,
      correlationCorrectness: ObservabilityValidationEngine.validateCorrelationCorrectness,
      auditIntegrity: ObservabilityValidationEngine.validateAuditIntegrity,
      get: ObservabilityValidationEngine.getValidations,
    }
  },

  async health(): Promise<{
    get: typeof ObservabilityHealthManager.getHealth
    snapshot: typeof ObservabilityHealthManager.snapshot
    snapshots: typeof ObservabilityHealthManager.getSnapshots
    recordDroppedTrace: typeof ObservabilityHealthManager.recordDroppedTrace
    recordFailedSpan: typeof ObservabilityHealthManager.recordFailedSpan
    recordReplayFailure: typeof ObservabilityHealthManager.recordReplayFailure
    recordMetricFailure: typeof ObservabilityHealthManager.recordMetricFailure
    recordAuditFailure: typeof ObservabilityHealthManager.recordAuditFailure
  }> {
    return {
      get: ObservabilityHealthManager.getHealth,
      snapshot: ObservabilityHealthManager.snapshot,
      snapshots: ObservabilityHealthManager.getSnapshots,
      recordDroppedTrace: ObservabilityHealthManager.recordDroppedTrace,
      recordFailedSpan: ObservabilityHealthManager.recordFailedSpan,
      recordReplayFailure: ObservabilityHealthManager.recordReplayFailure,
      recordMetricFailure: ObservabilityHealthManager.recordMetricFailure,
      recordAuditFailure: ObservabilityHealthManager.recordAuditFailure,
    }
  },

  async createTrace(name: string, service: string, tags?: Record<string, string>, attributes?: Record<string, unknown>): Promise<Trace> {
    const trace = await TraceManager.createTrace(name, service, tags, attributes)
    await cortexEventBus.publish("observability", "analytics", "observability.trace.created", "ObservabilityEngine", {
      traceId: trace.id,
      name,
      service,
    }, "low", trace.id)
    return trace
  },

  async closeTrace(traceId: string, finalState: "completed" | "failed"): Promise<Trace> {
    const trace = await TraceManager.closeTrace(traceId, finalState)
    await cortexEventBus.publish("observability", "analytics", `observability.trace.${finalState}`, "ObservabilityEngine", {
      traceId: trace.id,
      state: finalState,
    }, "low", traceId)
    return trace
  },

  async startSpan(traceId: string, name: string, service: string, operation: string, parentSpanId?: string, kind?: string, tags?: Record<string, string>, attributes?: Record<string, unknown>): Promise<Span> {
    const span = await SpanManager.startSpan(traceId, name, service, operation, parentSpanId, kind, tags, attributes)
    await cortexEventBus.publish("observability", "analytics", "observability.span.started", "ObservabilityEngine", {
      spanId: span.id,
      traceId,
      name,
      service,
    }, "low", traceId)
    return span
  },

  async finishSpan(spanId: string): Promise<Span> {
    const span = await SpanManager.finishSpan(spanId)
    await cortexEventBus.publish("observability", "analytics", "observability.span.completed", "ObservabilityEngine", {
      spanId: span.id,
      traceId: span.traceId,
      durationMs: span.durationMs,
    }, "low", span.traceId)
    return span
  },

  async failSpan(spanId: string, message: string): Promise<Span> {
    const span = await SpanManager.failSpan(spanId, message)
    await ObservabilityHealthManager.recordFailedSpan()
    await cortexEventBus.publish("observability", "analytics", "observability.span.failed", "ObservabilityEngine", {
      spanId: span.id,
      traceId: span.traceId,
      message,
    }, "high", span.traceId)
    return span
  },

  async recordMetric(name: string, value: number, labels?: Record<string, string>): Promise<MetricSample> {
    const sample = await MetricsRegistry.recordMetric(name, value, labels)
    await cortexEventBus.publish("observability", "analytics", "observability.metric.recorded", "ObservabilityEngine", {
      metric: name,
      value,
      labels,
    }, "low", "metrics")
    return sample
  },

  async recordAudit(action: string, actor: string, target: string, severity: AuditSeverity, source: string, details?: string, metadata?: Record<string, unknown>): Promise<{ record: AuditRecord; event: AuditEvent }> {
    const result = await AuditManager.recordAudit(action, actor, target, severity, source, details, metadata)
    await cortexEventBus.publish("observability", "analytics", `observability.audit.${action}`, "ObservabilityEngine", {
      auditId: result.record.id,
      action,
      actor,
      target,
      severity,
    }, severity === "critical" ? "high" : "low", result.record.id)
    return result
  },

  async createReplay(traceId: string, name: string, metadata?: Record<string, unknown>): Promise<ReplaySession> {
    const session = await ReplayManager.createReplay(traceId, name, metadata)
    await cortexEventBus.publish("observability", "analytics", "observability.replay.created", "ObservabilityEngine", {
      sessionId: session.id,
      traceId,
      name,
    }, "low", traceId)
    return session
  },

  async replayFrames(sessionId: string): Promise<ReplayFrame[]> {
    const frames = await ReplayManager.replay(sessionId)
    const session = await ReplayManager.getReplay(sessionId)
    await cortexEventBus.publish("observability", "analytics", "observability.replay.completed", "ObservabilityEngine", {
      sessionId,
      frameCount: frames.length,
    }, "normal", session?.traceId ?? "unknown")
    return frames
  },

  async correlateEvents(traceId: string, sourceEventId: string, targetEventId: string, confidence?: number): Promise<CorrelationRecord> {
    const record = await CorrelationEngine.correlateEvents(traceId, sourceEventId, targetEventId, confidence)
    await cortexEventBus.publish("observability", "analytics", "observability.correlation.created", "ObservabilityEngine", {
      correlationId: record.id,
      traceId,
      sourceEventId,
      targetEventId,
    }, "low", traceId)
    return record
  },

  async analyzeTrace(traceId: string, spans: Span[]): Promise<DiagnosticResult[]> {
    const results = await DiagnosticsEngine.analyzeTrace(traceId, spans)
    const criticalCount = results.filter((r) => r.severity === "critical" || r.severity === "error").length
    if (criticalCount > 0) {
      await cortexEventBus.publish("observability", "analytics", "observability.diagnostics.alert", "ObservabilityEngine", {
        traceId,
        diagnosticCount: results.length,
        criticalCount,
      }, "high", traceId)
    }
    return results
  },

  async validateTrace(trace: Trace, spans: Span[]): Promise<ValidationResult> {
    const result = await ObservabilityValidationEngine.validateTraceIntegrity(trace, spans)
    await cortexEventBus.publish("observability", "analytics", "observability.validation.completed", "ObservabilityEngine", {
      validationId: result.id,
      type: result.type,
      passed: result.passed,
      errors: result.errors.length,
    }, result.passed ? "low" : "high", trace.id)
    return result
  },

  async collectMetrics(): Promise<ObservabilityMetrics> {
    const metrics = await ObservabilityMetricsCollector.collectAll()
    await cortexEventBus.publish("observability", "analytics", "observability.metrics.collected", "ObservabilityEngine", {
      metrics,
    }, "low", "metrics")
    return metrics
  },

  async getHealth(): Promise<ObservabilityHealth> {
    return ObservabilityHealthManager.getHealth()
  },

  async snapshotHealth(component: string, metrics: Record<string, number>, details?: string): Promise<HealthSnapshot> {
    const snapshot = await ObservabilityHealthManager.snapshot(component, metrics, details)
    const health = await ObservabilityHealthManager.getHealth()
    await cortexEventBus.publish("observability", "analytics", "observability.health.snapshot", "ObservabilityEngine", {
      component,
      status: health.status,
      snapshot,
    }, health.status === "unhealthy" ? "high" : "low", "health")
    return snapshot
  },

  async getCapabilities(): Promise<ObservabilityCapabilityDefinition[]> {
    return ObservabilityCapability.list()
  },

  async isCapabilityEnabled(name: string): Promise<boolean> {
    return ObservabilityCapability.isEnabled(name)
  },

  async evaluatePolicy(policyId: string, type: string, current: number, max: number): Promise<ObservabilityDecision> {
    switch (type) {
      case "audit_retention":
        return ObservabilityPolicyEngine.evaluateAuditRetention(policyId, current, max)
      case "trace_policy":
        return ObservabilityPolicyEngine.evaluateTracePolicy(policyId, current, max)
      case "replay_policy":
        return ObservabilityPolicyEngine.evaluateReplayPolicy(policyId, current, max)
      case "metrics_policy":
        return ObservabilityPolicyEngine.evaluateMetricsPolicy(policyId, current, max)
      case "diagnostic_policy":
        return ObservabilityPolicyEngine.evaluateDiagnosticPolicy(policyId, current, max)
      default:
        throw new Error(`Unknown policy type: ${type}`)
    }
  },

  async registerPolicy(policy: Omit<ObservabilityPolicy, "id">): Promise<ObservabilityPolicy> {
    return ObservabilityPolicyEngine.registerPolicy(policy)
  },
}
