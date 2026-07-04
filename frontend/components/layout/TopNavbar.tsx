"use client"

import { useRuntimeStore } from "@/store/runtimeStore"


export default function TopNavbar() {

    // ==========================================
    // GLOBAL RUNTIME STATE
    // ==========================================

    const {

        activeAgents,

        memoryUsage,

        runtimeStatus,

        websocketConnected,

        totalEvents,

        latency

    } = useRuntimeStore()

    // ==========================================
    // UI
    // ==========================================

    return (

        <header
            className="h-[80px] bg-white border-b px-8 flex items-center justify-between"
        >

            {/* LEFT */}

            <div>

                <h1
                    className="text-3xl font-bold tracking-tight text-[#1a1a1a]"
                >

                    🧠 CortexPrime Runtime

                </h1>

                <p
                    className="text-sm font-medium text-[#737373]"
                >

                    Enterprise AI Orchestration Platform

                </p>

            </div>

            {/* RIGHT */}

            <div
                className="flex items-center gap-8"
            >

                {/* ACTIVE AGENTS */}

                <div>

                    <div
                        className="text-sm font-medium text-[#737373]"
                    >

                        Active Agents

                    </div>

                    <div
                        className="text-base font-bold text-[#1a1a1a]"
                    >

                        {
                            activeAgents
                        }

                    </div>

                </div>

                {/* MEMORY */}

                <div>

                    <div
                        className="text-sm font-medium text-[#737373]"
                    >

                        Memory Usage

                    </div>

                    <div
                        className="text-base font-bold text-[#1a1a1a]"
                    >

                        {
                            memoryUsage
                        }

                    </div>

                </div>

                {/* EVENTS */}

                <div>

                    <div
                        className="text-sm font-medium text-[#737373]"
                    >

                        Runtime Events

                    </div>

                    <div
                        className="text-base font-bold text-[#1a1a1a]"
                    >

                        {
                            totalEvents
                        }

                    </div>

                </div>

                {/* LATENCY */}

                <div>

                    <div
                        className="text-sm font-medium text-[#737373]"
                    >

                        Latency

                    </div>

                    <div
                        className="text-base font-bold text-[#1a1a1a]"
                    >

                        {
                            latency
                        }

                    </div>

                </div>

                {/* STATUS */}

                <div>

                    <div
                        className="text-sm font-medium text-[#737373]"
                    >

                        Runtime Status

                    </div>

                    <div
                        className={`text-base font-bold ${
                            websocketConnected
                                ? "text-green-600"
                                : "text-red-600"
                        }`}
                    >

                        ● {
                            runtimeStatus
                        }

                    </div>

                </div>

            </div>

        </header>
    )
}