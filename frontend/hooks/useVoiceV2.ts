"use client"

/**
 * useVoiceV2 — manages a CortexPrime LiveKit voice session with automatic
 * reconnection and conversation recovery.
 *
 * Normal flow:
 *  1. startSession()  → POST /api/voice/v2/session  → token + room
 *  2. connect()       → Room.connect(livekitUrl, token) → WebRTC established
 *  3. enableMic()     → LocalTrack published → Deepgram transcribes
 *  4. Agent speaks    → RemoteAudioTrack plays in browser automatically
 *  5. endSession()    → Room.disconnect() + DELETE /api/voice/v2/session/{id}
 *
 * Recovery flow (on unexpected disconnect):
 *  1. ConnectionStateChanged → Disconnected fires
 *  2. Status → "recovering"; reconnect timer starts
 *  3. POST /api/voice/v2/session/reconnect → new token for same session
 *  4. Room.connect() with new token + exponential backoff (1s → 2s → 4s … 32s)
 *  5. On success: GET /api/voice/v2/session/{id}/history → restore transcripts
 *  6. Status → "recovered"; telemetry updated
 *  7. After MAX_RECONNECT_ATTEMPTS: status → "failed"
 */

import { useCallback, useEffect, useRef } from "react"
import {
    Room,
    RoomEvent,
    Participant,
    RemoteParticipant,
    Track,
    TrackPublication,
    ConnectionState,
    createLocalAudioTrack,
} from "livekit-client"
import { apiUrl } from "@/lib/constants"
import { useVoiceStore } from "@/store/voiceStore"

// ── Reconnect policy ──────────────────────────────────────────────────────────
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_BASE_DELAY_MS = 1000   // doubles each attempt: 1s, 2s, 4s, 8s, 16s

interface StartSessionOptions {
    identity:     string
    workspaceId?: string
    displayName?: string
}

export function useVoiceV2() {
    const roomRef             = useRef<Room | null>(null)
    const reconnectAttemptRef = useRef(0)
    const reconnectTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null)
    const disconnectTimeRef   = useRef<number | null>(null)
    // Keep a stable copy of reconnect options so the backoff loop can re-use them
    const reconnectOptsRef    = useRef<{
        sessionId:   string
        livekitUrl:  string
        identity:    string
        workspaceId: string | null
    } | null>(null)

    const {
        status, v2Session,
        roomConnected, agentConnected, isMuted, transcripts, errorMessage,
        setStatus, setV2Session, setRoomConnected, setAgentConnected,
        setMuted, setError, addTranscript, resetV2,
        recordDisconnect, recordReconnect, recordFailedAttempt,
    } = useVoiceStore()

    // ── Helper: authenticated fetch ──────────────────────────────────────────
    const apiFetch = useCallback(async (path: string, opts?: RequestInit) => {
        const headers: HeadersInit = {
            "Content-Type": "application/json",
            ...(opts?.headers ?? {}),
        }
        const res = await fetch(apiUrl(path), { ...opts, headers, credentials: "include" })
        if (!res.ok) {
            const body = await res.text()
            throw new Error(`${res.status} ${body}`)
        }
        return res.json()
    }, [])

    // ── Clear any pending reconnect timer ────────────────────────────────────
    const _clearReconnectTimer = useCallback(() => {
        if (reconnectTimerRef.current !== null) {
            clearTimeout(reconnectTimerRef.current)
            reconnectTimerRef.current = null
        }
    }, [])

    // ── Fetch and restore transcript history ─────────────────────────────────
    const fetchHistory = useCallback(async (sessionId: string) => {
        try {
            const data = await apiFetch(`/api/voice/v2/session/${sessionId}/history`)
            if (data.history && Array.isArray(data.history)) {
                for (const turn of data.history) {
                    addTranscript({
                        id:        crypto.randomUUID(),
                        text:      turn.text ?? "",
                        speaker:   turn.role === "assistant" ? "assistant" : "user",
                        timestamp: turn.timestamp
                            ? new Date(turn.timestamp * 1000).toISOString()
                            : new Date().toISOString(),
                        isFinal:   true,
                    })
                }
            }
            return data
        } catch {
            return null
        }
    }, [apiFetch, addTranscript])

    // ── Connect to a LiveKit room (shared by start + reconnect) ──────────────
    const _connectRoom = useCallback(async (
        livekitUrl: string,
        token:      string,
        sessionId:  string,
    ) => {
        const room = new Room({
            audioCaptureDefaults: {
                autoGainControl:  true,
                echoCancellation: true,
                noiseSuppression: true,
            },
            adaptiveStream: true,
            dynacast:       true,
        })
        roomRef.current = room
        _attachRoomEvents(room, sessionId)

        await room.connect(livekitUrl, token)
        setRoomConnected(true)

        const audioTrack = await createLocalAudioTrack({
            echoCancellation: true,
            noiseSuppression: true,
        })
        await room.localParticipant.publishTrack(audioTrack)
    }, [setRoomConnected]) // eslint-disable-line react-hooks/exhaustive-deps

    // ── Reconnect with exponential backoff ───────────────────────────────────
    const _attemptReconnect = useCallback(async () => {
        const opts = reconnectOptsRef.current
        if (!opts) return

        const attempt = reconnectAttemptRef.current + 1
        reconnectAttemptRef.current = attempt

        if (attempt > MAX_RECONNECT_ATTEMPTS) {
            setStatus("failed")
            setError(`Reconnection failed after ${MAX_RECONNECT_ATTEMPTS} attempts.`)
            recordFailedAttempt()
            return
        }

        const delay = RECONNECT_BASE_DELAY_MS * Math.pow(2, attempt - 1)
        recordFailedAttempt()  // counts this pending attempt
        setStatus("recovering")

        reconnectTimerRef.current = setTimeout(async () => {
            try {
                // Ask backend for a fresh token for the existing session
                const data = await apiFetch(
                    `/api/voice/v2/session/${opts.sessionId}/reconnect`,
                    { method: "POST" },
                )

                // Destroy stale room if still attached
                if (roomRef.current) {
                    try { roomRef.current.disconnect(true) } catch { /* ignore */ }
                    roomRef.current = null
                }

                await _connectRoom(data.livekit_url, data.token, opts.sessionId)

                // Restore conversation history
                await fetchHistory(opts.sessionId)

                // Record recovery
                const latencyMs = disconnectTimeRef.current
                    ? Date.now() - disconnectTimeRef.current
                    : 0
                recordReconnect(latencyMs)
                reconnectAttemptRef.current = 0
                setStatus("recovered")

                // After a brief "recovered" flash, settle to listening
                setTimeout(() => {
                    if (useVoiceStore.getState().roomConnected) {
                        setStatus("listening")
                    }
                }, 2500)

            } catch {
                // This attempt failed — schedule the next one
                _attemptReconnect()
            }
        }, delay)
    }, [apiFetch, fetchHistory, _connectRoom, setStatus, setError, recordFailedAttempt, recordReconnect])

    // ── Start session (fresh) ─────────────────────────────────────────────────
    const startSession = useCallback(async (opts: StartSessionOptions) => {
        _clearReconnectTimer()
        reconnectAttemptRef.current = 0
        setStatus("connecting")
        setError(null)

        try {
            const data = await apiFetch("/api/voice/v2/session", {
                method: "POST",
                body: JSON.stringify({
                    identity:     opts.identity,
                    workspace_id: opts.workspaceId ?? null,
                    display_name: opts.displayName ?? opts.identity,
                }),
            })

            setV2Session({
                sessionId:   data.session_id,
                roomName:    data.room_name,
                token:       data.token,
                livekitUrl:  data.livekit_url,
                identity:    data.identity,
                workspaceId: opts.workspaceId ?? null,
            })

            // Store stable opts for reconnect loop
            reconnectOptsRef.current = {
                sessionId:   data.session_id,
                livekitUrl:  data.livekit_url,
                identity:    data.identity,
                workspaceId: opts.workspaceId ?? null,
            }

            await _connectRoom(data.livekit_url, data.token, data.session_id)
            setStatus("listening")

        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            setError(msg)
            setStatus("error")
        }
    }, [apiFetch, _clearReconnectTimer, _connectRoom, setStatus, setError, setV2Session])

    // ── End session (intentional) ─────────────────────────────────────────────
    const endSession = useCallback(async () => {
        _clearReconnectTimer()
        reconnectAttemptRef.current = 0
        reconnectOptsRef.current    = null

        const sessionId = useVoiceStore.getState().v2Session?.sessionId

        if (roomRef.current) {
            await roomRef.current.disconnect(true)
            roomRef.current = null
        }

        if (sessionId) {
            try {
                await apiFetch(`/api/voice/v2/session/${sessionId}`, { method: "DELETE" })
            } catch { /* best-effort */ }
        }

        resetV2()
    }, [apiFetch, _clearReconnectTimer, resetV2])

    // ── Mute / unmute ─────────────────────────────────────────────────────────
    const toggleMute = useCallback(async () => {
        const room = roomRef.current
        if (!room) return
        const nextMuted = !isMuted
        await room.localParticipant.setMicrophoneEnabled(!nextMuted)
        setMuted(nextMuted)
    }, [isMuted, setMuted])

    // ── Room event wiring ────────────────────────────────────────────────────
    // NOTE: defined as a plain function (not useCallback) so it can reference
    // _attemptReconnect without a stale-closure issue.  It is only called from
    // _connectRoom which itself is inside useCallback, so this is stable.
    const _attachRoomEvents = (room: Room, sessionId: string) => {
        room.on(RoomEvent.ConnectionStateChanged, (state: ConnectionState) => {
            if (state === ConnectionState.Disconnected) {
                setRoomConnected(false)
                setAgentConnected(false)

                // Only attempt recovery when we have reconnect options
                // (i.e. this was not an intentional disconnect via endSession)
                if (reconnectOptsRef.current) {
                    disconnectTimeRef.current = Date.now()
                    recordDisconnect()
                    setStatus("recovering")
                    reconnectAttemptRef.current = 0
                    _attemptReconnect()
                } else {
                    setStatus("idle")
                }
            }
            if (state === ConnectionState.Reconnecting) {
                setStatus("recovering")
            }
        })

        room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
            if (participant.identity.startsWith("cortex-agent")) {
                setAgentConnected(true)
            }
        })

        room.on(RoomEvent.ParticipantDisconnected, (participant: RemoteParticipant) => {
            if (participant.identity.startsWith("cortex-agent")) {
                setAgentConnected(false)
            }
        })

        // Auto-play remote audio (agent speech)
        room.on(RoomEvent.TrackSubscribed, (
            track:       Track,
            _publication: TrackPublication,
            _participant: RemoteParticipant,
        ) => {
            if (track.kind === Track.Kind.Audio) {
                const audioEl = track.attach()
                audioEl.autoplay = true
                document.body.appendChild(audioEl)
                room.once(RoomEvent.TrackUnsubscribed, (t: Track) => {
                    if (t === track) audioEl.remove()
                })
            }
        })

        // Detect agent speaking state via data messages
        room.on(RoomEvent.DataReceived, (payload: Uint8Array) => {
            try {
                const msg = JSON.parse(new TextDecoder().decode(payload))
                if (msg.type === "bot_speaking") {
                    setStatus("speaking")
                } else if (msg.type === "bot_stopped") {
                    setStatus("listening")
                } else if (msg.type === "transcript" && msg.text) {
                    addTranscript({
                        id:         crypto.randomUUID(),
                        text:       msg.text,
                        speaker:    msg.role === "assistant" ? "assistant" : "user",
                        timestamp:  new Date().toISOString(),
                        isFinal:    msg.is_final ?? true,
                        confidence: msg.confidence,
                    })
                }
            } catch { /* ignore malformed */ }
        })

        // Detect speaking status from track-level events
        room.on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
            const agentSpeaking = speakers.some(
                (p) => p.identity.startsWith("cortex-agent"),
            )
            if (agentSpeaking) {
                setStatus("speaking")
            } else if (useVoiceStore.getState().roomConnected) {
                setStatus("listening")
            }
        })
    }

    // ── Cleanup on unmount ────────────────────────────────────────────────────
    useEffect(() => {
        return () => {
            _clearReconnectTimer()
            reconnectOptsRef.current = null
            if (roomRef.current) {
                roomRef.current.disconnect(true)
                roomRef.current = null
            }
        }
    }, [_clearReconnectTimer])

    return {
        status,
        v2Session,
        roomConnected,
        agentConnected,
        isMuted,
        transcripts,
        errorMessage,
        recovery: useVoiceStore((s) => s.recovery),
        startSession,
        endSession,
        toggleMute,
        fetchHistory,
    }
}
