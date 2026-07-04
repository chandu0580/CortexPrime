"use client"

import {
    useEffect,
    useMemo,
    useState
} from "react"

import {

    websocketService,

    CognitionEvent,

    CognitionSource

} from "@/services/websocketService"


// ==========================================
// SOURCE STATE
// ==========================================

interface SourceState {

    agent: string

    query?: string

    sources: CognitionSource[]

    timestamp?: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function SourceIntelligencePanel() {

    const [

        sourceState,

        setSourceState

    ] = useState<
        SourceState | null
    >(null)


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            // ==========================================
            // RESEARCH COMPLETED
            // ==========================================

            if (

                event.event_type ===
                "research_completed"

                &&

                event.payload
            ) {

                const payload =
                    event.payload

                setSourceState({

                    agent:
                        event.agent,

                    query:
                        payload.query,

                    timestamp:
                        event.timestamp,

                    sources:
                        payload.sources || []
                })
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
    // SORTED SOURCES
    // ==========================================

    const sortedSources = useMemo(() => {

        if (!sourceState) {

            return []
        }

        return [

            ...sourceState.sources

        ].sort(

            (a, b) =>

                (b.score || 0)

                -

                (a.score || 0)
        )

    }, [sourceState])


    // ==========================================
    // SCORE COLOR
    // ==========================================

    const getScoreColor = (
        score?: number
    ) => {

        if (!score) {

            return (
                "bg-gray-100 text-gray-700"
            )
        }

        if (score >= 0.8) {

            return (
                "bg-green-100 text-green-700"
            )
        }

        if (score >= 0.5) {

            return (
                "bg-yellow-100 text-yellow-700"
            )
        }

        return (
            "bg-red-100 text-red-700"
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

                    🌐 Source Intelligence

                </h2>

                <p
                    className="
                        text-gray-500
                        mt-1
                    "
                >

                    Live retrieval augmented intelligence

                </p>

            </div>


            {/* QUERY */}

            {

                sourceState?.query && (

                    <div
                        className="
                            px-5
                            py-4
                            border-b
                            border-gray-100
                            bg-gray-50
                        "
                    >

                        <div
                            className="
                                text-xs
                                font-bold
                                text-gray-500
                                uppercase
                                tracking-wide
                            "
                        >

                            Active Query

                        </div>

                        <div
                            className="
                                mt-2
                                text-sm
                                text-gray-800
                                font-medium
                            "
                        >

                            {

                                sourceState.query
                            }

                        </div>

                    </div>
                )
            }


            {/* SOURCES */}

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

                    sortedSources.length === 0 ? (

                        <div
                            className="
                                text-sm
                                text-gray-400
                            "
                        >

                            Waiting for intelligence sources...

                        </div>

                    ) : (

                        sortedSources.map(

                            (
                                source,
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
                                        hover:shadow-md
                                        transition-all
                                    "
                                >

                                    {/* HEADER */}

                                    <div
                                        className="
                                            flex
                                            items-start
                                            justify-between
                                            gap-4
                                        "
                                    >

                                        <div
                                            className="
                                                flex-1
                                            "
                                        >

                                            <div
                                                className="
                                                    font-bold
                                                    text-base
                                                    text-gray-900
                                                    line-clamp-2
                                                "
                                            >

                                                {

                                                    source.title ||

                                                    "Untitled Source"
                                                }

                                            </div>

                                            {

                                                source.url && (

                                                    <a

                                                        href={
                                                            source.url
                                                        }

                                                        target="_blank"

                                                        rel="noopener noreferrer"

                                                        className="
                                                            mt-2
                                                            inline-block
                                                            text-sm
                                                            text-blue-600
                                                            hover:underline
                                                            break-all
                                                        "
                                                    >

                                                        {

                                                            source.url
                                                        }

                                                    </a>
                                                )
                                            }

                                        </div>


                                        {/* SCORE */}

                                        <div
                                            className={`

                                                px-3
                                                py-1
                                                rounded-full
                                                text-xs
                                                font-bold
                                                whitespace-nowrap

                                                ${getScoreColor(
                                                    source.score
                                                )}

                                            `}
                                        >

                                            {

                                                source.score
                                                    ?.toFixed(2)

                                                ||

                                                "N/A"
                                            }

                                        </div>

                                    </div>


                                    {/* CONTENT */}

                                    {

                                        source.content && (

                                            <div
                                                className="
                                                    mt-4
                                                    text-sm
                                                    leading-7
                                                    text-gray-700
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
                    )
                }

            </div>

        </div>
    )
}