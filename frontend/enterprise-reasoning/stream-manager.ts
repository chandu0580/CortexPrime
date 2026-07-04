import type { StreamingChunk, LLMResponse } from "./types"

interface ActiveStream {
  sessionId: string
  abortController: AbortController
  startedAt: number
}

const activeStreams = new Map<string, ActiveStream>()

export const ReasoningStreamManager = {
  activeStreams,

  async createStream(sessionId: string): Promise<AbortSignal> {
    const existing = activeStreams.get(sessionId)
    if (existing) {
      existing.abortController.abort()
      activeStreams.delete(sessionId)
    }

    const abortController = new AbortController()
    activeStreams.set(sessionId, { sessionId, abortController, startedAt: Date.now() })
    return abortController.signal
  },

  async cancelStream(sessionId: string): Promise<boolean> {
    const stream = activeStreams.get(sessionId)
    if (!stream) return false

    stream.abortController.abort()
    activeStreams.delete(sessionId)
    return true
  },

  async isStreaming(sessionId: string): Promise<boolean> {
    return activeStreams.has(sessionId)
  },

  async cancelAll(): Promise<number> {
    const count = activeStreams.size
    for (const [sessionId, stream] of activeStreams) {
      stream.abortController.abort()
      activeStreams.delete(sessionId)
    }
    return count
  },

  async getActiveStreams(): Promise<string[]> {
    return Array.from(activeStreams.keys())
  },

  async cleanupStaleStreams(maxAgeMs: number = 300000): Promise<number> {
    const now = Date.now()
    let cleaned = 0
    for (const [sessionId, stream] of activeStreams) {
      if (now - stream.startedAt > maxAgeMs) {
        stream.abortController.abort()
        activeStreams.delete(sessionId)
        cleaned++
      }
    }
    return cleaned
  },

  defaultOnChunk: (onContent: (text: string) => void, onDone: (response: LLMResponse | null) => void, onError: (error: string) => void) => {
    return (chunk: StreamingChunk): void => {
      if (chunk.error) {
        onError(chunk.error)
        return
      }

      if (chunk.done) {
        onDone(null)
        return
      }

      onContent(chunk.content)
    }
  },
}
