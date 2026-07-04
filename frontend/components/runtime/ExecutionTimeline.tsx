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
// COMPONENT
// ==========================================

export default function ExecutionTimeline() {

    // ==========================================
    // STATE
    // ==========================================

    const [events, setEvents] =
        useState<CognitionEvent[]>([])


    // ==========================================
    // WEBSOCKET STREAM
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        websocketService.subscribe(

            (
                event: CognitionEvent
            ) => {

                setEvents(

                    (previous) => [

                        event,

                        ...previous
                    ]
                )
            }
        )

        return () => {

            websocketService.disconnect()
        }

    }, [])


    // ==========================================
    // FORMAT TIME
    // ==========================================

    const formatTimestamp = (

        timestamp?: string

    ) => {

        if (!timestamp) {

            return "Unknown Time"
        }

        return new Date(

            timestamp

        ).toLocaleTimeString()
    }


    // ==========================================
    // STATUS COLOR
    // ==========================================

    const getStatusColor = (

        status?: string

    ) => {

        switch (status) {

            case "running":

                return "border-yellow-500"

            case "completed":

                return "border-green-500"

            case "failed":

                return "border-red-500"

            default:

                return "border-blue-500"
        }
    }


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm"
        >

            {/* HEADER */}

            <div className="mb-6">

                <h2
                    className="text-2xl font-black"
                >

                    🕒 Execution Timeline

                </h2>

                <p
                    className="text-gray-500 mt-1"
                >

                    Live multi-agent cognitive execution stream

                </p>

            </div>


            {/* EVENTS */}

            <div
                className="space-y-4 max-h-[600px] overflow-y-auto pr-2"
            >

                {

                    events.length === 0 && (

                        <div
                            className="text-gray-400 text-sm"
                        >

                            Waiting for runtime events...

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

                                key={index}

                                className={`flex gap-4 items-start border-l-4 rounded-r-xl bg-gray-50 p-4 ${

                                    getStatusColor(
                                        event.status
                                    )
                                }`}
                            >

                                {/* TIME */}

                                <div
                                    className="text-xs text-gray-500 min-w-[100px]"
                                >

                                    {

                                        formatTimestamp(
                                            event.timestamp
                                        )
                                    }

                                </div>


                                {/* CONTENT */}

                                <div className="flex-1">

                                    {/* AGENT */}

                                    <div
                                        className="flex items-center gap-2"
                                    >

                                        <span
                                            className="font-bold text-blue-600 uppercase text-sm"
                                        >

                                            {

                                                event.agent
                                            }

                                        </span>

                                        <span
                                            className="text-xs bg-black text-white px-2 py-1 rounded-lg"
                                        >

                                            {

                                                event.status
                                            }

                                        </span>

                                    </div>


                                    {/* EVENT TYPE */}

                                    <div
                                        className="text-sm font-semibold mt-2"
                                    >

                                        {

                                            event.event_type
                                        }

                                    </div>


                                    {/* MESSAGE */}

                                    <div
                                        className="text-gray-700 mt-1 text-sm"
                                    >

                                        {

                                            event.message
                                        }

                                    </div>

                                </div>

                            </div>
                        )
                    )
                }

            </div>

        </div>
    )
}