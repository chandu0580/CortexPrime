"use client"

import {
    useEffect,
    useState
} from "react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// METRICS INTERFACE
// ==========================================

interface RuntimeMetrics {

    runtime_started_at?: string

    last_updated?: string

    total_executions?: number

    active_executions?: number

    completed_executions?: number

    failed_executions?: number

    active_agents?: string[]

    active_agent_count?: number

    total_tokens?: number

    prompt_tokens?: number

    completion_tokens?: number

    average_latency_ms?: number

    average_hallucination_score?: number

    average_confidence_score?: number
}


// ==========================================
// COMPONENT
// ==========================================

export default function RuntimeMetricsPanel() {

    const [metrics, setMetrics] =
        useState<RuntimeMetrics>({})


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            if (

                event.event_type ===
                "runtime_metrics"
            ) {

                setMetrics(
                    event.payload || {}
                )
            }
        }

        websocketService.subscribe(
            handleEvent
        )

        return () => {

            websocketService.unsubscribe(
                handleEvent
            )
        }

    }, [])


    // ==========================================
    // METRIC CARD
    // ==========================================

    const MetricCard = (

        title: string,

        value: any,

        color: string
    ) => (

        <div
            className="
                bg-white
                rounded-2xl
                border
                border-gray-200
                shadow-sm
                p-5
            "
        >

            <div
                className="
                    text-sm
                    text-gray-500
                "
            >

                {title}

            </div>

            <div
                className={`

                    text-3xl
                    font-black
                    mt-2

                    ${color}

                `}
            >

                {value}

            </div>

        </div>
    )


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="
                space-y-6
            "
        >

            {/* HEADER */}

            <div>

                <h2
                    className="
                        text-3xl
                        font-black
                    "
                >

                    📊 Runtime Observatory

                </h2>

                <p
                    className="
                        text-gray-500
                        mt-1
                    "
                >

                    Live enterprise cognitive telemetry

                </p>

            </div>


            {/* GRID */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-2
                    xl:grid-cols-4
                    gap-4
                "
            >

                {

                    MetricCard(

                        "Total Executions",

                        metrics.total_executions || 0,

                        "text-blue-600"
                    )
                }

                {

                    MetricCard(

                        "Active Executions",

                        metrics.active_executions || 0,

                        "text-yellow-500"
                    )
                }

                {

                    MetricCard(

                        "Completed",

                        metrics.completed_executions || 0,

                        "text-green-600"
                    )
                }

                {

                    MetricCard(

                        "Failed",

                        metrics.failed_executions || 0,

                        "text-red-500"
                    )
                }

                {

                    MetricCard(

                        "Total Tokens",

                        metrics.total_tokens || 0,

                        "text-[#82c0a4]"
                    )
                }

                {

                    MetricCard(

                        "Prompt Tokens",

                        metrics.prompt_tokens || 0,

                        "text-indigo-500"
                    )
                }

                {

                    MetricCard(

                        "Completion Tokens",

                        metrics.completion_tokens || 0,

                        "text-pink-500"
                    )
                }

                {

                    MetricCard(

                        "Avg Latency",

                        `${

                            metrics.average_latency_ms || 0

                        } ms`,

                        "text-orange-500"
                    )
                }

                {

                    MetricCard(

                        "Hallucination",

                        metrics.average_hallucination_score || 0,

                        "text-red-400"
                    )
                }

                {

                    MetricCard(

                        "Confidence",

                        metrics.average_confidence_score || 0,

                        "text-emerald-600"
                    )
                }

                {

                    MetricCard(

                        "Active Agents",

                        metrics.active_agent_count || 0,

                        "text-[#4a8c70]"
                    )
                }

            </div>


            {/* ACTIVE AGENTS */}

            <div
                className="
                    bg-white
                    border
                    border-gray-200
                    rounded-2xl
                    p-5
                    shadow-sm
                "
            >

                <div
                    className="
                        font-bold
                        text-lg
                        mb-4
                    "
                >

                    ⚡ Active Cognitive Agents

                </div>

                <div
                    className="
                        flex
                        flex-wrap
                        gap-3
                    "
                >

                    {

                        metrics.active_agents?.map(

                            (
                                agent,
                                index
                            ) => (

                                <div

                                    key={index}

                                    className="
                                        px-4
                                        py-2
                                        rounded-full
                                        bg-blue-100
                                        text-blue-700
                                        font-semibold
                                        text-sm
                                    "
                                >

                                    {agent}

                                </div>
                            )
                        )
                    }

                </div>

            </div>

        </div>
    )
}