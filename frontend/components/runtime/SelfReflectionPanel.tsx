"use client"

import {
    useEffect,
    useMemo,
    useState
} from "react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// REFLECTION EVENT
// ==========================================

interface ReflectionEvent {

    agent: string

    message: string

    timestamp: string

    retryCount?: number

    confidenceScore?: number

    hallucinationScore?: number

    governanceStatus?: string

    status: string

    phase?: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function SelfReflectionPanel() {

    const [

        reflections,

        setReflections

    ] = useState<
        ReflectionEvent[]
    >([])


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            // ==========================================
            // FILTER REFLECTION EVENTS
            // ==========================================

            const isReflectionEvent = (

                event.phase ===
                "self_reflection"

                ||

                event.event_type ===
                "autonomous_retry"

                ||

                event.agent ===
                "critic"
            )

            if (!isReflectionEvent) {

                return
            }

            setReflections(

                (previous) => [

                    {

                        agent:
                            event.agent,

                        message:
                            event.message,

                        timestamp:
                            event.timestamp,

                        retryCount:
                            event.retry_count,

                        confidenceScore:
                            event.confidence_score,

                        hallucinationScore:
                            event.hallucination_score,

                        governanceStatus:
                            event.governance_status,

                        status:
                            event.status,

                        phase:
                            event.phase
                    },

                    ...previous
                ]
            )
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
    // SORTED EVENTS
    // ==========================================

    const reflectionList = useMemo(() => {

        return reflections

    }, [reflections])


    // ==========================================
    // STATUS COLORS
    // ==========================================

    const getStatusColor = (
        status: string
    ) => {

        if (status === "running") {

            return (
                "bg-yellow-100 text-yellow-700"
            )
        }

        if (status === "completed") {

            return (
                "bg-green-100 text-green-700"
            )
        }

        if (status === "failed") {

            return (
                "bg-red-100 text-red-700"
            )
        }

        return (
            "bg-gray-100 text-gray-700"
        )
    }


    // ==========================================
    // SCORE COLOR
    // ==========================================

    const getConfidenceColor = (
        score?: number
    ) => {

        if (score === undefined) {

            return (
                "text-gray-500"
            )
        }

        if (score >= 0.8) {

            return (
                "text-green-600"
            )
        }

        if (score >= 0.5) {

            return (
                "text-yellow-600"
            )
        }

        return (
            "text-red-600"
        )
    }


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="
                bg-white
                border
                border-gray-200
                rounded-2xl
                shadow-sm
                overflow-hidden
            "
        >

            {/* HEADER */}

            <div
                className="
                    p-5
                    border-b
                    border-gray-200
                "
            >

                <h2
                    className="
                        text-2xl
                        font-black
                    "
                >

                    🧠 Autonomous Self-Reflection

                </h2>

                <p
                    className="
                        text-gray-500
                        mt-1
                    "
                >

                    Live cognitive evaluation and retry engine

                </p>

            </div>


            {/* REFLECTION STREAM */}

            <div
                className="
                    p-5
                    space-y-5
                    max-h-150
                    overflow-y-auto
                    bg-gray-50
                "
            >

                {

                    reflectionList.length === 0 ? (

                        <div
                            className="
                                text-sm
                                text-gray-400
                            "
                        >

                            Waiting for autonomous cognition...

                        </div>

                    ) : (

                        reflectionList.map(

                            (
                                reflection,
                                index
                            ) => (

                                <div

                                    key={index}

                                    className="
                                        bg-white
                                        border
                                        border-gray-200
                                        rounded-2xl
                                        p-5
                                        shadow-sm
                                    "
                                >

                                    {/* TOP */}

                                    <div
                                        className="
                                            flex
                                            items-center
                                            justify-between
                                            gap-4
                                        "
                                    >

                                        <div>

                                            <div
                                                className="
                                                    font-bold
                                                    text-base
                                                "
                                            >

                                                {

                                                    reflection.agent
                                                }

                                            </div>

                                            {

                                                reflection.phase && (

                                                    <div
                                                        className="
                                                            text-xs
                                                            text-gray-500
                                                            mt-1
                                                        "
                                                    >

                                                        {

                                                            reflection.phase
                                                        }

                                                    </div>
                                                )
                                            }

                                        </div>

                                        <div
                                            className={`

                                                px-3
                                                py-1
                                                rounded-full
                                                text-xs
                                                font-bold

                                                ${getStatusColor(
                                                    reflection.status
                                                )}

                                            `}
                                        >

                                            {

                                                reflection.status
                                            }

                                        </div>

                                    </div>


                                    {/* MESSAGE */}

                                    <div
                                        className="
                                            mt-4
                                            text-sm
                                            text-gray-700
                                            leading-7
                                        "
                                    >

                                        {

                                            reflection.message
                                        }

                                    </div>


                                    {/* METRICS */}

                                    <div
                                        className="
                                            mt-5
                                            grid
                                            grid-cols-2
                                            gap-4
                                            text-sm
                                        "
                                    >

                                        {/* RETRIES */}

                                        <div
                                            className="
                                                bg-gray-50
                                                rounded-xl
                                                p-3
                                            "
                                        >

                                            <div
                                                className="
                                                    text-gray-500
                                                    text-xs
                                                    uppercase
                                                    font-bold
                                                "
                                            >

                                                Retry Count

                                            </div>

                                            <div
                                                className="
                                                    mt-2
                                                    font-bold
                                                    text-lg
                                                "
                                            >

                                                {

                                                    reflection.retryCount
                                                    ?? 0
                                                }

                                            </div>

                                        </div>


                                        {/* CONFIDENCE */}

                                        <div
                                            className="
                                                bg-gray-50
                                                rounded-xl
                                                p-3
                                            "
                                        >

                                            <div
                                                className="
                                                    text-gray-500
                                                    text-xs
                                                    uppercase
                                                    font-bold
                                                "
                                            >

                                                Confidence

                                            </div>

                                            <div
                                                className={`

                                                    mt-2
                                                    font-bold
                                                    text-lg

                                                    ${getConfidenceColor(
                                                        reflection
                                                        .confidenceScore
                                                    )}

                                                `}
                                            >

                                                {

                                                    reflection
                                                    .confidenceScore
                                                    ?.toFixed(2)

                                                    ||

                                                    "N/A"
                                                }

                                            </div>

                                        </div>

                                    </div>


                                    {/* GOVERNANCE */}

                                    {

                                        reflection.governanceStatus && (

                                            <div
                                                className="
                                                    mt-4
                                                    text-xs
                                                    text-gray-500
                                                "
                                            >

                                                Governance:
                                                {" "}

                                                <span
                                                    className="
                                                        font-bold
                                                    "
                                                >

                                                    {

                                                        reflection
                                                        .governanceStatus
                                                    }

                                                </span>

                                            </div>
                                        )
                                    }


                                    {/* TIMESTAMP */}

                                    <div
                                        className="
                                            mt-4
                                            text-xs
                                            text-gray-400
                                        "
                                    >

                                        {

                                            reflection.timestamp
                                        }

                                    </div>

                                </div>
                            )
                        )
                    )
                }

            </div>

        </div>
    )
}