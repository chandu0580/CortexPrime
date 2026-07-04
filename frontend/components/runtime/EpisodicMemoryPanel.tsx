"use client"

import { useEffect, useState } from "react"

import {

    Brain,

    MemoryStick,

    Sparkles,

    Clock3,

    Activity,

    Database,

    Star,

    RefreshCcw

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// MEMORY EVENT
// ==========================================

interface MemoryEvent {

    event_type: string

    message: string

    timestamp: string

    payload?: any
}


// ==========================================
// MEMORY ITEM
// ==========================================

interface MemoryItem {

    memory_id: string

    content: string

    memory_type: string

    importance_score: number

    timestamp: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function EpisodicMemoryPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        memoryEvents,

        setMemoryEvents

    ] = useState<MemoryEvent[]>([])

    const [

        memories,

        setMemories

    ] = useState<MemoryItem[]>([])

    const [

        reflections,

        setReflections

    ] = useState<string[]>([])

    const [

        totalMemories,

        setTotalMemories

    ] = useState<number>(0)


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ==========================================
            // FILTER MEMORY EVENTS
            // ==========================================

            const isMemoryEvent = (

                event.agent ===
                "episodic_memory_engine"

                ||

                event.event_type ===
                "episodic_memory_stored"

                ||

                event.event_type ===
                "episodic_memory_recalled"

                ||

                event.event_type ===
                "memory_reflection_completed"
            )

            if (!isMemoryEvent) {

                return
            }

            // ==========================================
            // ADD EVENT
            // ==========================================

            setMemoryEvents(

                (previous) => [

                    {

                        event_type:
                            event.event_type,

                        message:
                            event.message,

                        timestamp:
                            event.timestamp,

                        payload:
                            event.payload
                    },

                    ...previous
                ].slice(0, 25)
            )

            // ==========================================
            // MEMORY STORED
            // ==========================================

            if (

                event.event_type ===
                "episodic_memory_stored"
            ) {

                const memory =

                    event.payload?.memory

                if (memory) {

                    setMemories(

                        (previous) => [

                            memory,

                            ...previous
                        ]
                    )
                }

                setTotalMemories(

                    (previous) =>
                        previous + 1
                )
            }

            // ==========================================
            // MEMORY REFLECTION
            // ==========================================

            if (

                event.event_type ===
                "memory_reflection_completed"
            ) {

                setReflections(

                    (previous) => [

                        event.message,

                        ...previous
                    ].slice(0, 10)
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
    // IMPORTANCE COLOR
    // ==========================================

    const getImportanceColor = (

        score: number
    ) => {

        if (score >= 0.8) {

            return "text-red-400"
        }

        if (score >= 0.5) {

            return "text-yellow-400"
        }

        return "text-emerald-400"
    }


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="

                rounded-2xl

                border
                border-[#82c0a4]/20

                bg-gradient-to-br

                from-slate-950
                via-slate-900
                to-black

                p-6

                shadow-2xl
                shadow-[#82c0a4]/10
            "
        >

            {/* HEADER */}

            <div
                className="
                    flex
                    items-center
                    justify-between
                    mb-6
                "
            >

                <div
                    className="
                        flex
                        items-center
                        gap-3
                    "
                >

                    <div
                        className="
                            p-3

                            rounded-xl

                            bg-[#82c0a4]/10

                            border
                            border-[#82c0a4]/20
                        "
                    >

                        <Brain
                            className="
                                w-6
                                h-6
                                text-[#82c0a4]
                            "
                        />

                    </div>

                    <div>

                        <h2
                            className="
                                text-xl
                                font-bold
                                text-white
                            "
                        >

                            Episodic Memory

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Long-Term Cognitive
                            Memory Runtime

                        </p>

                    </div>

                </div>

                <div
                    className="
                        flex
                        items-center
                        gap-2

                        px-4
                        py-2

                        rounded-full

                        bg-emerald-500/10

                        border
                        border-emerald-400/20
                    "
                >

                    <Activity
                        className="
                            w-4
                            h-4
                            text-emerald-400
                            animate-pulse
                        "
                    />

                    <span
                        className="
                            text-sm
                            text-emerald-300
                            font-medium
                        "
                    >

                        MEMORY ACTIVE

                    </span>

                </div>

            </div>


            {/* METRICS */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-3
                    gap-4
                    mb-6
                "
            >

                {/* TOTAL MEMORIES */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Database
                            className="
                                w-4
                                h-4
                                text-[#4a8c70]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Stored Memories

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {totalMemories}

                    </div>

                </div>


                {/* EVENTS */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <Clock3
                            className="
                                w-4
                                h-4
                                text-yellow-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Memory Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {memoryEvents.length}

                    </div>

                </div>


                {/* REFLECTIONS */}

                <div
                    className="
                        rounded-xl

                        bg-white/5

                        border
                        border-white/10

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-2
                        "
                    >

                        <RefreshCcw
                            className="
                                w-4
                                h-4
                                text-[#82c0a4]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Reflections

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {reflections.length}

                    </div>

                </div>

            </div>


            {/* MEMORY TIMELINE */}

            <div
                className="
                    mb-6
                "
            >

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Memory Timeline

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[350px]
                        overflow-y-auto
                    "
                >

                    {memories.map(

                        (memory, index) => (

                            <div
                                key={index}

                                className="
                                    p-4

                                    rounded-xl

                                    bg-white/5

                                    border
                                    border-white/10
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        justify-between
                                        mb-2
                                    "
                                >

                                    <div
                                        className="
                                            flex
                                            items-center
                                            gap-2
                                        "
                                    >

                                        <MemoryStick
                                            className="
                                                w-4
                                                h-4
                                                text-[#82c0a4]
                                            "
                                        />

                                        <span
                                            className="
                                                text-sm
                                                text-white
                                                font-medium
                                            "
                                        >

                                            {memory.memory_type}

                                        </span>

                                    </div>

                                    <div
                                        className="
                                            flex
                                            items-center
                                            gap-1
                                        "
                                    >

                                        <Star
                                            className={`
                                                w-4
                                                h-4

                                                ${getImportanceColor(
                                                    memory.importance_score
                                                )}
                                            `}
                                        />

                                        <span
                                            className={`
                                                text-sm

                                                ${getImportanceColor(
                                                    memory.importance_score
                                                )}
                                            `}
                                        >

                                            {memory.importance_score.toFixed(
                                                2
                                            )}

                                        </span>

                                    </div>

                                </div>

                                <p
                                    className="
                                        text-sm
                                        text-slate-200
                                        leading-relaxed
                                    "
                                >

                                    {memory.content}

                                </p>

                                <div
                                    className="
                                        mt-3

                                        text-xs
                                        text-slate-500
                                    "
                                >

                                    {new Date(
                                        memory.timestamp
                                    ).toLocaleString()}

                                </div>

                            </div>
                        )
                    )}

                    {memories.length === 0 && (

                        <div
                            className="
                                flex
                                flex-col
                                items-center
                                justify-center

                                py-14

                                text-center
                            "
                        >

                            <Sparkles
                                className="
                                    w-12
                                    h-12
                                    text-[#82c0a4]
                                    mb-4
                                "
                            />

                            <h3
                                className="
                                    text-lg
                                    font-semibold
                                    text-white
                                    mb-2
                                "
                            >

                                Awaiting Memory Formation

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime will begin
                                forming episodic memories
                                from runtime cognition and
                                autonomous experiences.

                            </p>

                        </div>
                    )}

                </div>

            </div>


            {/* REFLECTIONS */}

            {reflections.length > 0 && (

                <div>

                    <h3
                        className="
                            text-sm
                            font-semibold
                            text-slate-300
                            mb-3
                        "
                    >

                        Autonomous Reflections

                    </h3>

                    <div
                        className="
                            space-y-3
                        "
                    >

                        {reflections.map(

                            (
                                reflection,
                                index
                            ) => (

                                <div
                                    key={index}

                                    className="
                                        rounded-xl

                                        bg-[#82c0a4]/10

                                        border
                                        border-[#82c0a4]/20

                                        p-4
                                    "
                                >

                                    <div
                                        className="
                                            flex
                                            items-start
                                            gap-3
                                        "
                                    >

                                        <Sparkles
                                            className="
                                                w-5
                                                h-5
                                                text-[#82c0a4]
                                                mt-0.5
                                            "
                                        />

                                        <p
                                            className="
                                                text-sm
                                                text-slate-200
                                                leading-relaxed
                                            "
                                        >

                                            {reflection}

                                        </p>

                                    </div>

                                </div>
                            )
                        )}

                    </div>

                </div>
            )}

        </div>
    )
}