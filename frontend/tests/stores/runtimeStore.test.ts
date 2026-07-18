import { describe, it, expect, beforeEach } from "vitest"
import { useRuntimeStore } from "@/store/runtimeStore"
import type { TelemetryPoint, AgentActivityStatus } from "@/store/runtimeStore"

const INITIAL_STATE = {
    activeAgents: 0,
    memoryUsage: "—",
    runtimeStatus: "connecting",
    websocketConnected: false,
    totalEvents: 0,
    latency: "—",
    telemetry: [],
    cognitionThroughput: 0,
    agentActivity: {
      orchestrator: "idle" as const,
      planner: "idle" as const,
      research: "idle" as const,
      critic: "idle" as const,
      optimizer: "idle" as const,
      memory: "idle" as const,
    },
    agentLastAction: {},
    isDemoMode: true,
  }

  describe("useRuntimeStore", () => {
    beforeEach(() => {
      useRuntimeStore.setState(INITIAL_STATE)
    })

  it("has correct initial state", () => {
    const state = useRuntimeStore.getState()
    expect(state.activeAgents).toBe(0)
    expect(state.runtimeStatus).toBe("connecting")
    expect(state.websocketConnected).toBe(false)
    expect(state.isDemoMode).toBe(true)
    expect(state.memoryUsage).toBe("—")
    expect(state.latency).toBe("—")
    expect(state.totalEvents).toBe(0)
    expect(state.telemetry).toEqual([])
    expect(state.cognitionThroughput).toBe(0)
    expect(Object.keys(state.agentActivity)).toHaveLength(6)
  })

  it("setActiveAgents updates activeAgents", () => {
    useRuntimeStore.getState().setActiveAgents(3)
    expect(useRuntimeStore.getState().activeAgents).toBe(3)
  })

  it("setMemoryUsage updates memoryUsage", () => {
    useRuntimeStore.getState().setMemoryUsage("2.4 GB")
    expect(useRuntimeStore.getState().memoryUsage).toBe("2.4 GB")
  })

  it("setRuntimeStatus updates runtimeStatus", () => {
    useRuntimeStore.getState().setRuntimeStatus("healthy")
    expect(useRuntimeStore.getState().runtimeStatus).toBe("healthy")
  })

  it("setWebsocketConnected updates websocketConnected", () => {
    useRuntimeStore.getState().setWebsocketConnected(true)
    expect(useRuntimeStore.getState().websocketConnected).toBe(true)
  })

  it("incrementEvents increments totalEvents and recalculates activeAgents", () => {
    useRuntimeStore.setState({
      agentActivity: { ...INITIAL_STATE.agentActivity, planner: "active" as const, research: "processing" as const },
    })

    useRuntimeStore.getState().incrementEvents()

    const state = useRuntimeStore.getState()
    expect(state.totalEvents).toBe(1)
    expect(state.activeAgents).toBe(2)
  })

  it("addTelemetryPoint appends point and truncates to 40 max", () => {
    const point: TelemetryPoint = { t: 1, throughput: 1234.567, latency: 42, eventRate: 10 }
    useRuntimeStore.getState().addTelemetryPoint(point)

    const state = useRuntimeStore.getState()
    expect(state.telemetry).toHaveLength(1)
    expect(state.telemetry[0]).toEqual(point)
    expect(state.cognitionThroughput).toBe(1235)

    const points: TelemetryPoint[] = []
    for (let i = 0; i < 50; i++) {
      points.push({ t: i, throughput: i * 100, latency: i, eventRate: i })
    }
    for (const p of points) {
      useRuntimeStore.getState().addTelemetryPoint(p)
    }

    expect(useRuntimeStore.getState().telemetry).toHaveLength(40)
    expect(useRuntimeStore.getState().telemetry[39].t).toBe(49)
    expect(useRuntimeStore.getState().cognitionThroughput).toBe(4900)
  })

  it("setAgentActivity updates agent status and recalculates activeAgents", () => {
    useRuntimeStore.getState().setAgentActivity("planner", "active", "planning mission")

    let state = useRuntimeStore.getState()
    expect(state.agentActivity.planner).toBe("active")
    expect(state.activeAgents).toBe(1)
    expect(state.agentLastAction.planner).toBe("planning mission")

    useRuntimeStore.getState().setAgentActivity("research", "processing", "researching topic")

    state = useRuntimeStore.getState()
    expect(state.agentActivity.research).toBe("processing")
    expect(state.activeAgents).toBe(2)

    useRuntimeStore.getState().setAgentActivity("planner", "done")

    state = useRuntimeStore.getState()
    expect(state.agentActivity.planner).toBe("done")
    expect(state.activeAgents).toBe(1)
  })

  it("setIsDemoMode toggles demo mode", () => {
    useRuntimeStore.getState().setIsDemoMode(false)
    expect(useRuntimeStore.getState().isDemoMode).toBe(false)

    useRuntimeStore.getState().setIsDemoMode(true)
    expect(useRuntimeStore.getState().isDemoMode).toBe(true)
  })

  it("setLatency updates latency", () => {
    useRuntimeStore.getState().setLatency("12ms")
    expect(useRuntimeStore.getState().latency).toBe("12ms")
  })
})
