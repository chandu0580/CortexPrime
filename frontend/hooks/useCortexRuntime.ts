"use client"
import { useEffect, useRef, useState } from "react"
import { wsService } from "@/services/websocket"
import { WS_URL, apiUrl } from "@/lib/constants"
import { useCognitionStore } from "@/store/cognitionStore"
import { useRuntimeStore } from "@/store/runtimeStore"
import { useMissionStore } from "@/store/missionStore"
import type { WSMessage } from "@/types/websocket"
import type { CognitionEvent } from "@/types/cognition"
import type { TelemetryPoint } from "@/store/runtimeStore"
import type { WSStatus } from "@/types/websocket"

// ==========================================
// SIMULATION EVENT POOL
// ==========================================

const SIM_EVENTS: Array<{
    agent:      string
    message:    string
    event_type: string
    status:     string
}> = [
    { agent: "orchestrator", message: "Initializing multi-agent cognitive pipeline",               event_type: "orchestration", status: "info"    },
    { agent: "planner",      message: "Decomposing mission objective into executable subtasks",     event_type: "planning",      status: "info"    },
    { agent: "research",     message: "Querying knowledge base across 847 semantic clusters",       event_type: "research",      status: "info"    },
    { agent: "critic",       message: "Evaluating output quality — confidence: 0.94",              event_type: "validation",    status: "success" },
    { agent: "optimizer",    message: "Applying token efficiency optimization strategy",            event_type: "optimization",  status: "info"    },
    { agent: "memory",       message: "Episodic memory synchronized — 1,204 concepts indexed",     event_type: "memory",        status: "success" },
    { agent: "orchestrator", message: "Agent coordination mesh established — 6 nodes active",      event_type: "orchestration", status: "success" },
    { agent: "planner",      message: "Task dependency graph: 6 nodes, 9 edges constructed",       event_type: "planning",      status: "success" },
    { agent: "research",     message: "Retrieved 14 relevant knowledge sources",                   event_type: "research",      status: "success" },
    { agent: "critic",       message: "Running cross-agent validation pass",                       event_type: "validation",    status: "info"    },
    { agent: "memory",       message: "Reflection cycle complete — 3 new insights stored",         event_type: "reflection",    status: "success" },
    { agent: "optimizer",    message: "Token efficiency improved 18% — latency 340ms→127ms",       event_type: "optimization",  status: "success" },
    { agent: "orchestrator", message: "Spawning parallel execution branches for research phase",   event_type: "orchestration", status: "info"    },
    { agent: "planner",      message: "Adapting strategy based on real-time research findings",    event_type: "planning",      status: "info"    },
    { agent: "research",     message: "Deep-crawling 3 external knowledge repositories",           event_type: "research",      status: "info"    },
    { agent: "critic",       message: "Hallucination check passed — all 23 claims verified",       event_type: "validation",    status: "success" },
    { agent: "memory",       message: "Short-term context buffer at 87% capacity",                 event_type: "memory",        status: "warning" },
    { agent: "optimizer",    message: "Embedding similarity threshold calibrated to 0.82",         event_type: "optimization",  status: "info"    },
    { agent: "orchestrator", message: "Mission scope validated against governance policy",         event_type: "orchestration", status: "success" },
    { agent: "planner",      message: "Contingency branches prepared for execution phase",         event_type: "planning",      status: "success" },
    { agent: "research",     message: "Cross-referencing findings across 3 knowledge domains",     event_type: "research",      status: "info"    },
    { agent: "critic",       message: "Confidence threshold maintained at 0.91",                   event_type: "validation",    status: "success" },
    { agent: "memory",       message: "Vector index rebuilt — 5,632 embeddings active",            event_type: "memory",        status: "success" },
    { agent: "optimizer",    message: "Reasoning chain compressed without information loss",       event_type: "optimization",  status: "success" },
    { agent: "orchestrator", message: "Initiating mission reflection and synthesis phase",         event_type: "orchestration", status: "info"    },
    { agent: "planner",      message: "Evaluating mission completion criteria",                    event_type: "planning",      status: "info"    },
    { agent: "research",     message: "Final knowledge consolidation pass initiated",              event_type: "research",      status: "info"    },
    { agent: "critic",       message: "Post-execution audit complete — all objectives met",        event_type: "validation",    status: "success" },
]

const DEMO_GOAL = "Analyze AGI safety frameworks and synthesize a comprehensive risk assessment"

// ==========================================
// USE CORTEX RUNTIME
// ==========================================

export function useCortexRuntime() {
    const [wsStatus, setWsStatus] = useState<WSStatus>("connecting")

    // Zustand store selectors — stable function refs in Zustand v5
    const addEvent          = useCognitionStore((s) => s.addEvent)
    const updateAgentNode   = useCognitionStore((s) => s.updateAgentNode)
    const appendStream      = useCognitionStore((s) => s.appendStream)
    const finalizeStream    = useCognitionStore((s) => s.finalizeStream)

    const addTelemetryPoint      = useRuntimeStore((s) => s.addTelemetryPoint)
    const setAgentActivity       = useRuntimeStore((s) => s.setAgentActivity)
    const incrementEvents        = useRuntimeStore((s) => s.incrementEvents)
    const setWebsocketConnected  = useRuntimeStore((s) => s.setWebsocketConnected)
    const setLatency             = useRuntimeStore((s) => s.setLatency)
    const setIsDemoMode          = useRuntimeStore((s) => s.setIsDemoMode)
    const setRuntimeStatus       = useRuntimeStore((s) => s.setRuntimeStatus)

    const advanceStage   = useMissionStore((s) => s.advanceStage)
    const advanceStageTo = useMissionStore((s) => s.advanceStageTo)
    const startMission   = useMissionStore((s) => s.startMission)
    const completeMission = useMissionStore((s) => s.completeMission)
    const missionStage   = useMissionStore((s) => s.stage)
    const missionGoal    = useMissionStore((s) => s.goal)

    // Keep stable refs for use inside intervals
    const R = useRef({
        addEvent, updateAgentNode, appendStream, finalizeStream,
        addTelemetryPoint, setAgentActivity, incrementEvents,
        setWebsocketConnected, setLatency, setIsDemoMode, setRuntimeStatus,
        advanceStage, advanceStageTo,
        startMission, completeMission,
        missionStage, missionGoal,
    })
    useEffect(() => {
        R.current = {
            addEvent, updateAgentNode, appendStream, finalizeStream,
            addTelemetryPoint, setAgentActivity, incrementEvents,
            setWebsocketConnected, setLatency, setIsDemoMode, setRuntimeStatus,
            advanceStage, advanceStageTo,
            startMission, completeMission,
            missionStage, missionGoal,
        }
    })

    // ── WebSocket connection ────────────────────────────────────────────────
    useEffect(() => {
        wsService.connect(WS_URL)

        const unsub = wsService.subscribe((msg: WSMessage) => {
            if (msg.agent && msg.event_type) {
                const event: CognitionEvent = {
                    agent:      msg.agent as string,
                    event_type: msg.event_type as string,
                    status:     (msg.status as string)    ?? "info",
                    message:    (msg.message as string)   ?? "",
                    timestamp:  (msg.timestamp as string) ?? new Date().toISOString(),
                }
                R.current.addEvent(event)
                const agentId = (msg.agent as string).toLowerCase()
                if (msg.event_type !== "stream_chunk" && msg.event_type !== "stream_completed") {
                    R.current.setAgentActivity(agentId, "active", event.message)
                    R.current.updateAgentNode(agentId, { status: "active" })
                    R.current.incrementEvents()
                    // Wire real latency from backend events
                    if (typeof msg.latency_ms === "number" && msg.latency_ms > 0) {
                        R.current.setLatency(`${Math.round(msg.latency_ms as number)}ms`)
                    }
                }

                // ── Map backend event_type → mission stage advances ──────
                const et = msg.event_type as string
                if (et === "mission_created") {
                    const goal = (msg.payload as Record<string, string> | undefined)?.objective
                        ?? (msg.message as string ?? "")
                    R.current.startMission(goal)
                } else if (et === "planning_started" || et === "planning_completed") {
                    R.current.advanceStageTo("planning")
                } else if (et === "research_started" || et === "research_completed") {
                    R.current.advanceStageTo("researching")
                } else if (et === "critic_started" || et === "critic_completed") {
                    R.current.advanceStageTo("executing")
                } else if (et === "generating_response") {
                    R.current.advanceStageTo("validating")
                } else if (et === "memory_updated" || et === "context_built") {
                    R.current.advanceStageTo("reflecting")
                } else if (et === "mission_completed") {
                    R.current.completeMission()
                }

                // ── Memory-phase events → emit cognition events to UI ─────
                if (et === "memory_retrieval_started") {
                    R.current.addEvent({
                        agent:      "memory",
                        event_type: "memory",
                        status:     "info",
                        message:    "Retrieving relevant memories for mission context…",
                        timestamp:  new Date().toISOString(),
                    })
                } else if (et === "memory_retrieved") {
                    const count = (msg.payload as Record<string, number> | undefined)?.count ?? 0
                    R.current.addEvent({
                        agent:      "memory",
                        event_type: "memory",
                        status:     "success",
                        message:    `Retrieved ${count} memory entries`,
                        timestamp:  new Date().toISOString(),
                    })
                } else if (et === "memory_ranked") {
                    const ep = (msg.payload as Record<string, number> | undefined)?.episodic ?? 0
                    const sem = (msg.payload as Record<string, number> | undefined)?.semantic ?? 0
                    const ref = (msg.payload as Record<string, number> | undefined)?.reflections ?? 0
                    R.current.addEvent({
                        agent:      "memory",
                        event_type: "memory",
                        status:     "info",
                        message:    `Memory ranked — ${ep} episodic · ${sem} semantic · ${ref} reflections`,
                        timestamp:  new Date().toISOString(),
                    })
                } else if (et === "reflection_loaded") {
                    const count = (msg.payload as Record<string, number> | undefined)?.count ?? 0
                    R.current.addEvent({
                        agent:      "memory",
                        event_type: "reflection",
                        status:     "info",
                        message:    `Loaded ${count} past reflection${count !== 1 ? "s" : ""} for context`,
                        timestamp:  new Date().toISOString(),
                    })
                } else if (et === "context_built") {
                    const tokens = (msg.payload as Record<string, number> | undefined)?.tokens ?? 0
                    R.current.addEvent({
                        agent:      "memory",
                        event_type: "memory",
                        status:     "success",
                        message:    `Context assembled — ${tokens} tokens injected into agents`,
                        timestamp:  new Date().toISOString(),
                    })
                }
            }
            if (msg.stream_chunk)     R.current.appendStream(msg.stream_chunk as string)
            if (msg.stream_completed) R.current.finalizeStream()
        })

        const statusTimer = setInterval(() => {
            const connected = wsService.connected
            const st: WSStatus = connected ? "connected" : "disconnected"
            setWsStatus(st)
            R.current.setWebsocketConnected(connected)
            if (connected) {
                R.current.setIsDemoMode(false)
                R.current.setRuntimeStatus("live")
            }
        }, 1500)

        return () => {
            clearInterval(statusTimer)
            unsub()
            wsService.disconnect()
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    // ── Simulation engine — keeps UI alive regardless of WS ────────────────
    const simIndexRef    = useRef(0)
    const telTickRef     = useRef(0)
    const missionTickRef = useRef(0)
    const agentRevertTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>())

    useEffect(() => {
        // Boot demo mission on first render
        setTimeout(() => {
            R.current.startMission(DEMO_GOAL)
        }, 800)

        // ── Cognition events ────────────────────────────────────────────────
        const eventTimer = setInterval(() => {
            const template = SIM_EVENTS[simIndexRef.current % SIM_EVENTS.length]
            simIndexRef.current++

            R.current.addEvent({
                ...template,
                event_id:  `sim-${Date.now()}`,
                timestamp: new Date().toISOString(),
            })

            R.current.setAgentActivity(template.agent, "active", template.message)
            R.current.updateAgentNode(template.agent, { status: "active" })
            R.current.incrementEvents()

            // Revert agent to idle after a realistic delay
            const existing = agentRevertTimers.current.get(template.agent)
            if (existing) clearTimeout(existing)
            const revert = setTimeout(() => {
                R.current.setAgentActivity(template.agent, "idle")
                R.current.updateAgentNode(template.agent, { status: "idle" })
            }, 1600 + Math.random() * 1200)
            agentRevertTimers.current.set(template.agent, revert)

        }, 2600 + Math.random() * 1000)

        // ── Telemetry: poll real backend every 3s, fall back to simulation ──
        let telFailed = 0
        const telTimer = setInterval(async () => {
            try {
                const res = await fetch(apiUrl("/api/telemetry/runtime"), { credentials: "include" })
                if (!res.ok) throw new Error(`HTTP ${res.status}`)
                const data = await res.json() as {
                    active_agents?:     number
                    queue_depth?:       number
                    total_completed?:   number
                }
                telFailed = 0
                const t = ++telTickRef.current
                // Derive synthetic throughput/latency from real active_agents count
                const agentLoad   = (data.active_agents ?? 0) * 18
                const throughput  = Math.max(20, Math.min(145, 60 + agentLoad + (Math.random() - 0.5) * 12))
                const latency     = Math.max(45, Math.min(360, 120 + agentLoad * 2 + (Math.random() - 0.5) * 20))
                const point: TelemetryPoint = {
                    t,
                    throughput: Math.round(throughput),
                    latency:    Math.round(latency),
                    eventRate:  (data.active_agents ?? 0) + Math.round(Math.random() * 4),
                }
                R.current.addTelemetryPoint(point)
                R.current.setLatency(`${Math.round(latency)}ms`)
            } catch {
                telFailed++
                // After 2 consecutive failures, fall back to simulation
                if (telFailed >= 2) {
                    const t = ++telTickRef.current
                    const throughput = Math.max(20, Math.min(145, 68 + Math.sin(t * 0.38) * 28 + (Math.random() - 0.5) * 16))
                    const latency    = Math.max(45, Math.min(360, 138 + Math.sin(t * 0.29) * 62 + (Math.random() - 0.5) * 18))
                    R.current.addTelemetryPoint({ t, throughput: Math.round(throughput), latency: Math.round(latency), eventRate: Math.round(4 + Math.random() * 14) })
                    R.current.setLatency(`${Math.round(latency)}ms`)
                }
            }
        }, 3000)

        // ── Mission stage advancement every ~22s ──────────────────────────
        const missionTimer = setInterval(() => {
            missionTickRef.current++
            if (R.current.missionStage !== "idle" && R.current.missionStage !== "completed") {
                R.current.advanceStage()
            } else if (R.current.missionStage === "completed") {
                // Restart with same goal after a pause
                setTimeout(() => R.current.startMission(DEMO_GOAL), 3000)
            }
        }, 22000)

        return () => {
            clearInterval(eventTimer)
            clearInterval(telTimer)
            clearInterval(missionTimer)
            agentRevertTimers.current.forEach((t) => clearTimeout(t))
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])

    return { wsStatus }
}
