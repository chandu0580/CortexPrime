import type { VoiceStream, VoiceStreamType, VoiceStreamState } from "./types"
import { generateId } from "@/worker-framework/shared"

const streams = new Map<string, VoiceStream>()
const streamChunks = new Map<string, { index: number; bytes: number; timestamp: string }[]>()

export const VoiceStreamManager = {
  async createStream(
    sessionId: string,
    type: VoiceStreamType,
    format: string,
    encoding: string,
    sampleRate: number,
    channels: number,
  ): Promise<VoiceStream> {
    const stream: VoiceStream = {
      id: generateId("voice-stream"),
      sessionId,
      turnId: null,
      type,
      format,
      encoding,
      sampleRate,
      channels,
      state: "created",
      startedAt: new Date().toISOString(),
      completedAt: null,
      durationMs: null,
      chunkCount: 0,
      totalBytes: 0,
    }
    streams.set(stream.id, stream)
    streamChunks.set(stream.id, [])
    await this.transitionState(stream.id, "active")
    return stream
  },

  async linkToTurn(streamId: string, turnId: string): Promise<void> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }
    stream.turnId = turnId
  },

  async completeStream(streamId: string): Promise<VoiceStream> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }
    const now = new Date().toISOString()
    const start = new Date(stream.startedAt).getTime()
    stream.state = "completed"
    stream.completedAt = now
    stream.durationMs = Date.now() - start
    streamChunks.delete(streamId)
    return stream
  },

  async getStream(streamId: string): Promise<VoiceStream | null> {
    return streams.get(streamId) ?? null
  },

  async getStreamsBySession(sessionId: string): Promise<VoiceStream[]> {
    return Array.from(streams.values()).filter((s) => s.sessionId === sessionId)
  },

  async getStreamsByTurn(turnId: string): Promise<VoiceStream[]> {
    return Array.from(streams.values()).filter((s) => s.turnId === turnId)
  },

  async transitionState(streamId: string, target: VoiceStreamState): Promise<void> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }
    const valid: Record<VoiceStreamState, VoiceStreamState[]> = {
      created: ["active"],
      active: ["completed", "error"],
      completed: [],
      error: [],
    }
    if (!valid[stream.state].includes(target)) {
      throw new Error(`Invalid voice stream state transition: ${stream.state} → ${target}`)
    }
    stream.state = target
  },

  async markError(streamId: string): Promise<void> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }
    stream.state = "error"
  },

  async recordChunk(streamId: string, bytes: number): Promise<{ index: number; bytes: number; timestamp: string }> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }

    const chunks = streamChunks.get(streamId) ?? []
    const chunk = {
      index: chunks.length,
      bytes,
      timestamp: new Date().toISOString(),
    }
    chunks.push(chunk)
    streamChunks.set(streamId, chunks)

    stream.chunkCount++
    stream.totalBytes += bytes

    return chunk
  },

  async getChunks(streamId: string): Promise<{ index: number; bytes: number; timestamp: string }[]> {
    return streamChunks.get(streamId) ?? []
  },

  async setLiveKitTrackSid(streamId: string, trackSid: string): Promise<void> {
    const stream = streams.get(streamId)
    if (!stream) {
      throw new Error(`Voice stream ${streamId} not found`)
    }
    stream.livekitTrackSid = trackSid
  },

  async getActiveStreams(): Promise<VoiceStream[]> {
    return Array.from(streams.values()).filter((s) => s.state === "active")
  },

  async getStreamCount(): Promise<number> {
    return streams.size
  },

  async clearSession(sessionId: string): Promise<void> {
    for (const [id, stream] of streams.entries()) {
      if (stream.sessionId === sessionId) {
        streams.delete(id)
        streamChunks.delete(id)
      }
    }
  },
}
