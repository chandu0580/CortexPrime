
"use client"

import { useEffect, useState } from "react"

import {

    Monitor,

    MousePointerClick,

    Keyboard,

    Workflow,

    Activity,

    Globe,

    Camera,

    Terminal,

    Sparkles,

    BrainCircuit

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// ACTION EVENT
// ==========================================

interface ActionEvent {

    message: string

    timestamp: string
}


// ==========================================
// WORKFLOW
// ==========================================

interface WorkflowEvent {

    name: string

    timestamp: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function ComputerControlPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        actionEvents,

        setActionEvents

    ] = useState<ActionEvent[]>([])

    const [

        workflows,

        setWorkflows

    ] = useState<WorkflowEvent[]>([])

    const [

        mouseActions,

        setMouseActions

    ] = useState(0)

    const [

        keyboardActions,

        setKeyboardActions

    ] = useState(0)

    const [

        screenshots,

        setScreenshots

    ] = useState(0)

    const [

        operatorEvents,

        setOperatorEvents

    ] = useState(0)


    // ==========================================
    // WEBSOCKET EVENTS
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            const validAgents = [

                "desktop_controller",

                "window_manager",

                "screen_intelligence",

                "computer_task_engine"
            ]

            // ======================================
            // FILTER EVENTS
            // ======================================

            if (

                !validAgents.includes(
                    event.agent
                )
            ) {

                return
            }

            // ======================================
            // STORE EVENTS
            // ======================================

            setActionEvents(

                (previous) => [

                    {

                        message:
                            event.message,

                        timestamp:
                            new Date()
                            .toISOString()
                    },

                    ...previous
                ].slice(0, 25)
            )

            setOperatorEvents(

                (previous) =>
                    previous + 1
            )

            // ======================================
            // MOUSE EVENTS
            // ======================================

            if (

                event.event_type.includes(
                    "mouse"
                )
            ) {

                setMouseActions(

                    (previous) =>
                        previous + 1
                )
            }

            // ======================================
            // KEYBOARD EVENTS
            // ======================================

            if (

                event.event_type.includes(
                    "keyboard"
                )

                ||

                event.event_type.includes(
                    "key"
                )

                ||

                event.event_type.includes(
                    "hotkey"
                )
            ) {

                setKeyboardActions(

                    (previous) =>
                        previous + 1
                )
            }

            // ======================================
            // SCREENSHOT EVENTS
            // ======================================

            if (

                event.event_type.includes(
                    "screen"
                )
            ) {

                setScreenshots(

                    (previous) =>
                        previous + 1
                )
            }

            // ======================================
            // WORKFLOW EVENTS
            // ======================================

            if (

                event.event_type.includes(
                    "workflow"
                )
            ) {

                setWorkflows(

                    (previous) => [

                        {

                            name:
                                event.message,

                            timestamp:
                                new Date()
                                .toISOString()
                        },

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

                        <Monitor
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

                            Computer Control Runtime

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Autonomous AI Operator
                            Telemetry

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

                        bg-[#4a8c70]/10

                        border
                        border-[#82c0a4]/20
                    "
                >

                    <Activity
                        className="
                            w-4
                            h-4

                            text-[#4a8c70]

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

                        OPERATOR ACTIVE

                    </span>

                </div>

            </div>


            {/* METRICS */}

            <div
                className="
                    grid
                    grid-cols-1
                    md:grid-cols-5
                    gap-4
                    mb-6
                "
            >

                {/* MOUSE */}

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

                        <MousePointerClick
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

                            Mouse

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {mouseActions}

                    </div>

                </div>


                {/* KEYBOARD */}

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

                        <Keyboard
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

                            Keyboard

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {keyboardActions}

                    </div>

                </div>


                {/* SCREEN */}

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

                        <Camera
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

                            Screens

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {screenshots}

                    </div>

                </div>


                {/* WORKFLOWS */}

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
                                text-yellow-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Workflows

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {workflows.length}

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

                            Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {operatorEvents}

                    </div>

                </div>

            </div>


            {/* WORKFLOW HISTORY */}

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

                    Autonomous Workflows

                </h3>

                <div
                    className="
                        space-y-3
                    "
                >

                    {workflows.map(

                        (
                            workflow,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-xl

                                    bg-[#4a8c70]/5

                                    border
                                    border-[#82c0a4]/10

                                    p-4
                                "
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        gap-3
                                    "
                                >

                                    <Workflow
                                        className="
                                            w-5
                                            h-5
                                            text-[#4a8c70]
                                        "
                                    />

                                    <div>

                                        <div
                                            className="
                                                text-white
                                                font-medium
                                            "
                                        >

                                            {workflow.name}

                                        </div>

                                        <div
                                            className="
                                                text-xs
                                                text-slate-500
                                            "
                                        >

                                            {new Date(
                                                workflow.timestamp
                                            ).toLocaleString()}

                                        </div>

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

                    Live Operator Event Stream

                </h3>

                <div
                    className="
                        space-y-2
                    "
                >

                    {actionEvents.map(

                        (
                            event,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-lg

                                    bg-[#4a8c70]/5

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

                                    <Sparkles
                                        className="
                                            w-4
                                            h-4
                                            text-[#4a8c70]
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

                    {actionEvents.length === 0 && (

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

                                AI Operator Idle

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime is ready
                                to autonomously operate
                                desktop workflows and
                                computer tasks.

                            </p>

                        </div>
                    )}

                </div>

            </div>

        </div>
    )
}