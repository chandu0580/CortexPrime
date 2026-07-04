import type { PlatformError } from "@/platform/contracts"

export type VoiceState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "paused"
  | "error"

export type VoiceSessionStatus =
  | "created"
  | "active"
  | "paused"
  | "closed"
  | "errored"

export type VoiceActivityType =
  | "speaking"
  | "listening"
  | "silence"
  | "thinking"
  | "error"

export type VoiceStreamType = "input" | "output"

export type VoiceStreamState = "created" | "active" | "completed" | "error"

export type VoicePolicyEffect = "allow" | "deny" | "audit"

export type LiveKitConnectionState = "disconnected" | "connecting" | "connected" | "reconnecting"

export type DeepgramConnectionState = "disconnected" | "connecting" | "connected" | "error"

export type ElevenLabsConnectionState = "disconnected" | "connecting" | "connected" | "error"

export interface VoiceSession {
  id: string
  status: VoiceSessionStatus
  state: VoiceState
  config: VoiceConfiguration
  startedAt: string
  updatedAt: string
  completedAt: string | null
  turnCount: number
  currentTurnId: string | null
  error: PlatformError | null
  livekitRoomName?: string
  livekitRoomSid?: string
  deepgramSessionId?: string
}

export interface VoiceTurn {
  id: string
  sessionId: string
  turnNumber: number
  input: VoiceInput
  output: VoiceOutput | null
  state: VoiceState
  startedAt: string
  completedAt: string | null
  durationMs: number | null
  activities: VoiceActivity[]
  interrupted: boolean
  interruptionReason?: string
}

export interface VoiceStream {
  id: string
  sessionId: string
  turnId: string | null
  type: VoiceStreamType
  format: string
  encoding: string
  sampleRate: number
  channels: number
  state: VoiceStreamState
  startedAt: string
  completedAt: string | null
  durationMs: number | null
  livekitTrackSid?: string
  chunkCount: number
  totalBytes: number
}

export interface VoiceInput {
  transcript: string
  confidence: number
  language: string
  isFinal: boolean
  streamId: string | null
  startTime: string
  endTime: string
  durationMs: number
  words?: VoiceWord[]
  channelIndex?: number
  speechFinal?: boolean
}

export interface VoiceWord {
  word: string
  start: number
  end: number
  confidence: number
  speaker?: number
}

export interface VoiceOutput {
  text: string
  streamId: string | null
  startTime: string
  endTime: string
  durationMs: number
  interrupted: boolean
  characterCount?: number
  audioDurationMs?: number
}

export interface VoiceActivity {
  id: string
  sessionId: string
  turnId: string | null
  type: VoiceActivityType
  startedAt: string
  completedAt: string | null
  durationMs: number | null
  metadata: Record<string, string>
}

export interface VoiceConfiguration {
  sampleRate: number
  encoding: string
  channels: number
  language: string
  inputTimeoutMs: number
  silenceTimeoutMs: number
  maxTurnDurationMs: number
  maxSessionDurationMs: number
  maxConcurrentSessions: number
  features: Record<string, boolean>
  limits: Record<string, number>
}

export interface LiveKitConfig {
  url: string
  apiKey: string
  apiSecret: string
  reconnectAttempts?: number
  reconnectIntervalMs?: number
}

export interface DeepgramConfig {
  apiKey: string
  model?: string
  language?: string
  punctuate?: boolean
  interimResults?: boolean
  endpointing?: number
  vadEvents?: boolean
  encoding?: string
  sampleRate?: number
  channels?: number
}

export interface ElevenLabsConfig {
  apiKey: string
  voiceId?: string
  modelId?: string
  stability?: number
  similarityBoost?: number
  style?: number
  useSpeakerBoost?: boolean
  streaming?: boolean
}

export interface VoiceWorkerConfig {
  maxInputTimeoutMs: number
  maxOutputTimeoutMs: number
  defaultLanguage: string
  defaultSampleRate: number
  defaultEncoding: string
  defaultChannels: number
  policies: VoicePolicy[]
  livekit?: LiveKitConfig
  deepgram?: DeepgramConfig
  elevenlabs?: ElevenLabsConfig
}

export interface VoiceMetrics {
  workerId: string
  totalSessions: number
  activeSessions: number
  totalTurns: number
  totalStreams: number
  totalActivities: number
  totalErrors: number
  averageTurnDurationMs: number
  averageInputDurationMs: number
  averageOutputDurationMs: number
  uptimeMs: number
  collectedAt: string
  totalConnections: number
  totalReconnects: number
  totalInterruptions: number
  totalWordsTranscribed: number
  totalCharactersSynthesized: number
  averageSTTDurationMs: number
  averageTTSDurationMs: number
}

export interface VoicePolicy {
  id: string
  name: string
  description: string
  effect: VoicePolicyEffect
  actions: string[]
  conditions: Record<string, unknown>
  priority: number
  enabled: boolean
}

export type VoiceTaskPayload =
  | { type: "process_input"; sessionId: string; input: VoiceInput }
  | { type: "generate_output"; sessionId: string; turnId: string; text: string }
  | { type: "manage_stream"; sessionId: string; streamId: string; action: "open" | "close" }
  | { type: "control_session"; sessionId: string; action: "pause" | "resume" | "stop" }
  | { type: "join_room"; sessionId: string; roomName: string; identity: string }
  | { type: "leave_room"; sessionId: string }
  | { type: "start_listening"; sessionId: string }
  | { type: "stop_listening"; sessionId: string }
  | { type: "start_speaking"; sessionId: string; turnId: string; text: string }
  | { type: "stop_speaking"; sessionId: string }
