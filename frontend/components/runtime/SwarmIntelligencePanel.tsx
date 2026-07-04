
"use client"

import { useEffect, useState } from "react"

import {

    Brain,

    Network,

    Users,

    Sparkles,

    Activity,

    ShieldCheck

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// SWARM EVENT
// ==========================================

interface SwarmEvent {

    agent: string

    event_type: string

    message: string

    timestamp: string

    phase?: string

    consensus_score?: number

    participating_agents?: string[]
}


// ==========================================
// COMPONENT
// ==========================================

export default function SwarmIntelligencePanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        swarmEvents,

        setSwarmEvents

    ] = useState<SwarmEvent[]>([])

    const [

        activeAgents,

        setActiveAgents

    ] = useState<string[]>([])

    const [

        consensusScore,

        setConsensusScore

    ] = useState<number>(0)

    const [

        debateRounds,

        setDebateRounds

    ] = useState<number>(0)


    // ==========================================
    // WEBSOCKET EVENTS
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ==========================================
            // SWARM EVENTS
            // ==========================================

            const isSwarmEvent = (

                event.event_type ===
                "swarm_execution"

                ||

                event.event_type ===
                "agent_debate"

                ||

                event.event_type ===
                "consensus_reached"

                ||

                event.event_type ===
                "consensus_failed"

                ||

                event.event_type ===
                "dynamic_agent_swarm"

                ||

                event.event_type ===
                "dynamic_agent_created"
            )

            if (!isSwarmEvent) {

                return
            }

            // ==========================================
            // UPDATE FEED
            // ==========================================

            setSwarmEvents(

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

                        consensus_score:
                            event.consensus_score,

                        participating_agents:
                            event.participating_agents
                    },

                    ...previous
                ].slice(0, 20)
            )

            // ==========================================
            // CONSENSUS SCORE
            // ==========================================

            if (

                typeof event.consensus_score
                === "number"
            ) {

                setConsensusScore(

                    event.consensus_score
                )
            }

            // ==========================================
            // DEBATE ROUNDS
            // ==========================================

            if (

                event.event_type ===
                "agent_debate"
            ) {

                setDebateRounds(

                    (previous) =>
                        previous + 1
                )
            }

            // ==========================================
            // PARTICIPATING AGENTS
            // ==========================================

            if (

                event.participating_agents
            ) {

                setActiveAgents(

                    event.participating_agents
                )
            }

            // ==========================================
            // DYNAMIC AGENTS
            // ==========================================

            if (

                event.payload?.agents
            ) {

                setActiveAgents(

                    event.payload.agents
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
    // CONSENSUS COLOR
    // ==========================================

    const consensusColor = (

        consensusScore >= 0.75

            ? "text-green-400"

            : consensusScore >= 0.5

                ? "text-yellow-400"

                : "text-red-400"
    )


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="

                bg-gradient-to-br

                from-slate-950
                via-slate-900
                to-black

                border
                border-[#4a8c70]/20

                rounded-2xl

                p-6

                shadow-2xl
                shadow-[#82c0a4]/10

                overflow-hidden
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

                        <Network
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

                            Swarm Intelligence

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Autonomous Multi-Agent Cognition

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

                        <Users
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


                {/* CONSENSUS */}

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

                        <ShieldCheck
                            className="
                                w-4
                                h-4
                                text-green-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Consensus

                        </span>

                    </div>

                    <div
                        className={`
                            text-3xl
                            font-bold
                            ${consensusColor}
                        `}
                    >

                        {(consensusScore * 100)
                            .toFixed(0)}%

                    </div>

                </div>


                {/* DEBATE ROUNDS */}

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
                                text-[#82c0a4]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Debate Rounds

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {debateRounds}

                    </div>

                </div>

            </div>


            {/* ACTIVE AGENTS */}

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

                    Active Swarm

                </h3>

                <div
                    className="
                        flex
                        flex-wrap
                        gap-2
                    "
                >

                    {activeAgents.map(

                        (agent, index) => (

                            <div
                                key={index}

                                className="
                                    flex
                                    items-center
                                    gap-2

                                    px-3
                                    py-2

                                    rounded-lg

                                    bg-[#4a8c70]/10

                                    border
                                    border-[#82c0a4]/20

                                    text-[#96cead]
                                    text-sm
                                "
                            >

                                <Sparkles
                                    className="
                                        w-3
                                        h-3
                                    "
                                />

                                {agent}

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

                    Swarm Cognition Feed

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[420px]
                        overflow-y-auto
                    "
                >

                    {swarmEvents.map(

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

                                        <div
                                            className="
                                                w-2
                                                h-2
                                                rounded-full
                                                bg-[#4a8c70]
                                                animate-pulse
                                            "
                                        />

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

                                                bg-[#82c0a4]/10

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