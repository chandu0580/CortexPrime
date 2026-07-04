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

    const [events, setEvents] = useState<
        CognitionEvent[]
    >([])

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
    // UI
    // ==========================================

    return (

        <div
            className="bg-white rounded-2xl border p-6 shadow-sm"
        >

            <h2
                className="text-2xl font-bold mb-6"
            >

                🕒 Execution Timeline

            </h2>

            <div
                className="space-y-4 max-h-[500px] overflow-y-auto"
            >

                {

                    events.map(

                        (
                            event,
                            index
                        ) => (

                            <div

                                key={index}

                                className="flex gap-4 items-start border-l-4 border-blue-500 pl-4"

                            >

                                {/* TIME */}

                                <div
                                    className="text-sm text-gray-500 min-w-[100px]"
                                >

                                    {

                                        formatTimestamp(
                                            event.timestamp
                                        )
                                    }

                                </div>

                                {/* EVENT */}

                                <div>

                                    <div
                                        className="font-semibold text-blue-600"
                                    >

                                        {

                                            event.type ||

                                            "runtime_event"
                                        }

                                    </div>

                                    <div
                                        className="text-gray-800"
                                    >

                                        {

                                            event.event ||

                                            event.message ||

                                            "No event message"
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