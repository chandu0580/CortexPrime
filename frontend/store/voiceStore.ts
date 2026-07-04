import { create } from "zustand"
import type { VoiceSession, VoiceStatus, VoiceTranscript, VoiceV2Session, VoiceRecoveryTelemetry, WaveformData } from "@/types/voice"

// ==========================================
// VOICE STORE
// ==========================================

interface VoiceState {
    status:       VoiceStatus
    session:      VoiceSession | null
    transcripts:  VoiceTranscript[]
    waveform:     WaveformData | null
    activeProfile: string
    wakeWordActive: boolean

    // V2 LiveKit state
    v2Session:      VoiceV2Session | null
    roomConnected:  boolean
    agentConnected: boolean
    isMuted:        boolean
    errorMessage:   string | null

    // Recovery telemetry
    recovery: VoiceRecoveryTelemetry

    setStatus:       (status: VoiceStatus) => void
    setSession:      (session: VoiceSession | null) => void
    addTranscript:   (t: VoiceTranscript) => void
    setWaveform:     (w: WaveformData) => void
    setProfile:      (id: string) => void
    setWakeWord:     (active: boolean) => void
    clearTranscripts: () => void

    // V2 actions
    setV2Session:      (s: VoiceV2Session | null) => void
    setRoomConnected:  (v: boolean) => void
    setAgentConnected: (v: boolean) => void
    setMuted:          (v: boolean) => void
    setError:          (msg: string | null) => void
    resetV2:           () => void

    // Recovery actions
    recordDisconnect:  () => void
    recordReconnect:   (latencyMs: number) => void
    recordFailedAttempt: () => void
}

const _initialRecovery: VoiceRecoveryTelemetry = {
    disconnectCount:   0,
    reconnectCount:    0,
    failedAttempts:    0,
    recoveryLatencyMs: null,
    lastDisconnectAt:  null,
    lastRecoveredAt:   null,
}

export const useVoiceStore = create<VoiceState>((set) => ({
    status:         "idle",
    session:        null,
    transcripts:    [],
    waveform:       null,
    activeProfile:  "default",
    wakeWordActive: false,

    v2Session:      null,
    roomConnected:  false,
    agentConnected: false,
    isMuted:        false,
    errorMessage:   null,

    recovery: { ..._initialRecovery },

    setStatus:       (status)  => set({ status }),
    setSession:      (session) => set({ session }),
    addTranscript:   (t)       => set((s) => ({ transcripts: [...s.transcripts, t].slice(-100) })),
    setWaveform:     (w)       => set({ waveform: w }),
    setProfile:      (id)      => set({ activeProfile: id }),
    setWakeWord:     (active)  => set({ wakeWordActive: active }),
    clearTranscripts: ()       => set({ transcripts: [] }),

    setV2Session:      (v2Session)     => set({ v2Session }),
    setRoomConnected:  (roomConnected)  => set({ roomConnected }),
    setAgentConnected: (agentConnected) => set({ agentConnected }),
    setMuted:          (isMuted)        => set({ isMuted }),
    setError:          (errorMessage)   => set({ errorMessage }),
    resetV2: () => set({
        v2Session:      null,
        roomConnected:  false,
        agentConnected: false,
        isMuted:        false,
        errorMessage:   null,
        status:         "idle",
    }),

    recordDisconnect: () => set((s) => ({
        recovery: {
            ...s.recovery,
            disconnectCount:  s.recovery.disconnectCount + 1,
            lastDisconnectAt: new Date().toISOString(),
            recoveryLatencyMs: null,   // reset; will be set on recovery
        },
    })),

    recordReconnect: (latencyMs) => set((s) => ({
        recovery: {
            ...s.recovery,
            reconnectCount:    s.recovery.reconnectCount + 1,
            recoveryLatencyMs: latencyMs,
            lastRecoveredAt:   new Date().toISOString(),
        },
    })),

    recordFailedAttempt: () => set((s) => ({
        recovery: {
            ...s.recovery,
            failedAttempts: s.recovery.failedAttempts + 1,
        },
    })),
}))
