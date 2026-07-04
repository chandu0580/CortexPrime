import type { ElevenLabsConfig, ElevenLabsConnectionState } from "./types"

export interface ElevenLabsVoice {
  voiceId: string
  name: string
  category: string
  labels: Record<string, string>
}

export interface ElevenLabsTTSChunk {
  audio: ArrayBuffer
  alignment?: { characterCount: number; audioDurationMs: number }
}

export interface ElevenLabsTTSSession {
  id: string
  config: ElevenLabsConfig
  state: ElevenLabsConnectionState
  startedAt: string
  characterCount: number
  requestCount: number
  queue: ElevenLabsTTSRequest[]
  isProcessing: boolean
}

export interface ElevenLabsTTSRequest {
  id: string
  text: string
  voiceId: string
  modelId: string
  createdAt: string
  completedAt: string | null
  success: boolean
  characterCount: number
  audioDurationMs: number | null
  error: string | null
}

const sessions = new Map<string, ElevenLabsTTSSession>()
const connections = new Map<string, ElevenLabsConnectionState>()
const audioChunks = new Map<string, ElevenLabsTTSChunk[]>()
const onAudioCallbacks = new Map<string, (chunk: ElevenLabsTTSChunk) => void>()
const availableVoices: ElevenLabsVoice[] = [
  { voiceId: "21m00Tcm4TlvDq8ikWAM", name: "Rachel", category: "premade", labels: { accent: "American", age: "Young", gender: "Female" } },
  { voiceId: "ErXwobaYiN019PkySvjV", name: "Antoni", category: "premade", labels: { accent: "British", age: "Young", gender: "Male" } },
  { voiceId: "VR6AewLTigWG4xSOukaG", name: "Arnold", category: "premade", labels: { accent: "American", age: "Middle-aged", gender: "Male" } },
  { voiceId: "pNInz6obpgDQGcFmaJgB", name: "Adam", category: "premade", labels: { accent: "American", age: "Young", gender: "Male" } },
  { voiceId: "yoZ06aMxZJJ28mfd3POQ", name: "Sam", category: "premade", labels: { accent: "American", age: "Young", gender: "Male" } },
]

export const ElevenLabsManager = {
  async startSession(config: ElevenLabsConfig, sessionId: string): Promise<ElevenLabsTTSSession> {
    connections.set(sessionId, "connecting")

    try {
      const session: ElevenLabsTTSSession = {
        id: sessionId,
        config: { ...config },
        state: "connected",
        startedAt: new Date().toISOString(),
        characterCount: 0,
        requestCount: 0,
        queue: [],
        isProcessing: false,
      }

      sessions.set(sessionId, session)
      audioChunks.set(sessionId, [])
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
    audioChunks.delete(sessionId)
    onAudioCallbacks.delete(sessionId)
  },

  async getSession(sessionId: string): Promise<ElevenLabsTTSSession | null> {
    return sessions.get(sessionId) ?? null
  },

  async getConnectionState(sessionId: string): Promise<ElevenLabsConnectionState> {
    return connections.get(sessionId) ?? "disconnected"
  },

  async synthesize(sessionId: string, text: string, voiceId?: string): Promise<ElevenLabsTTSChunk> {
    const session = sessions.get(sessionId)
    if (!session || session.state !== "connected") {
      throw new Error(`ElevenLabs session ${sessionId} not connected`)
    }

    const requestId = `tts_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
    const characterCount = text.length
    const estimatedAudioMs = Math.round(characterCount * 80)

    const request: ElevenLabsTTSRequest = {
      id: requestId,
      text,
      voiceId: voiceId ?? session.config.voiceId ?? "21m00Tcm4TlvDq8ikWAM",
      modelId: session.config.modelId ?? "eleven_monolingual_v1",
      createdAt: new Date().toISOString(),
      completedAt: new Date().toISOString(),
      success: true,
      characterCount,
      audioDurationMs: estimatedAudioMs,
      error: null,
    }

    session.characterCount += characterCount
    session.requestCount++
    session.queue.push(request)

    const chunk: ElevenLabsTTSChunk = {
      audio: new ArrayBuffer(0),
      alignment: { characterCount, audioDurationMs: estimatedAudioMs },
    }

    const chunks = audioChunks.get(sessionId) ?? []
    chunks.push(chunk)
    audioChunks.set(sessionId, chunks)

    const callback = onAudioCallbacks.get(sessionId)
    if (callback) {
      callback(chunk)
    }

    return chunk
  },

  async synthesizeStreaming(sessionId: string, text: string, voiceId?: string): Promise<ReadableStream<ElevenLabsTTSChunk>> {
    const session = sessions.get(sessionId)
    if (!session || session.state !== "connected") {
      throw new Error(`ElevenLabs session ${sessionId} not connected`)
    }

    const chunks: ElevenLabsTTSChunk[] = []
    const words = text.split(" ")
    const chunkSize = Math.max(1, Math.floor(words.length / 5))

    for (let i = 0; i < words.length; i += chunkSize) {
      const chunkWords = words.slice(i, i + chunkSize)
      const chunkText = chunkWords.join(" ")
      const chunk = await this.synthesize(sessionId, chunkText, voiceId)
      chunks.push(chunk)
    }

    return new ReadableStream({
      start(controller) {
        for (const chunk of chunks) {
          controller.enqueue(chunk)
        }
        controller.close()
      },
    })
  },

  async cancelSynthesis(sessionId: string, requestId: string): Promise<boolean> {
    const session = sessions.get(sessionId)
    if (!session) return false

    const requestIndex = session.queue.findIndex((r) => r.id === requestId && !r.completedAt)
    if (requestIndex >= 0) {
      session.queue.splice(requestIndex, 1)
      return true
    }
    return false
  },

  async clearQueue(sessionId: string): Promise<void> {
    const session = sessions.get(sessionId)
    if (session) {
      session.queue = session.queue.filter((r) => r.completedAt)
    }
  },

  async getQueueLength(sessionId: string): Promise<number> {
    const session = sessions.get(sessionId)
    if (!session) return 0
    return session.queue.filter((r) => !r.completedAt).length
  },

  async getVoices(): Promise<ElevenLabsVoice[]> {
    return [...availableVoices]
  },

  async getVoice(voiceId: string): Promise<ElevenLabsVoice | null> {
    return availableVoices.find((v) => v.voiceId === voiceId) ?? null
  },

  async onAudio(sessionId: string, callback: (chunk: ElevenLabsTTSChunk) => void): Promise<void> {
    onAudioCallbacks.set(sessionId, callback)
  },

  async getAudioChunks(sessionId: string, limit?: number): Promise<ElevenLabsTTSChunk[]> {
    const chunks = audioChunks.get(sessionId) ?? []
    if (limit) {
      return chunks.slice(-limit)
    }
    return [...chunks]
  },

  async getCharacterCount(sessionId: string): Promise<number> {
    const session = sessions.get(sessionId)
    return session?.characterCount ?? 0
  },

  async getRequestCount(sessionId: string): Promise<number> {
    const session = sessions.get(sessionId)
    return session?.requestCount ?? 0
  },

  async getRequestHistory(sessionId: string): Promise<ElevenLabsTTSRequest[]> {
    const session = sessions.get(sessionId)
    return session?.queue.filter((r) => r.completedAt) ?? []
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

  async getActiveSessions(): Promise<ElevenLabsTTSSession[]> {
    return Array.from(sessions.values()).filter((s) => s.state === "connected")
  },

  async cleanup(): Promise<void> {
    sessions.clear()
    connections.clear()
    audioChunks.clear()
    onAudioCallbacks.clear()
  },
}
