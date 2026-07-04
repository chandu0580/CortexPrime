"use client"

import { useEffect, useState } from "react"

import {

    Globe,

    Activity,

    Search,

    Link2,

    ExternalLink,

    Sparkles,

    CheckCircle2,

    AlertTriangle

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// BROWSER EVENT
// ==========================================

interface BrowserEvent {

    agent: string

    event_type: string

    message: string

    timestamp: string

    phase?: string

    payload?: any
}


// ==========================================
// EXTRACTED LINK
// ==========================================

interface ExtractedLink {

    text?: string

    href?: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function BrowserTelemetryPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        browserEvents,

        setBrowserEvents

    ] = useState<BrowserEvent[]>([])

    const [

        activeUrl,

        setActiveUrl

    ] = useState<string>("")

    const [

        extractedLinks,

        setExtractedLinks

    ] = useState<ExtractedLink[]>([])

    const [

        navigationStatus,

        setNavigationStatus

    ] = useState<string>("idle")


    // ==========================================
    // WEBSOCKET EVENTS
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ==========================================
            // FILTER BROWSER EVENTS
            // ==========================================

            const isBrowserEvent = (

                event.agent ===
                "browser_agent"

                ||

                event.event_type ===
                "browser_navigation_started"

                ||

                event.event_type ===
                "browser_navigation_completed"

                ||

                event.event_type ===
                "browser_navigation_failed"

                ||

                event.event_type ===
                "link_extraction_started"

                ||

                event.event_type ===
                "link_extraction_completed"
            )

            if (!isBrowserEvent) {

                return
            }

            // ==========================================
            // ADD EVENT
            // ==========================================

            setBrowserEvents(

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
                ].slice(0, 30)
            )

            // ==========================================
            // NAVIGATION STARTED
            // ==========================================

            if (

                event.event_type ===
                "browser_navigation_started"
            ) {

                setNavigationStatus(
                    "running"
                )

                setActiveUrl(

                    event.payload?.url || ""
                )
            }

            // ==========================================
            // NAVIGATION COMPLETED
            // ==========================================

            if (

                event.event_type ===
                "browser_navigation_completed"
            ) {

                setNavigationStatus(
                    "completed"
                )
            }

            // ==========================================
            // NAVIGATION FAILED
            // ==========================================

            if (

                event.event_type ===
                "browser_navigation_failed"
            ) {

                setNavigationStatus(
                    "failed"
                )
            }

            // ==========================================
            // LINK EXTRACTION
            // ==========================================

            if (

                event.event_type ===
                "link_extraction_completed"
            ) {

                const links =

                    event.payload?.links

                if (

                    Array.isArray(
                        links
                    )
                ) {

                    setExtractedLinks(
                        links
                    )
                }
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
    // STATUS COLOR
    // ==========================================

    const getStatusColor = (

        status: string
    ) => {

        switch (status) {

            case "running":

                return "text-[#4a8c70]"

            case "completed":

                return "text-emerald-400"

            case "failed":

                return "text-red-400"

            default:

                return "text-slate-400"
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

                        <Globe
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

                            Browser Telemetry

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Autonomous Internet
                            Execution Runtime

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

                {/* STATUS */}

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

                        <Activity
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

                            Navigation Status

                        </span>

                    </div>

                    <div
                        className={`
                            text-2xl
                            font-bold

                            ${getStatusColor(
                                navigationStatus
                            )}
                        `}
                    >

                        {navigationStatus}

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

                        <Search
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

                            Browser Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {browserEvents.length}

                    </div>

                </div>


                {/* LINKS */}

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

                        <Link2
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

                            Extracted Links

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {extractedLinks.length}

                    </div>

                </div>

            </div>


            {/* ACTIVE URL */}

            {activeUrl && (

                <div
                    className="
                        mb-6

                        rounded-xl

                        bg-[#4a8c70]/10

                        border
                        border-[#82c0a4]/20

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

                        <ExternalLink
                            className="
                                w-4
                                h-4
                                text-[#4a8c70]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-[#96cead]
                                font-medium
                            "
                        >

                            Active Navigation

                        </span>

                    </div>

                    <div
                        className="
                            text-sm
                            text-white
                            break-all
                        "
                    >

                        {activeUrl}

                    </div>

                </div>
            )}


            {/* TELEMETRY FEED */}

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

                    Browser Execution Feed

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[400px]
                        overflow-y-auto
                    "
                >

                    {browserEvents.map(

                        (event, index) => (

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
                                                text-[#96cead]
                                                font-medium
                                            "
                                        >

                                            {event.event_type}

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
                                    "
                                >

                                    {event.message}

                                </p>

                            </div>
                        )
                    )}

                    {browserEvents.length === 0 && (

                        <div
                            className="
                                flex
                                flex-col
                                items-center
                                justify-center

                                py-16

                                text-center
                            "
                        >

                            <Sparkles
                                className="
                                    w-12
                                    h-12
                                    text-[#4a8c70]
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

                                Awaiting Browser Activity

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime browser agents
                                will stream autonomous
                                navigation and internet
                                cognition telemetry here.

                            </p>

                        </div>
                    )}

                </div>

            </div>


            {/* EXTRACTED LINKS */}

            {extractedLinks.length > 0 && (

                <div>

                    <h3
                        className="
                            text-sm
                            font-semibold
                            text-slate-300
                            mb-3
                        "
                    >

                        Extracted Links

                    </h3>

                    <div
                        className="
                            space-y-2

                            max-h-[250px]
                            overflow-y-auto
                        "
                    >

                        {extractedLinks.map(

                            (link, index) => (

                                <a
                                    key={index}

                                    href={link.href}

                                    target="_blank"

                                    rel="noopener noreferrer"

                                    className="
                                        flex
                                        items-center
                                        gap-3

                                        p-3

                                        rounded-lg

                                        bg-white/5

                                        border
                                        border-white/10

                                        hover:border-[#82c0a4]/30

                                        transition-all
                                    "
                                >

                                    <Link2
                                        className="
                                            w-4
                                            h-4
                                            text-[#4a8c70]
                                        "
                                    />

                                    <div
                                        className="
                                            flex-1
                                            overflow-hidden
                                        "
                                    >

                                        <div
                                            className="
                                                text-sm
                                                text-white

                                                truncate
                                            "
                                        >

                                            {link.text ||
                                                "Untitled Link"}

                                        </div>

                                        <div
                                            className="
                                                text-xs
                                                text-slate-400

                                                truncate
                                            "
                                        >

                                            {link.href}

                                        </div>

                                    </div>

                                </a>
                            )
                        )}

                    </div>

                </div>
            )}

        </div>
    )
}