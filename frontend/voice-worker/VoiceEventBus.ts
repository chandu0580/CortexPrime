import type { IEventBus } from "@/platform/interfaces"

let eventBusInstance: IEventBus | null = null

async function publishEvent(eventType: string, data: Record<string, unknown>): Promise<void> {
  if (!eventBusInstance) return

  try {
    await eventBusInstance.publish("voice", eventType, data)
  } catch {
    // Silently fail if event bus is unavailable
  }
}

export const VoiceEventBus = {
  initialize(bus: IEventBus): void {
    eventBusInstance = bus
  },

  async publishSessionCreated(sessionId: string, config: Record<string, unknown>): Promise<void> {
    await publishEvent("voice.session.created", { sessionId, config })
  },

  async publishSessionClosed(sessionId: string, reason?: string): Promise<void> {
    await publishEvent("voice.session.closed", { sessionId, reason })
  },

  async publishSessionPaused(sessionId: string): Promise<void> {
    await publishEvent("voice.session.paused", { sessionId })
  },

  async publishSessionResumed(sessionId: string): Promise<void> {
    await publishEvent("voice.session.resumed", { sessionId })
  },

  async publishRoomJoined(sessionId: string, roomName: string, identity: string): Promise<void> {
    await publishEvent("voice.room.joined", { sessionId, roomName, identity })
  },

  async publishRoomLeft(sessionId: string, roomName: string): Promise<void> {
    await publishEvent("voice.room.left", { sessionId, roomName })
  },

  async publishParticipantJoined(sessionId: string, roomName: string, participantId: string): Promise<void> {
    await publishEvent("voice.participant.joined", { sessionId, roomName, participantId })
  },

  async publishParticipantLeft(sessionId: string, roomName: string, participantId: string): Promise<void> {
    await publishEvent("voice.participant.left", { sessionId, roomName, participantId })
  },

  async publishTranscriptStarted(sessionId: string): Promise<void> {
    await publishEvent("voice.transcript.started", { sessionId })
  },

  async publishTranscriptInterim(sessionId: string, transcript: string, confidence: number): Promise<void> {
    await publishEvent("voice.transcript.interim", { sessionId, transcript, confidence })
  },

  async publishTranscriptFinal(sessionId: string, transcript: string, confidence: number, wordCount: number): Promise<void> {
    await publishEvent("voice.transcript.final", { sessionId, transcript, confidence, wordCount })
  },

  async publishTranscriptEnded(sessionId: string): Promise<void> {
    await publishEvent("voice.transcript.ended", { sessionId })
  },

  async publishSpeechStarted(sessionId: string): Promise<void> {
    await publishEvent("voice.speech.started", { sessionId })
  },

  async publishSpeechEnded(sessionId: string, durationMs: number): Promise<void> {
    await publishEvent("voice.speech.ended", { sessionId, durationMs })
  },

  async publishTTSStarted(sessionId: string, turnId: string, text: string): Promise<void> {
    await publishEvent("voice.tts.started", { sessionId, turnId, text })
  },

  async publishTTSChunk(sessionId: string, turnId: string, chunkIndex: number): Promise<void> {
    await publishEvent("voice.tts.chunk", { sessionId, turnId, chunkIndex })
  },

  async publishTTSCompleted(sessionId: string, turnId: string, durationMs: number, characterCount: number): Promise<void> {
    await publishEvent("voice.tts.completed", { sessionId, turnId, durationMs, characterCount })
  },

  async publishTTSInterrupted(sessionId: string, turnId: string, reason: string): Promise<void> {
    await publishEvent("voice.tts.interrupted", { sessionId, turnId, reason })
  },

  async publishTurnStarted(sessionId: string, turnId: string, turnNumber: number): Promise<void> {
    await publishEvent("voice.turn.started", { sessionId, turnId, turnNumber })
  },

  async publishTurnCompleted(sessionId: string, turnId: string, durationMs: number): Promise<void> {
    await publishEvent("voice.turn.completed", { sessionId, turnId, durationMs })
  },

  async publishTurnInterrupted(sessionId: string, turnId: string, reason: string): Promise<void> {
    await publishEvent("voice.turn.interrupted", { sessionId, turnId, reason })
  },

  async publishStreamOpened(sessionId: string, streamId: string, type: string): Promise<void> {
    await publishEvent("voice.stream.opened", { sessionId, streamId, type })
  },

  async publishStreamClosed(sessionId: string, streamId: string, durationMs: number): Promise<void> {
    await publishEvent("voice.stream.closed", { sessionId, streamId, durationMs })
  },

  async publishStreamChunk(sessionId: string, streamId: string, chunkIndex: number, bytes: number): Promise<void> {
    await publishEvent("voice.stream.chunk", { sessionId, streamId, chunkIndex, bytes })
  },

  async publishConnectionReconnecting(sessionId: string, service: string): Promise<void> {
    await publishEvent("voice.connection.reconnecting", { sessionId, service })
  },

  async publishConnectionRecovered(sessionId: string, service: string): Promise<void> {
    await publishEvent("voice.connection.recovered", { sessionId, service })
  },

  async publishConnectionFailed(sessionId: string, service: string, error: string): Promise<void> {
    await publishEvent("voice.connection.failed", { sessionId, service, error })
  },

  async publishInterruption(sessionId: string, turnId: string, reason: string): Promise<void> {
    await publishEvent("voice.interruption", { sessionId, turnId, reason })
  },

  async publishError(sessionId: string, code: string, message: string): Promise<void> {
    await publishEvent("voice.error", { sessionId, code, message })
  },

  async publishHealthCheck(health: Record<string, unknown>): Promise<void> {
    await publishEvent("voice.health.check", health)
  },

  async publishMetricsCollected(metrics: Record<string, unknown>): Promise<void> {
    await publishEvent("voice.metrics.collected", metrics)
  },
}
