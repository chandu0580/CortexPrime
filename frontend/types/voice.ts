// ==========================================
// VOICE TYPES
// ==========================================

export type VoiceStatus =
    | "idle"
    | "connecting"
    | "listening"
    | "processing"
    | "speaking"
    | "error"
    | "recovering"   // temporary disconnect — reconnect in progress
    | "recovered"    // reconnect succeeded — conversation restored
    | "failed"       // all reconnect attempts exhausted

export interface VoiceProfile {
    id: string
    name: string
    description: string
    speed?: number
    pitch?: number
}

export interface VoiceTranscript {
    id: string
    text: string
    speaker: "user" | "assistant"
    timestamp: string
    confidence?: number
    isFinal?: boolean
}

export interface WaveformData {
    frequencies: number[]
    amplitude: number
    timestamp: number
}

export interface VoiceSession {
    id: string
    status: VoiceStatus
    wakeWordDetected: boolean
    activeProfile: string
    transcripts: VoiceTranscript[]
    startedAt?: string
}

// ── Voice V2 (LiveKit) ───────────────────────────────

export interface VoiceV2Session {
    sessionId:   string
    roomName:    string
    token:       string
    livekitUrl:  string
    identity:    string
    workspaceId: string | null
}

export interface VoiceV2State {
    v2Session:      VoiceV2Session | null
    roomConnected:  boolean
    agentConnected: boolean
    isMuted:        boolean
    errorMessage:   string | null
}

// Recovery telemetry tracked on the frontend
export interface VoiceRecoveryTelemetry {
    disconnectCount:   number
    reconnectCount:    number
    failedAttempts:    number
    recoveryLatencyMs: number | null   // ms from disconnect to recovered
    lastDisconnectAt:  string | null
    lastRecoveredAt:   string | null
}
