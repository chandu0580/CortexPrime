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
// STREAM STATE
// ==========================================

interface StreamState {

    [executionId: string]: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function CognitionEventPanel() {

    const [events, setEvents] =
        useState<CognitionEvent[]>([])

    const [streams, setStreams] =
        useState<StreamState>({})


    // ==========================================
    // WEBSOCKET CONNECTION
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            // ==========================================
            // TOKEN STREAMING
            // ==========================================

            if (

                event.event_type ===
                "token_stream"

                &&

                event.execution_id
            ) {

                setStreams((previous) => {

                    const existing =

                        previous[
                            event.execution_id!
                        ] || ""

                    const incoming =
                        event.stream_chunk || ""

                    let updated =
                        existing

                    // ==========================================
                    // CASE 1:
                    // BACKEND SENDS FULL CONTENT
                    // ==========================================

                    if (

                        incoming.startsWith(
                            existing
                        )
                    ) {

                        updated = incoming
                    }

                    // ==========================================
                    // CASE 2:
                    // BACKEND SENDS INCREMENTAL TOKENS
                    // ==========================================

                    else if (

                        !existing.endsWith(
                            incoming
                        )
                    ) {

                        updated =
                            existing + incoming
                    }

                    return {

                        ...previous,

                        [event.execution_id!]:
                            updated
                    }
                })
            }


            // ==========================================
            // EVENT DEDUPLICATION
            // ==========================================

            setEvents((previous) => {

                const exists = previous.some(

                    (item) =>

                        item.event_id ===
                        event.event_id
                )

                if (exists) {

                    return previous
                }

                return [

                    event,

                    ...previous

                ].slice(0, 50)
            })
        }


        // ==========================================
        // SUBSCRIBE
        // ==========================================

        websocketService.subscribe(
            handleEvent
        )


        // ==========================================
        // CLEANUP
        // ==========================================

        return () => {

            websocketService.unsubscribe(
                handleEvent
            )
        }

    }, [])


    // ==========================================
    // EVENT COLORS
    // ==========================================

    const getEventColor = (

        status?: string

    ) => {

        switch (status) {

            case "running":

                return (
                    "border-yellow-500"
                )

            case "completed":

                return (
                    "border-green-500"
                )

            case "failed":

                return (
                    "border-red-500"
                )

            default:

                return (
                    "border-blue-500"
                )
        }
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
                h-full
            "
        >

            {/* HEADER */}

            <div className="mb-6">

                <h1
                    className="
                        text-3xl
                        font-black
                    "
                >

                    🧠 Live Cognition Stream

                </h1>

                <p
                    className="
                        text-gray-500
                        mt-2
                    "
                >

                    Realtime multi-agent cognitive telemetry

                </p>

            </div>


            {/* EVENTS */}

            <div
                className="
                    space-y-4
                    max-h-[900px]
                    overflow-y-auto
                    pr-2
                "
            >

                {

                    events.length === 0 && (

                        <div
                            className="
                                text-gray-400
                            "
                        >

                            Waiting for cognition stream...

                        </div>
                    )
                }

                {

                    events.map(

                        (
                            event,
                            index
                        ) => (

                            <div

                                key={
                                    event.event_id ||
                                    index
                                }

                                className={`

                                    border-l-4
                                    rounded-xl
                                    p-4
                                    bg-gray-50

                                    ${

                                        getEventColor(
                                            event.status
                                        )
                                    }

                                `}
                            >

                                {/* HEADER */}

                                <div
                                    className="
                                        flex
                                        justify-between
                                        items-center
                                    "
                                >

                                    <div
                                        className="
                                            font-bold
                                            uppercase
                                            text-sm
                                            text-blue-600
                                        "
                                    >

                                        {

                                            event.agent
                                        }

                                    </div>

                                    <div
                                        className="
                                            text-xs
                                            text-gray-500
                                        "
                                    >

                                        {

                                            new Date(

                                                event.timestamp

                                            ).toLocaleTimeString()
                                        }

                                    </div>

                                </div>


                                {/* EVENT TYPE */}

                                <div
                                    className="
                                        mt-3
                                        font-semibold
                                        text-sm
                                    "
                                >

                                    {

                                        event.event_type
                                    }

                                </div>


                                {/* STREAMING */}

                                {

                                    event.execution_id

                                    &&

                                    streams[
                                        event.execution_id
                                    ]

                                    &&

                                    event.event_type ===
                                    "token_stream"

                                    && (

                                        <div
                                            className="
                                                mt-4
                                                bg-black
                                                rounded-xl
                                                p-4
                                                text-green-400
                                                text-sm
                                                whitespace-pre-wrap
                                                leading-7
                                            "
                                        >

                                            {

                                                streams[
                                                    event.execution_id
                                                ]
                                            }

                                        </div>
                                    )
                                }


                                {/* MESSAGE */}

                                {

                                    event.event_type !==
                                    "token_stream"

                                    && (

                                        <div
                                            className="
                                                mt-2
                                                text-gray-700
                                                text-sm
                                            "
                                        >

                                            {

                                                event.message
                                            }

                                        </div>
                                    )
                                }


                                {/* SOURCES */}

                                {

                                    event.payload?.sources

                                    &&

                                    Array.isArray(
                                        event.payload.sources
                                    )

                                    &&

                                    event.payload.sources.length > 0

                                    && (

                                        <div
                                            className="
                                                mt-4
                                                space-y-3
                                            "
                                        >

                                            <div
                                                className="
                                                    text-sm
                                                    font-bold
                                                    text-[#82c0a4]
                                                "
                                            >

                                                🔎 Retrieved Sources

                                            </div>

                                            {

                                                event.payload.sources.map(

                                                    (
                                                        source: any,
                                                        sourceIndex: number
                                                    ) => (

                                                        <div

                                                            key={sourceIndex}

                                                            className="
                                                                border
                                                                border-gray-200
                                                                rounded-xl
                                                                p-3
                                                                bg-white
                                                            "
                                                        >

                                                            {/* TITLE */}

                                                            <div
                                                                className="
                                                                    font-semibold
                                                                    text-sm
                                                                "
                                                            >

                                                                {

                                                                    source.title ||

                                                                    "Untitled Source"
                                                                }

                                                            </div>


                                                            {/* URL */}

                                                            <a

                                                                href={
                                                                    source.url
                                                                }

                                                                target="_blank"

                                                                rel="noopener noreferrer"

                                                                className="
                                                                    text-xs
                                                                    text-blue-600
                                                                    break-all
                                                                "
                                                            >

                                                                {

                                                                    source.url
                                                                }

                                                            </a>


                                                            {/* SCORE */}

                                                            {

                                                                source.score && (

                                                                    <div
                                                                        className="
                                                                            text-xs
                                                                            text-green-600
                                                                            mt-1
                                                                        "
                                                                    >

                                                                        Relevance Score:

                                                                        {

                                                                            (
                                                                                source.score * 100
                                                                            ).toFixed(1)
                                                                        }%

                                                                    </div>
                                                                )
                                                            }


                                                            {/* CONTENT */}

                                                            {

                                                                source.content && (

                                                                    <div
                                                                        className="
                                                                            text-xs
                                                                            text-gray-600
                                                                            mt-2
                                                                            line-clamp-4
                                                                        "
                                                                    >

                                                                        {

                                                                            source.content
                                                                        }

                                                                    </div>
                                                                )
                                                            }

                                                        </div>
                                                    )
                                                )
                                            }

                                        </div>
                                    )
                                }

                            </div>
                        )
                    )
                }

            </div>

        </div>
    )
}