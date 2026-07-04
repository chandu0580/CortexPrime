"use client"

import {
    useEffect,
    useMemo,
    useRef,
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

    agent: string

    content: string

    completed: boolean

    timestamp?: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function LiveTokenStream() {

    const [

        streams,

        setStreams

    ] = useState<
        Record<string, StreamState>
    >({})

    const containerRef =
        useRef<HTMLDivElement>(
            null
        )


    // ==========================================
    // AUTO SCROLL
    // ==========================================

    useEffect(() => {

        if (containerRef.current) {

            containerRef.current.scrollTop = (

                containerRef.current
                .scrollHeight
            )
        }

    }, [streams])


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (
            event: CognitionEvent
        ) => {

            // ==========================================
            // TOKEN STREAM
            // ==========================================

            if (

                event.event_type ===
                "token_stream"

                &&

                event.stream_chunk
            ) {

                setStreams(

                    (previous) => {

                        const existing = (

                            previous[
                                event.agent
                            ]
                        )

                        return {

                            ...previous,

                            [event.agent]: {

                                agent:
                                    event.agent,

                                completed:
                                    false,

                                timestamp:
                                    event.timestamp,

                                content:

                                    existing
                                    ?.content ||

                                    "" +

                                    event.stream_chunk
                            }
                        }
                    }
                )
            }


            // ==========================================
            // STREAM COMPLETED
            // ==========================================

            if (

                event.event_type ===
                "stream_completed"
            ) {

                setStreams(

                    (previous) => {

                        const existing = (

                            previous[
                                event.agent
                            ]
                        )

                        if (!existing) {

                            return previous
                        }

                        return {

                            ...previous,

                            [event.agent]: {

                                ...existing,

                                completed: true
                            }
                        }
                    }
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
    // STREAM LIST
    // ==========================================

    const streamList = useMemo(() => {

        return Object.values(
            streams
        )

    }, [streams])


    // ==========================================
    // STATUS COLOR
    // ==========================================

    const getStatusColor = (
        completed: boolean
    ) => {

        return completed

            ? "bg-green-100 text-green-700"

            : "bg-blue-100 text-blue-700"
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

                    ⚡ Live Cognitive Stream

                </h2>

                <p
                    className="
                        text-gray-500
                        mt-1
                    "
                >

                    Realtime multi-agent token generation

                </p>

            </div>


            {/* STREAMS */}

            <div
                ref={containerRef}
                className="
                    p-6
                    space-y-6
                    max-h-150
                    overflow-y-auto
                    bg-gray-50
                "
            >

                {

                    streamList.length === 0 ? (

                        <div
                            className="
                                text-sm
                                text-gray-400
                            "
                        >

                            Waiting for live token streams...

                        </div>

                    ) : (

                        streamList.map(

                            (
                                stream,
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

                                    {/* HEADER */}

                                    <div
                                        className="
                                            flex
                                            items-center
                                            justify-between
                                            mb-4
                                        "
                                    >

                                        <div
                                            className="
                                                font-bold
                                                text-lg
                                            "
                                        >

                                            {

                                                stream.agent
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
                                                    stream.completed
                                                )}

                                            `}
                                        >

                                            {

                                                stream.completed

                                                    ? "completed"

                                                    : "streaming"
                                            }

                                        </div>

                                    </div>


                                    {/* CONTENT */}

                                    <div
                                        className="
                                            whitespace-pre-wrap
                                            text-sm
                                            leading-7
                                            text-gray-800
                                        "
                                    >

                                        {

                                            stream.content
                                        }

                                        {

                                            !stream.completed && (

                                                <span
                                                    className="
                                                        animate-pulse
                                                        ml-1
                                                        font-bold
                                                        text-blue-500
                                                    "
                                                >

                                                    ▋

                                                </span>
                                            )
                                        }

                                    </div>


                                    {/* FOOTER */}

                                    <div
                                        className="
                                            mt-4
                                            text-xs
                                            text-gray-400
                                        "
                                    >

                                        {

                                            stream.timestamp
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