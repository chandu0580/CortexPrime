import type { CorrelationRecord } from "./types"
import { generateId } from "./shared"

const correlations = new Map<string, CorrelationRecord>()

export const CorrelationEngine = {
  async correlateEvents(traceId: string, sourceEventId: string, targetEventId: string, confidence: number = 1, metadata: Record<string, unknown> = {}): Promise<CorrelationRecord> {
    const id = generateId("corr")
    const record: CorrelationRecord = {
      id,
      traceId,
      sourceType: "event",
      sourceId: sourceEventId,
      targetType: "event",
      targetId: targetEventId,
      relationship: "related",
      confidence,
      metadata,
    }
    correlations.set(id, record)
    return record
  },

  async correlateWorkers(traceId: string, sourceWorkerId: string, targetWorkerId: string, relationship: string = "communicated", confidence: number = 1, metadata: Record<string, unknown> = {}): Promise<CorrelationRecord> {
    const id = generateId("corr")
    const record: CorrelationRecord = {
      id,
      traceId,
      sourceType: "worker",
      sourceId: sourceWorkerId,
      targetType: "worker",
      targetId: targetWorkerId,
      relationship,
      confidence,
      metadata,
    }
    correlations.set(id, record)
    return record
  },

  async correlateSessions(traceId: string, sourceSessionId: string, targetSessionId: string, relationship: string = "chained", confidence: number = 1, metadata: Record<string, unknown> = {}): Promise<CorrelationRecord> {
    const id = generateId("corr")
    const record: CorrelationRecord = {
      id,
      traceId,
      sourceType: "session",
      sourceId: sourceSessionId,
      targetType: "session",
      targetId: targetSessionId,
      relationship,
      confidence,
      metadata,
    }
    correlations.set(id, record)
    return record
  },

  async correlateMissions(traceId: string, sourceMissionId: string, targetMissionId: string, relationship: string = "triggered", confidence: number = 1, metadata: Record<string, unknown> = {}): Promise<CorrelationRecord> {
    const id = generateId("corr")
    const record: CorrelationRecord = {
      id,
      traceId,
      sourceType: "mission",
      sourceId: sourceMissionId,
      targetType: "mission",
      targetId: targetMissionId,
      relationship,
      confidence,
      metadata,
    }
    correlations.set(id, record)
    return record
  },

  async getCorrelations(traceId: string): Promise<CorrelationRecord[]> {
    return Array.from(correlations.values()).filter((c) => c.traceId === traceId)
  },

  async getAllCorrelations(): Promise<CorrelationRecord[]> {
    return Array.from(correlations.values())
  },

  async getCorrelationCount(): Promise<number> {
    return correlations.size
  },
}
