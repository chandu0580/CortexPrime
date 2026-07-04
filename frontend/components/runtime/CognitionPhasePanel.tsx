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
// PHASE EVENT
// ==========================================

interface PhaseEvent {

    agent: string

    phase: string

    timestamp: string

    message: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function CognitionPhasePanel() {

    const [phases, setPhases] =
        useState<PhaseEvent[]>([])


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            if (event.phase) {

                setPhases(

                    (previous) => [

                        {

                            agent:
                                event.agent,

                            phase:
                                event.phase ||
                                "unknown_phase",

                            timestamp:
                                event.timestamp,

                            message:
                                event.message
                        },

                        ...previous
                    ]
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
    // PHASE COLORS
    // ==========================================

    const getPhaseColor = (
        phase: string
    ) => {

        if (
            phase.includes(
                "research"
            )
        ) {

            return (
                "bg-blue-100 text-blue-700"
            )
        }

        if (
            phase.includes(
                "analy"
            )
        ) {

            return (
                "bg-[#e8f5ee] text-[#4a8c70]"
            )
        }

        if (
            phase.includes(
                "stream"
            )
        ) {

            return (
                "bg-orange-100 text-orange-700"
            )
        }

        if (
            phase.includes(
                "synth"
            )
        ) {

            return (
                "bg-[#e8f5ee] text-[#4a8c70]"
            )
        }

        if (
            phase.includes(
                "complete"
            )
        ) {

            return (
                "bg-green-100 text-green-700"
            )
        }

        return (
            "bg-gray-100 text-gray-700"
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
                p-6
            "
        >

            {/* HEADER */}

            <div
                className="
                    mb-6
                "
            >

                <h2
                    className="
                        text-2xl
                        font-black
                    "
                >

                    🧠 Live Cognitive Phases

                </h2>

                <p
                    className="
                        text-gray-500
                        mt-1
                    "
                >

                    Realtime AI reasoning lifecycle

                </p>

            </div>


            {/* PHASE TIMELINE */}

            <div
                className="
                    space-y-4
                    max-h-125
                    overflow-y-auto
                "
            >

                {

                    phases.length === 0 ? (

                        <div
                            className="
                                text-sm
                                text-gray-400
                            "
                        >

                            Waiting for cognition phases...

                        </div>

                    ) : (

                        phases.map(

                            (
                                phase,
                                index
                            ) => (

                                <div

                                    key={index}

                                    className="
                                        flex
                                        gap-4
                                        items-start
                                        border-l-4
                                        border-blue-500
                                        pl-4
                                        py-2
                                    "
                                >

                                    {/* BADGE */}

                                    <div
                                        className={`

                                            px-3
                                            py-1
                                            rounded-full
                                            text-xs
                                            font-bold

                                            ${getPhaseColor(
                                                phase.phase
                                            )}

                                        `}
                                    >

                                        {

                                            phase.phase
                                        }

                                    </div>


                                    {/* CONTENT */}

                                    <div
                                        className="
                                            flex-1
                                        "
                                    >

                                        <div
                                            className="
                                                font-semibold
                                                text-sm
                                            "
                                        >

                                            {

                                                phase.agent
                                            }

                                        </div>

                                        <div
                                            className="
                                                text-gray-700
                                                text-sm
                                                mt-1
                                            "
                                        >

                                            {

                                                phase.message
                                            }

                                        </div>

                                        <div
                                            className="
                                                text-xs
                                                text-gray-400
                                                mt-2
                                            "
                                        >

                                            {

                                                phase.timestamp
                                            }

                                        </div>

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