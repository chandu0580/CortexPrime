import { create } from "zustand"
import type { CognitionEvent, AgentNode, AgentEdge, ExecutionTrace } from "@/types/cognition"
import { buildDefaultAgentNodes } from "@/lib/runtimeHelpers"

// ==========================================
// COGNITION STORE
// ==========================================

interface CognitionState {
    events:      CognitionEvent[]
    agentNodes:  AgentNode[]
    agentEdges:  AgentEdge[]
    activeTrace: ExecutionTrace | null
    streamBuffer: string
    isStreaming:  boolean

    addEvent:        (event: CognitionEvent) => void
    clearEvents:     () => void
    updateAgentNode: (id: string, patch: Partial<AgentNode>) => void
    setActiveTrace:  (trace: ExecutionTrace | null) => void
    appendStream:    (chunk: string) => void
    finalizeStream:  () => void
}

export const useCognitionStore = create<CognitionState>((set) => ({
    events:       [],
    agentNodes:   buildDefaultAgentNodes(),
    agentEdges:   [
        { id: "e-orch-plan", source: "orchestrator", target: "planner",    animated: true },
        { id: "e-orch-res",  source: "orchestrator", target: "research",   animated: true },
        { id: "e-orch-crit", source: "orchestrator", target: "critic",     animated: true },
        { id: "e-plan-opt",  source: "planner",      target: "optimizer",  animated: false },
        { id: "e-res-crit",  source: "research",     target: "critic",     animated: false },
        { id: "e-crit-mem",  source: "critic",       target: "memory",     animated: false },
    ],
    activeTrace:  null,
    streamBuffer: "",
    isStreaming:  false,

    addEvent: (event) =>
        set((s) => ({
            events: [event, ...s.events].slice(0, 100),
        })),

    clearEvents: () => set({ events: [] }),

    updateAgentNode: (id, patch) =>
        set((s) => ({
            agentNodes: s.agentNodes.map((n) =>
                n.id === id ? { ...n, ...patch } : n
            ),
        })),

    setActiveTrace: (trace) => set({ activeTrace: trace }),

    appendStream: (chunk) =>
        set((s) => ({
            streamBuffer: s.streamBuffer + chunk,
            isStreaming:  true,
        })),

    finalizeStream: () => set({ isStreaming: false }),
}))
