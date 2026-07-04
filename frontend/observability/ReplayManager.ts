import type { ReplaySession, ReplayFrame, ReplayCheckpoint, ReplayState } from "./types"
import { generateId } from "./shared"

const replays = new Map<string, ReplaySession>()

export const ReplayManager = {
  async createReplay(traceId: string, name: string, metadata: Record<string, unknown> = {}): Promise<ReplaySession> {
    const id = generateId("replay")
    const session: ReplaySession = {
      id,
      traceId,
      name,
      state: "recording",
      frames: [],
      checkpoints: [],
      createdAt: new Date().toISOString(),
      metadata,
    }
    replays.set(id, session)
    return session
  },

  async addFrame(sessionId: string, type: string, data: Record<string, unknown>, durationMs: number | null = null): Promise<ReplayFrame> {
    const session = replays.get(sessionId)
    if (!session) throw new Error(`Replay session not found: ${sessionId}`)
    const frame: ReplayFrame = {
      id: generateId("rframe"),
      sessionId,
      sequence: session.frames.length + 1,
      timestamp: new Date().toISOString(),
      type,
      data,
      durationMs,
    }
    const updated: ReplaySession = {
      ...session,
      frames: [...session.frames, frame],
    }
    replays.set(sessionId, updated)
    return frame
  },

  async checkpoint(sessionId: string, label: string): Promise<ReplayCheckpoint> {
    const session = replays.get(sessionId)
    if (!session) throw new Error(`Replay session not found: ${sessionId}`)
    if (session.frames.length === 0) throw new Error(`No frames to checkpoint in session: ${sessionId}`)
    const checkpoint: ReplayCheckpoint = {
      id: generateId("rchk"),
      sessionId,
      frameSequence: session.frames.length,
      label,
      timestamp: new Date().toISOString(),
    }
    const updated: ReplaySession = {
      ...session,
      checkpoints: [...session.checkpoints, checkpoint],
    }
    replays.set(sessionId, updated)
    return checkpoint
  },

  async replay(sessionId: string): Promise<ReplayFrame[]> {
    const session = replays.get(sessionId)
    if (!session) throw new Error(`Replay session not found: ${sessionId}`)
    const updated: ReplaySession = {
      ...session,
      state: "completed",
    }
    replays.set(sessionId, updated)
    return [...session.frames]
  },

  async getReplay(sessionId: string): Promise<ReplaySession | null> {
    return replays.get(sessionId) ?? null
  },

  async listReplays(traceId?: string): Promise<ReplaySession[]> {
    let result = Array.from(replays.values())
    if (traceId) result = result.filter((r) => r.traceId === traceId)
    return result.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
  },

  async setReplayState(sessionId: string, state: ReplayState): Promise<ReplaySession> {
    const session = replays.get(sessionId)
    if (!session) throw new Error(`Replay session not found: ${sessionId}`)
    const updated: ReplaySession = { ...session, state }
    replays.set(sessionId, updated)
    return updated
  },
}
