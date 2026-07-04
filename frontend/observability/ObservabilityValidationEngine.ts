import type { ValidationResult, Trace, Span, ReplaySession, MetricSeries, CorrelationRecord, AuditRecord } from "./types"
import { generateId } from "./shared"

const validations = new Map<string, ValidationResult>()

export const ObservabilityValidationEngine = {
  async validateTraceIntegrity(trace: Trace, spans: Span[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!trace.id) errors.push("Trace missing id")
    if (!trace.traceId) errors.push("Trace missing traceId")
    if (!trace.name) errors.push("Trace missing name")

    const orphanSpans = spans.filter((s) => s.parentSpanId && !spans.find((p) => p.id === s.parentSpanId))
    for (const span of orphanSpans) {
      warnings.push(`Span "${span.name}" references missing parent span: ${span.parentSpanId}`)
    }

    const result: ValidationResult = {
      id: generateId("valid"),
      type: "trace_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { traceId: trace.id, spanCount: spans.length, orphanSpanCount: orphanSpans.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateReplayConsistency(session: ReplaySession): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!session.id) errors.push("Replay session missing id")
    if (!session.traceId) errors.push("Replay session missing traceId")

    const sequences = session.frames.map((f) => f.sequence)
    for (let i = 0; i < sequences.length; i++) {
      if (sequences[i] !== i + 1) {
        errors.push(`Frame sequence gap at index ${i}: expected ${i + 1}, got ${sequences[i]}`)
      }
    }

    for (const cp of session.checkpoints) {
      if (cp.frameSequence > session.frames.length) {
        errors.push(`Checkpoint "${cp.label}" references frame ${cp.frameSequence} beyond frame count ${session.frames.length}`)
      }
    }

    const result: ValidationResult = {
      id: generateId("valid"),
      type: "replay_consistency",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { sessionId: session.id, frameCount: session.frames.length, checkpointCount: session.checkpoints.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateMetricCompleteness(series: MetricSeries): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    if (!series.id) errors.push("Metric series missing id")
    if (!series.name) errors.push("Metric series missing name")
    if (!series.type) errors.push("Metric series missing type")

    if (series.samples.length === 0) {
      warnings.push(`Metric "${series.name}" has no samples`)
    }

    const result: ValidationResult = {
      id: generateId("valid"),
      type: "metric_completeness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { metricName: series.name, sampleCount: series.samples.length, type: series.type },
    }
    validations.set(result.id, result)
    return result
  },

  async validateCorrelationCorrectness(records: CorrelationRecord[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const record of records) {
      if (!record.traceId) errors.push(`Correlation ${record.id} missing traceId`)
      if (!record.sourceId) errors.push(`Correlation ${record.id} missing sourceId`)
      if (!record.targetId) errors.push(`Correlation ${record.id} missing targetId`)
      if (record.confidence < 0 || record.confidence > 1) {
        errors.push(`Correlation ${record.id} has invalid confidence: ${record.confidence}`)
      }
    }

    const result: ValidationResult = {
      id: generateId("valid"),
      type: "correlation_correctness",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { recordCount: records.length },
    }
    validations.set(result.id, result)
    return result
  },

  async validateAuditIntegrity(records: AuditRecord[]): Promise<ValidationResult> {
    const errors: string[] = []
    const warnings: string[] = []

    for (const record of records) {
      if (!record.id) errors.push("Audit record missing id")
      if (!record.action) errors.push(`Audit ${record.id} missing action`)
      if (!record.actor) errors.push(`Audit ${record.id} missing actor`)
      if (!record.timestamp) errors.push(`Audit ${record.id} missing timestamp`)
    }

    if (records.length === 0) {
      warnings.push("No audit records to validate")
    }

    const result: ValidationResult = {
      id: generateId("valid"),
      type: "audit_integrity",
      passed: errors.length === 0,
      errors,
      warnings,
      details: { recordCount: records.length },
    }
    validations.set(result.id, result)
    return result
  },

  async getValidations(type?: string): Promise<ValidationResult[]> {
    let result = Array.from(validations.values())
    if (type) result = result.filter((v) => v.type === type)
    return result
  },
}
