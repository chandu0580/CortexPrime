"use client"

import { useEffect, useState } from "react"

import {
    websocketService,
    CognitionEvent
} from "@/services/websocketService"


// ==========================================
// COMPONENT
// ==========================================

export default function CognitionEventPanel() {

    const [events, setEvents] = useState<
        CognitionEvent[]
    >([])

    // ==========================================
    // CONNECT WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        websocketService.subscribe(
            (event) => {

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
    // UI
    // ==========================================

    return (

        <div className="p-6">

            <h1 className="text-3xl font-bold mb-6">

                🧠 CortexPrime
                Realtime Cognition

            </h1>

            <div className="space-y-4">

                {

                    events.map(

                        (
                            event,
                            index
                        ) => (

                            <div

                                key={index}

                                className="border rounded-xl p-4 shadow-sm bg-white"

                            >

                                {/* EVENT TYPE */}

                                <div className="font-semibold text-blue-600">

                                    {

                                        event.type ||

                                        "runtime_event"
                                    }

                                </div>

                                {/* EVENT MESSAGE */}

                                <div className="mt-1 text-gray-800">

                                    {

                                        event.event ||

                                        event.message ||

                                        "No message"
                                    }

                                </div>

                                {/* TIMESTAMP */}

                                <div className="text-sm text-gray-500 mt-2">

                                    {

                                        event.timestamp ||

                                        "No timestamp"
                                    }

                                </div>

                            </div>
                        )
                    )
                }

            </div>

        </div>
    )
}