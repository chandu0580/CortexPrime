import type { DeepgramConfig, DeepgramConnectionState, VoiceWord } from "./types"

export interface DeepgramTranscript {
  transcript: string
  confidence: number
  words: VoiceWord[]
  isFinal: boolean
  speechFinal: boolean
  channelIndex: number
  language: string
}

export interface DeepgramVADEvent {
  type: "speech_started" | "speech_ended" | "endpoint" | "silence_detected"
  timestamp: string
  durationMs?: number
}

export interface DeepgramSession {
  id: string
  config: DeepgramConfig
  state: DeepgramConnectionState
  startedAt: string
  transcriptCount: number
  wordCount: number
}

const sessions = new Map<string, DeepgramSession>()
const connections = new Map<string, DeepgramConnectionState>()
const transcriptBuffers = new Map<string, DeepgramTranscript[]>()
const vadEvents = new Map<string, DeepgramVADEvent[]>()
const onTranscriptCallbacks = new Map<string, (transcript: DeepgramTranscript) => void>()
const onVADCallbacks = new Map<string, (event: DeepgramVADEvent) => void>()

export const DeepgramManager = {
  async startSession(config: DeepgramConfig, sessionId: string): Promise<DeepgramSession> {
    connections.set(sessionId, "connecting")

    try {
      const session: DeepgramSession = {
        id: sessionId,
        config: { ...config },
        state: "connected",
        startedAt: new Date().toISOString(),
        transcriptCount: 0,
        wordCount: 0,
      }

      sessions.set(sessionId, session)
      transcriptBuffers.set(sessionId, [])
      vadEvents.set(sessionId, [])
      connections.set(sessionId, "connected")

      return session
    } catch (err) {
      connections.set(sessionId, "error")
      throw err
    }
  },

  async stopSession(sessionId: string): Promise<void> {
    connections.set(sessionId, "disconnected")
    sessions.delete(sessionId)
    transcriptBuffers.delete(sessionId)
    vadEvents.delete(sessionId)
    onTranscriptCallbacks.delete(sessionId)
    onVADCallbacks.delete(sessionId)
  },

  async getSession(sessionId: string): Promise<DeepgramSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async getConnectionState(sessionId: string): Promise<DeepgramConnectionState> {
    return connections.get(sessionId) ?? "disconnected"
  },

  async processAudioChunk(sessionId: string): Promise<DeepgramTranscript | null> {
    const session = sessions.get(sessionId)
    if (!session || session.state !== "connected") {
      return null
    }

    const mockTranscript: DeepgramTranscript = {
      transcript: "",
      confidence: 0,
      words: [],
      isFinal: false,
      speechFinal: false,
      channelIndex: 0,
      language: session.config.language ?? "en-US",
    }

    session.transcriptCount++

    const buffer = transcriptBuffers.get(sessionId) ?? []
    buffer.push(mockTranscript)
    transcriptBuffers.set(sessionId, buffer)

    const callback = onTranscriptCallbacks.get(sessionId)
    if (callback) {
      callback(mockTranscript)
    }

    return mockTranscript
  },

  async sendFinalTranscript(sessionId: string, transcript: string, confidence: number, words: VoiceWord[]): Promise<DeepgramTranscript> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Deepgram session ${sessionId} not found`)
    }

    const finalTranscript: DeepgramTranscript = {
      transcript,
      confidence,
      words,
      isFinal: true,
      speechFinal: true,
      channelIndex: 0,
      language: session.config.language ?? "en-US",
    }

    session.transcriptCount++
    session.wordCount += words.length

    const buffer = transcriptBuffers.get(sessionId) ?? []
    buffer.push(finalTranscript)
    transcriptBuffers.set(sessionId, buffer)

    const callback = onTranscriptCallbacks.get(sessionId)
    if (callback) {
      callback(finalTranscript)
    }

    return finalTranscript
  },

  async processInterimTranscript(sessionId: string, transcript: string, confidence: number): Promise<DeepgramTranscript> {
    const session = sessions.get(sessionId)
    if (!session) {
      throw new Error(`Deepgram session ${sessionId} not found`)
    }

    const interimTranscript: DeepgramTranscript = {
      transcript,
      confidence,
      words: [],
      isFinal: false,
      speechFinal: false,
      channelIndex: 0,
      language: session.config.language ?? "en-US",
    }

    const buffer = transcriptBuffers.get(sessionId) ?? []
    buffer.push(interimTranscript)
    transcriptBuffers.set(sessionId, buffer)

    const callback = onTranscriptCallbacks.get(sessionId)
    if (callback) {
      callback(interimTranscript)
    }

    return interimTranscript
  },

  async processVADEvent(sessionId: string, type: DeepgramVADEvent["type"], durationMs?: number): Promise<DeepgramVADEvent> {
    const event: DeepgramVADEvent = {
      type,
      timestamp: new Date().toISOString(),
      durationMs,
    }

    const events = vadEvents.get(sessionId) ?? []
    events.push(event)
    vadEvents.set(sessionId, events)

    const callback = onVADCallbacks.get(sessionId)
    if (callback) {
      callback(event)
    }

    return event
  },

  async onTranscript(sessionId: string, callback: (transcript: DeepgramTranscript) => void): Promise<void> {
    onTranscriptCallbacks.set(sessionId, callback)
  },

  async onVAD(sessionId: string, callback: (event: DeepgramVADEvent) => void): Promise<void> {
    onVADCallbacks.set(sessionId, callback)
  },

  async getTranscripts(sessionId: string, limit?: number): Promise<DeepgramTranscript[]> {
    const buffer = transcriptBuffers.get(sessionId) ?? []
    if (limit) {
      return buffer.slice(-limit)
    }
    return [...buffer]
  },

  async getVADEvents(sessionId: string, limit?: number): Promise<DeepgramVADEvent[]> {
    const events = vadEvents.get(sessionId) ?? []
    if (limit) {
      return events.slice(-limit)
    }
    return [...events]
  },

  async getWordCount(sessionId: string): Promise<number> {
    const session = sessions.get(sessionId)
    return session?.wordCount ?? 0
  },

  async getTranscriptCount(sessionId: string): Promise<number> {
    const session = sessions.get(sessionId)
    return session?.transcriptCount ?? 0
  },

  async reconnect(sessionId: string): Promise<boolean> {
    connections.set(sessionId, "connecting")

    try {
      await new Promise((resolve) => setTimeout(resolve, 500))
      connections.set(sessionId, "connected")
      return true
    } catch {
      connections.set(sessionId, "error")
      return false
    }
  },

  async getActiveSessions(): Promise<DeepgramSession[]> {
    return Array.from(sessions.values()).filter((s) => s.state === "connected")
  },

  async cleanup(): Promise<void> {
    sessions.clear()
    connections.clear()
    transcriptBuffers.clear()
    vadEvents.clear()
    onTranscriptCallbacks.clear()
    onVADCallbacks.clear()
  },
}
