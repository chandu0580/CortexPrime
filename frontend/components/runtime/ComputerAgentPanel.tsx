
"use client"

import { useEffect, useState } from "react"

import {

    Bot,

    Workflow,

    BrainCircuit,

    CheckCircle2,

    AlertTriangle,

    Activity,

    Cpu,

    Sparkles,

    Terminal,

    ArrowRightCircle

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// MISSION
// ==========================================

interface Mission {

    id: string

    name: string

    status: string

    timestamp: string
}


// ==========================================
// STEP EVENT
// ==========================================

interface StepEvent {

    message: string

    status: string

    timestamp: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function ComputerAgentPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        missions,

        setMissions

    ] = useState<Mission[]>([])

    const [

        stepEvents,

        setStepEvents

    ] = useState<StepEvent[]>([])

    const [

        activeMissionCount,

        setActiveMissionCount

    ] = useState(0)

    const [

        completedSteps,

        setCompletedSteps

    ] = useState(0)

    const [

        failedSteps,

        setFailedSteps

    ] = useState(0)

    const [

        cognitionEvents,

        setCognitionEvents

    ] = useState(0)


    // ==========================================
    // WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ======================================
            // FILTER AGENT
            // ======================================

            if (

                event.agent !==
                "computer_agent"
            ) {

                return
            }

            // ======================================
            // STORE EVENTS
            // ======================================

            setStepEvents(

                (previous) => [

                    {

                        message:
                            event.message,

                        status:
                            event.status,

                        timestamp:
                            new Date()
                            .toISOString()
                    },

                    ...previous
                ].slice(0, 30)
            )

            setCognitionEvents(

                (previous) =>
                    previous + 1
            )

            // ======================================
            // MISSION START
            // ======================================

            if (

                event.event_type ===
                "computer_mission_started"
            ) {

                setActiveMissionCount(

                    (previous) =>
                        previous + 1
                )

                setMissions(

                    (previous) => [

                        {

                            id:
                                event.execution_id ?? crypto.randomUUID(),

                            name:
                                event.message
                                    .replace(
                                        "Starting mission: ",
                                        ""
                                    ),
                            status:
                                "running",

                            timestamp:
                                new Date()
                                .toISOString()
                        },

                        ...previous
                    ]
                )
            }

            // ======================================
            // MISSION COMPLETE
            // ======================================

            if (

                event.event_type ===
                "computer_mission_completed"
            ) {

                setActiveMissionCount(

                    (previous) =>

                        Math.max(
                            0,
                            previous - 1
                        )
                )

                setMissions(

                    (previous) =>

                        previous.map(

                            (
                                mission
                            ) => {

                                if (

                                    mission.id ===
                                    event.execution_id
                                ) {

                                    return {

                                        ...mission,

                                        status:
                                            "completed"
                                    }
                                }

                                return mission
                            }
                        )
                )
            }

            // ======================================
            // STEP COMPLETE
            // ======================================

            if (

                event.event_type ===
                "computer_step_completed"
            ) {

                setCompletedSteps(

                    (previous) =>
                        previous + 1
                )
            }

            // ======================================
            // STEP FAILED
            // ======================================

            if (

                event.event_type ===
                "computer_step_failed"
            ) {

                setFailedSteps(

                    (previous) =>
                        previous + 1
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

                        <Bot
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

                            Computer Agent Runtime

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Devin-Style Autonomous
                            Computer Cognition

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

                        bg-[#82c0a4]/10

                        border
                        border-[#82c0a4]/20
                    "
                >

                    <Activity
                        className="
                            w-4
                            h-4

                            text-[#82c0a4]

                            animate-pulse
                        "
                    />

                    <span
                        className="
                            text-sm
                            text-[#96cead]
                            font-medium
                        "
                    >

                        AGENT ACTIVE

                    </span>

                </div>

            </div>


            {/* METRICS */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-4
                    gap-4
                    mb-6
                "
            >

                {/* ACTIVE MISSIONS */}

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

                        <Workflow
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

                            Active Missions

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {activeMissionCount}

                    </div>

                </div>


                {/* COMPLETED */}

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

                        <CheckCircle2
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

                            Completed Steps

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {completedSteps}

                    </div>

                </div>


                {/* FAILURES */}

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

                        <AlertTriangle
                            className="
                                w-4
                                h-4
                                text-red-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Recovery Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {failedSteps}

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

                        <BrainCircuit
                            className="
                                w-4
                                h-4
                                text-pink-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Cognition Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {cognitionEvents}

                    </div>

                </div>

            </div>


            {/* MISSIONS */}

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

                    Mission Runtime

                </h3>

                <div
                    className="
                        space-y-3
                    "
                >

                    {missions.map(

                        (
                            mission,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-xl

                                    bg-[#82c0a4]/5

                                    border
                                    border-[#82c0a4]/10

                                    p-4
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        justify-between
                                    "
                                >

                                    <div
                                        className="
                                            flex
                                            items-center
                                            gap-3
                                        "
                                    >

                                        <Cpu
                                            className="
                                                w-5
                                                h-5
                                                text-[#82c0a4]
                                            "
                                        />

                                        <div>

                                            <div
                                                className="
                                                    text-white
                                                    font-medium
                                                "
                                            >

                                                {mission.name}

                                            </div>

                                            <div
                                                className="
                                                    text-xs
                                                    text-slate-500
                                                "
                                            >

                                                {new Date(
                                                    mission.timestamp
                                                ).toLocaleString()}

                                            </div>

                                        </div>

                                    </div>

                                    <div
                                        className="
                                            flex
                                            items-center
                                            gap-2
                                        "
                                    >

                                        {mission.status ===
                                        "completed" ? (

                                            <CheckCircle2
                                                className="
                                                    w-4
                                                    h-4
                                                    text-emerald-400
                                                "
                                            />

                                        ) : (

                                            <Activity
                                                className="
                                                    w-4
                                                    h-4
                                                    text-yellow-400
                                                    animate-pulse
                                                "
                                            />

                                        )}

                                        <span
                                            className="
                                                text-sm
                                                text-slate-300
                                            "
                                        >

                                            {mission.status
                                                .toUpperCase()}

                                        </span>

                                    </div>

                                </div>

                            </div>
                        )
                    )}

                </div>

            </div>


            {/* EVENT STREAM */}

            <div>

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Computer Cognition Stream

                </h3>

                <div
                    className="
                        space-y-2
                    "
                >

                    {stepEvents.map(

                        (
                            event,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-lg

                                    bg-[#82c0a4]/5

                                    border
                                    border-[#82c0a4]/10

                                    px-4
                                    py-3
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        gap-2
                                    "
                                >

                                    <ArrowRightCircle
                                        className="
                                            w-4
                                            h-4
                                            text-[#82c0a4]
                                        "
                                    />

                                    <span
                                        className="
                                            text-sm
                                            text-slate-200
                                        "
                                    >

                                        {event.message}

                                    </span>

                                </div>

                            </div>
                        )
                    )}

                    {stepEvents.length === 0 && (

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

                            <Terminal
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

                                Computer Agent Idle

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime is ready
                                to autonomously execute
                                multi-step computer
                                missions and workflows.

                            </p>

                        </div>
                    )}

                </div>

            </div>

        </div>
    )
}