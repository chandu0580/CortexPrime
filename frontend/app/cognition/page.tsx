"use client"
import CortexShell from "@/components/layout/CortexShell"
import CognitionStream from "@/components/cognition/CognitionStream"
import AgentActivityFeed from "@/components/cognition/AgentActivityFeed"
import NeuralCore from "@/components/cognition/CognitionPulse"
import ExecutionFlow from "@/components/cognition/ExecutionFlow"
import RuntimeGrid from "@/components/layout/RuntimeGrid"
import AgentGraphV2 from "@/components/runtime/AgentGraphV2"
import { useCortexRuntime } from "@/hooks/useCortexRuntime"
import { useCognitionStore } from "@/store/cognitionStore"

// ==========================================
// NEURAL CORE PAGE  (/cognition)
// ==========================================

export default function CognitionPage() {
    useCortexRuntime()
    const isStreaming = useCognitionStore((s) => s.isStreaming)

    return (
        <CortexShell title="Neural Core" subtitle="Live agent topology & cognition stream">
            <div className="flex flex-col gap-5">

                {/* -- Primary: Neural graph + Agent graph side-by-side -- */}
                <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-5 items-start">

                    {/* Neural topology */}
                    <div
                        className="runtime-card p-5 flex flex-col items-center"
                        style={{ minHeight: 340 }}
                    >
                        <div className="flex items-center justify-between w-full mb-4">
                            <div>
                                <h2 className="text-sm font-semibold text-[#1a1a1a] leading-none">Neural Core</h2>
                                <p className="text-[11px] text-[#a3a3a3] mt-0.5">Agent topology</p>
                            </div>
                            <div
                                className="flex items-center gap-1.5 px-2 py-0.5 rounded-full"
                                style={{
                                    background: isStreaming ? "rgba(74,140,112,0.08)" : "transparent",
                                    border: `1px solid ${isStreaming ? "rgba(74,140,112,0.2)" : "transparent"}`,
                                }}
                            >
                                {isStreaming && (
                                    <div className="w-1.5 h-1.5 rounded-full bg-[#4a8c70] animate-blink" />
                                )}
                                <span className="text-[10px] font-medium text-[#737373]">
                                    {isStreaming ? "Streaming" : "Idle"}
                                </span>
                            </div>
                        </div>
                        <NeuralCore size={220} showLabels />
                    </div>

                    {/* Agent Graph � flagship */}
                    <div className="runtime-card p-4">
                        <div className="flex items-center justify-between mb-3">
                            <div>
                                <h2 className="text-sm font-semibold text-[#1a1a1a] leading-none">Agent Graph</h2>
                                <p className="text-[11px] text-[#a3a3a3] mt-0.5">Live execution topology</p>
                            </div>
                        </div>
                        <AgentGraphV2 />
                    </div>
                </div>

                {/* -- Secondary: Cognition stream + Activity feed -- */}
                <RuntimeGrid cols={2}>
                    <CognitionStream />
                    <AgentActivityFeed />
                </RuntimeGrid>

                {/* -- Execution flow trace -- */}
                <ExecutionFlow />
            </div>
        </CortexShell>
    )
}
