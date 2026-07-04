import type { VoiceMetrics } from "./types"

const workerMetrics = new Map<string, {
  totalSessions: number
  totalTurns: number
  totalStreams: number
  totalActivities: number
  totalErrors: number
  turnDurations: number[]
  inputDurations: number[]
  outputDurations: number[]
  startedAt: string
  totalConnections: number
  totalReconnects: number
  totalInterruptions: number
  totalWordsTranscribed: number
  totalCharactersSynthesized: number
  sttDurations: number[]
  ttsDurations: number[]
}>()

export const VoiceMetricsCollector = {
  async initialize(workerId: string): Promise<void> {
    if (workerMetrics.has(workerId)) return
    workerMetrics.set(workerId, {
      totalSessions: 0,
      totalTurns: 0,
      totalStreams: 0,
      totalActivities: 0,
      totalErrors: 0,
      turnDurations: [],
      inputDurations: [],
      outputDurations: [],
      startedAt: new Date().toISOString(),
      totalConnections: 0,
      totalReconnects: 0,
      totalInterruptions: 0,
      totalWordsTranscribed: 0,
      totalCharactersSynthesized: 0,
      sttDurations: [],
      ttsDurations: [],
    })
  },

  async recordSessionCreated(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalSessions++
  },

  async recordTurn(workerId: string, durationMs: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) {
      metrics.totalTurns++
      metrics.turnDurations.push(durationMs)
    }
  },

  async recordStream(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalStreams++
  },

  async recordActivity(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalActivities++
  },

  async recordError(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalErrors++
  },

  async recordInputDuration(workerId: string, durationMs: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.inputDurations.push(durationMs)
  },

  async recordOutputDuration(workerId: string, durationMs: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.outputDurations.push(durationMs)
  },

  async recordConnection(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalConnections++
  },

  async recordReconnect(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalReconnects++
  },

  async recordInterruption(workerId: string): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalInterruptions++
  },

  async recordWordsTranscribed(workerId: string, wordCount: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalWordsTranscribed += wordCount
  },

  async recordCharactersSynthesized(workerId: string, characterCount: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.totalCharactersSynthesized += characterCount
  },

  async recordSTTDuration(workerId: string, durationMs: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.sttDurations.push(durationMs)
  },

  async recordTTSDuration(workerId: string, durationMs: number): Promise<void> {
    const metrics = workerMetrics.get(workerId)
    if (metrics) metrics.ttsDurations.push(durationMs)
  },

  async collect(workerId: string, activeSessions: number): Promise<VoiceMetrics> {
    const metrics = workerMetrics.get(workerId)
    if (!metrics) {
      return {
        workerId,
        totalSessions: 0,
        activeSessions: 0,
        totalTurns: 0,
        totalStreams: 0,
        totalActivities: 0,
        totalErrors: 0,
        averageTurnDurationMs: 0,
        averageInputDurationMs: 0,
        averageOutputDurationMs: 0,
        uptimeMs: 0,
        collectedAt: new Date().toISOString(),
        totalConnections: 0,
        totalReconnects: 0,
        totalInterruptions: 0,
        totalWordsTranscribed: 0,
        totalCharactersSynthesized: 0,
        averageSTTDurationMs: 0,
        averageTTSDurationMs: 0,
      }
    }

    const avg = (arr: number[]): number => arr.length > 0 ? arr.reduce((a, b) => a + b, 0) / arr.length : 0
    const uptime = Date.now() - new Date(metrics.startedAt).getTime()

    return {
      workerId,
      totalSessions: metrics.totalSessions,
      activeSessions,
      totalTurns: metrics.totalTurns,
      totalStreams: metrics.totalStreams,
      totalActivities: metrics.totalActivities,
      totalErrors: metrics.totalErrors,
      averageTurnDurationMs: Math.round(avg(metrics.turnDurations)),
      averageInputDurationMs: Math.round(avg(metrics.inputDurations)),
      averageOutputDurationMs: Math.round(avg(metrics.outputDurations)),
      uptimeMs: uptime,
      collectedAt: new Date().toISOString(),
      totalConnections: metrics.totalConnections,
      totalReconnects: metrics.totalReconnects,
      totalInterruptions: metrics.totalInterruptions,
      totalWordsTranscribed: metrics.totalWordsTranscribed,
      totalCharactersSynthesized: metrics.totalCharactersSynthesized,
      averageSTTDurationMs: Math.round(avg(metrics.sttDurations)),
      averageTTSDurationMs: Math.round(avg(metrics.ttsDurations)),
    }
  },

  async reset(workerId: string): Promise<void> {
    workerMetrics.delete(workerId)
  },
}
