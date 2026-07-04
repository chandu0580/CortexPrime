"use client"

import { useEffect, useState } from "react"

import {

    Bot,

    Activity,

    Cpu,

    Workflow,

    Sparkles,

    BrainCircuit,

    Clock3,

    RadioTower,

    CheckCircle2

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// AGENT
// ==========================================

interface AutonomousAgent {

    agent_id: string

    agent_name: string

    interval: number

    status: string

    registered_at: string
}


// ==========================================
// WORKFLOW
// ==========================================

interface WorkflowExecution {

    workflow_name: string

    completed_steps: any[]

    timestamp: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function AutonomousRuntimePanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        runtimeActive,

        setRuntimeActive

    ] = useState(false)

    const [

        activeAgents,

        setActiveAgents

    ] = useState<AutonomousAgent[]>([])

    const [

        workflows,

        setWorkflows

    ] = useState<WorkflowExecution[]>([])

    const [

        runtimeEvents,

        setRuntimeEvents

    ] = useState<string[]>([])

    const [

        cognitionCycles,

        setCognitionCycles

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
            // FILTER EVENTS
            // ======================================

            if (

                event.agent !==
                "autonomous_runtime"
            ) {

                return
            }

            // ======================================
            // STORE EVENTS
            // ======================================

            setRuntimeEvents(

                (previous) => [

                    event.message,

                    ...previous
                ].slice(0, 20)
            )

            // ======================================
            // RUNTIME START
            // ======================================

            if (

                event.event_type ===
                "autonomous_runtime_started"
            ) {

                setRuntimeActive(
                    true
                )
            }

            // ======================================
            // RUNTIME STOP
            // ======================================

            if (

                event.event_type ===
                "autonomous_runtime_stopped"
            ) {

                setRuntimeActive(
                    false
                )
            }

            // ======================================
            // REGISTERED AGENT
            // ======================================

            if (

                event.event_type ===
                "autonomous_agent_registered"
            ) {

                const payload =
                    event.payload

                if (payload) {

                    setActiveAgents(

                        (previous) => [

                            {

                                agent_id:
                                    payload.agent_id,

                                agent_name:
                                    event.message
                                        .replace(
                                            "Registered autonomous agent: ",
                                            ""
                                        ),

                                interval:
                                    payload.interval,

                                status:
                                    "active",

                                registered_at:
                                    new Date()
                                    .toISOString()
                            },

                            ...previous
                        ]
                    )
                }
            }

            // ======================================
            // WORKFLOW COMPLETED
            // ======================================

            if (

                event.event_type ===
                "workflow_execution_completed"
            ) {

                setWorkflows(

                    (previous) => [

                        {

                            workflow_name:
                                event.message
                                    .replace(
                                        "Workflow completed: ",
                                        ""
                                    ),

                            completed_steps:
                                [],

                            timestamp:
                                new Date()
                                .toISOString()
                        },

                        ...previous
                    ].slice(0, 10)
                )
            }

            // ======================================
            // COGNITION CYCLE
            // ======================================

            if (

                event.event_type ===
                "autonomous_agent_cycle"
            ) {

                setCognitionCycles(

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
                border-emerald-500/20

                bg-gradient-to-br

                from-slate-950
                via-slate-900
                to-black

                p-6

                shadow-2xl
                shadow-emerald-500/10
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

                            bg-emerald-500/10

                            border
                            border-emerald-400/20
                        "
                    >

                        <Bot
                            className="
                                w-6
                                h-6
                                text-emerald-400
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

                            Autonomous Runtime

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Persistent Autonomous
                            Agent Orchestration

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

                        {runtimeActive
                            ? "AUTONOMOUS"
                            : "IDLE"}

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

                {/* ACTIVE AGENTS */}

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

                        <Cpu
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

                            Active Agents

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {activeAgents.length}

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
                                text-[#82c0a4]
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


                {/* CYCLES */}

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
                                text-yellow-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Cognition Cycles

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {cognitionCycles}

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
                                text-emerald-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Runtime Events

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {runtimeEvents.length}

                    </div>

                </div>

            </div>


            {/* ACTIVE AGENTS */}

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

                    Active Autonomous Agents

                </h3>

                <div
                    className="
                        space-y-3
                    "
                >

                    {activeAgents.map(

                        (
                            agent,
                            index
                        ) => (

                            <div
                                key={index}

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

                                        <Bot
                                            className="
                                                w-5
                                                h-5
                                                text-emerald-400
                                            "
                                        />

                                        <div>

                                            <div
                                                className="
                                                    text-white
                                                    font-medium
                                                "
                                            >

                                                {agent.agent_name}

                                            </div>

                                            <div
                                                className="
                                                    text-xs
                                                    text-slate-500
                                                "
                                            >

                                                Interval:
                                                {" "}
                                                {agent.interval}s

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
                                                text-emerald-300
                                            "
                                        >

                                            ACTIVE

                                        </span>

                                    </div>

                                </div>

                            </div>
                        )
                    )}

                    {activeAgents.length === 0 && (

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

                            <RadioTower
                                className="
                                    w-12
                                    h-12
                                    text-emerald-400
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

                                No Autonomous Agents

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime autonomous
                                runtime is waiting for
                                persistent AI workforce
                                activation.

                            </p>

                        </div>
                    )}

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

                    Workflow Execution History

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

                                    bg-emerald-500/5

                                    border
                                    border-emerald-400/10

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
                                            text-emerald-400
                                        "
                                    />

                                    <div>

                                        <div
                                            className="
                                                text-white
                                                font-medium
                                            "
                                        >

                                            {workflow.workflow_name}

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

                    Runtime Telemetry Stream

                </h3>

                <div
                    className="
                        space-y-2
                    "
                >

                    {runtimeEvents.map(

                        (
                            event,
                            index
                        ) => (

                            <div
                                key={index}

                                className="
                                    rounded-lg

                                    bg-emerald-500/5

                                    border
                                    border-emerald-400/10

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
                                            text-emerald-400
                                        "
                                    />

                                    <span
                                        className="
                                            text-sm
                                            text-slate-200
                                        "
                                    >

                                        {event}

                                    </span>

                                </div>

                            </div>
                        )
                    )}

                </div>

            </div>

        </div>
    )
}