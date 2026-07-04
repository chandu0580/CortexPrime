"use client"

import { useEffect, useState } from "react"

import {

    Search,

    Brain,

    Activity,

    Sparkles,

    Database,

    Layers3,

    CheckCircle2,

    Globe,

    ArrowRight

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// RESEARCH EVENT
// ==========================================

interface ResearchEvent {

    agent: string

    event_type: string

    message: string

    timestamp: string

    phase?: string

    payload?: any
}


// ==========================================
// SOURCE
// ==========================================

interface ResearchSource {

    title?: string

    url?: string

    score?: number
}


// ==========================================
// COMPONENT
// ==========================================

export default function DeepResearchPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        researchEvents,

        setResearchEvents

    ] = useState<ResearchEvent[]>([])

    const [

        sources,

        setSources

    ] = useState<ResearchSource[]>([])

    const [

        recursiveQueries,

        setRecursiveQueries

    ] = useState<string[]>([])

    const [

        synthesisComplete,

        setSynthesisComplete

    ] = useState<boolean>(false)


    // ==========================================
    // WEBSOCKET EVENTS
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ==========================================
            // FILTER RESEARCH EVENTS
            // ==========================================

            const isResearchEvent = (

                event.agent ===
                "deep_research_engine"

                ||

                event.event_type ===
                "deep_research_completed"

                ||

                event.event_type ===
                "research_started"

                ||

                event.event_type ===
                "research_completed"

                ||

                event.event_type ===
                "source_extraction"

                ||

                event.event_type ===
                "semantic_reranking"

                ||

                event.event_type ===
                "recursive_research"
            )

            if (!isResearchEvent) {

                return
            }

            // ==========================================
            // ADD EVENT
            // ==========================================

            setResearchEvents(

                (previous) => [

                    {

                        agent:
                            event.agent,

                        event_type:
                            event.event_type,

                        message:
                            event.message,

                        timestamp:
                            event.timestamp,

                        phase:
                            event.phase,

                        payload:
                            event.payload
                    },

                    ...previous
                ].slice(0, 25)
            )

            // ==========================================
            // RECURSIVE RESEARCH
            // ==========================================

            if (

                event.event_type ===
                "recursive_research"
            ) {

                const query =

                    event.payload
                    ?.follow_up_query

                if (query) {

                    setRecursiveQueries(

                        (previous) => [

                            query,

                            ...previous
                        ]
                    )
                }
            }

            // ==========================================
            // RESEARCH COMPLETED
            // ==========================================

            if (

                event.event_type ===
                "research_completed"
            ) {

                const eventSources =

                    event.payload?.sources

                if (

                    Array.isArray(
                        eventSources
                    )
                ) {

                    setSources(
                        eventSources
                    )
                }

                setSynthesisComplete(
                    true
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
    // PHASE ICONS
    // ==========================================

    const getPhaseIcon = (

        phase?: string
    ) => {

        switch (phase) {

            case "deep_research":

                return (

                    <Search
                        className="
                            w-4
                            h-4
                            text-[#4a8c70]
                        "
                    />
                )

            case "source_collection":

                return (

                    <Globe
                        className="
                            w-4
                            h-4
                            text-blue-400
                        "
                    />
                )

            case "semantic_ranking":

                return (

                    <Layers3
                        className="
                            w-4
                            h-4
                            text-[#82c0a4]
                        "
                    />
                )

            case "research_synthesis":

                return (

                    <Brain
                        className="
                            w-4
                            h-4
                            text-emerald-400
                        "
                    />
                )

            default:

                return (

                    <Database
                        className="
                            w-4
                            h-4
                            text-slate-400
                        "
                    />
                )
        }
    }


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="

                rounded-2xl

                border
                border-[#4a8c70]/20

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

                            bg-[#4a8c70]/10

                            border
                            border-[#82c0a4]/20
                        "
                    >

                        <Search
                            className="
                                w-6
                                h-6
                                text-[#4a8c70]
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

                            Deep Research Engine

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Recursive Intelligence &
                            Semantic Research

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

                        LIVE

                    </span>

                </div>

            </div>


            {/* RESEARCH METRICS */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-3
                    gap-4
                    mb-6
                "
            >

                {/* SOURCES */}

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

                        <Globe
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

                            Sources

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {sources.length}

                    </div>

                </div>


                {/* RECURSIVE QUERIES */}

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

                        <Layers3
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

                            Research Chains

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {recursiveQueries.length}

                    </div>

                </div>


                {/* SYNTHESIS */}

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

                        <Brain
                            className="
                                w-4
                                h-4
                                text-emerald-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Synthesis

                        </span>

                    </div>

                    <div
                        className={`
                            text-2xl
                            font-bold

                            ${
                                synthesisComplete

                                    ? "text-emerald-400"

                                    : "text-yellow-400"
                            }
                        `}
                    >

                        {synthesisComplete

                            ? "Complete"

                            : "Running"}

                    </div>

                </div>

            </div>


            {/* RESEARCH CHAINS */}

            <div
                className="mb-6"
            >

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Recursive Research Chains

                </h3>

                <div
                    className="
                        flex
                        flex-wrap
                        gap-2
                    "
                >

                    {recursiveQueries.map(

                        (query, index) => (

                            <div
                                key={index}

                                className="
                                    flex
                                    items-center
                                    gap-2

                                    px-3
                                    py-2

                                    rounded-lg

                                    bg-[#82c0a4]/10

                                    border
                                    border-[#82c0a4]/20

                                    text-[#96cead]
                                    text-sm
                                "
                            >

                                <ArrowRight
                                    className="
                                        w-3
                                        h-3
                                    "
                                />

                                {query}

                            </div>
                        )
                    )}

                </div>

            </div>


            {/* LIVE FEED */}

            <div>

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Research Telemetry

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[500px]
                        overflow-y-auto
                    "
                >

                    {researchEvents.map(

                        (event, index) => (

                            <div
                                key={index}

                                className="
                                    p-4

                                    rounded-xl

                                    bg-white/5

                                    border
                                    border-white/10

                                    backdrop-blur-sm
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

                                        {getPhaseIcon(
                                            event.phase
                                        )}

                                        <span
                                            className="
                                                text-[#96cead]
                                                font-medium
                                                text-sm
                                            "
                                        >

                                            {event.agent}

                                        </span>

                                    </div>

                                    <span
                                        className="
                                            text-xs
                                            text-slate-500
                                        "
                                    >

                                        {new Date(
                                            event.timestamp
                                        ).toLocaleTimeString()}

                                    </span>

                                </div>

                                <p
                                    className="
                                        text-sm
                                        text-slate-200
                                        leading-relaxed
                                    "
                                >

                                    {event.message}

                                </p>

                                {event.phase && (

                                    <div
                                        className="
                                            mt-3
                                        "
                                    >

                                        <span
                                            className="
                                                inline-flex

                                                px-2
                                                py-1

                                                rounded-md

                                                bg-[#4a8c70]/10

                                                border
                                                border-[#82c0a4]/20

                                                text-xs
                                                text-[#96cead]
                                            "
                                        >

                                            {event.phase}

                                        </span>

                                    </div>
                                )}

                            </div>
                        )
                    )}

                </div>

            </div>

        </div>
    )
}