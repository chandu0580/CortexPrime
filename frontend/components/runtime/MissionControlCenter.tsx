"use client"

import { useEffect, useState } from "react"

import {

    Activity,

    BrainCircuit,

    Bot,

    Cpu,

    Workflow,

    CheckCircle2,

    AlertTriangle,

    Sparkles,

    TimerReset,

    Orbit

} from "lucide-react"

import { runtimeService } from "@/services/runtime"


// ==========================================
// TYPES
// ==========================================

interface Mission {

    goal: string

    status: string

    started_at?: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function MissionControlCenter() {

    // ======================================
    // STATE
    // ======================================

    const [

        activeMissions,

        setActiveMissions

    ] = useState<any>({})

    const [

        completedMissions,

        setCompletedMissions

    ] = useState<any[]>([])

    const [

        activeLoops,

        setActiveLoops

    ] = useState<any>({})

    const [

        loading,

        setLoading

    ] = useState(true)


    // ======================================
    // LOAD DATA
    // ======================================

    const loadTelemetry = async () => {

        try {

            const [

                activeMissionData,

                completedMissionData,

                activeLoopData

            ] = await Promise.all([

                runtimeService.getActiveMissions(),

                runtimeService.getCompletedMissions(),

                runtimeService.getActiveLoops()
            ])

            setActiveMissions(

                activeMissionData
                ?.active_missions || {}
            )

            setCompletedMissions(

                completedMissionData
                ?.completed_missions || []
            )

            setActiveLoops(

                activeLoopData
                ?.active_loops || {}
            )

        } catch (error) {

            console.error(error)

        } finally {

            setLoading(false)
        }
    }


    // ======================================
    // EFFECT
    // ======================================

    useEffect(() => {

        loadTelemetry()

        const interval = setInterval(

            loadTelemetry,

            3000
        )

        return () =>

            clearInterval(interval)

    }, [])


    // ======================================
    // COUNTS
    // ======================================

    const activeMissionCount = Object.keys(
        activeMissions
    ).length

    const activeLoopCount = Object.keys(
        activeLoops
    ).length


    // ======================================
    // UI
    // ======================================

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

                        <Orbit
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

                            Mission Control Center

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Autonomous AI Orchestration Runtime

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
                        "
                    >

                        SYSTEM ONLINE

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


                {/* ACTIVE LOOPS */}

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
                                text-[#4a8c70]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Reasoning Loops

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {activeLoopCount}

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

                            Completed Missions

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-white
                        "
                    >

                        {completedMissions.length}

                    </div>

                </div>


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

                        <Cpu
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

                            AI Runtime

                        </span>

                    </div>

                    <div
                        className="
                            text-xl
                            font-bold
                            text-emerald-400
                        "
                    >

                        ACTIVE

                    </div>

                </div>

            </div>


            {/* ACTIVE MISSIONS */}

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

                    Active Autonomous Missions

                </h3>

                <div
                    className="
                        space-y-3
                    "
                >

                    {Object.entries(
                        activeMissions
                    ).map(

                        (
                            [id, mission]: any
                        ) => (

                            <div
                                key={id}

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

                                        <Bot
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

                                                {
                                                    mission.goal
                                                }

                                            </div>

                                            <div
                                                className="
                                                    text-xs
                                                    text-slate-500
                                                "
                                            >

                                                {
                                                    mission.started_at
                                                }

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
                                            "
                                        >

                                            RUNNING

                                        </span>

                                    </div>

                                </div>

                            </div>
                        )
                    )}

                    {activeMissionCount === 0 && (

                        <div
                            className="
                                rounded-xl

                                bg-white/5

                                border
                                border-white/10

                                p-10

                                text-center
                            "
                        >

                            <Sparkles
                                className="
                                    w-10
                                    h-10

                                    mx-auto

                                    mb-3

                                    text-[#82c0a4]
                                "
                            />

                            <h3
                                className="
                                    text-lg
                                    font-semibold
                                    text-white
                                "
                            >

                                No Active Missions

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    mt-2
                                "
                            >

                                CortexPrime is waiting
                                for autonomous execution requests.

                            </p>

                        </div>
                    )}

                </div>

            </div>


            {/* COMPLETED */}

            <div>

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300

                        mb-3
                    "
                >

                    Completed Missions

                </h3>

                <div
                    className="
                        space-y-3
                    "
                >

                    {completedMissions
                        .slice(-5)
                        .reverse()
                        .map(

                            (
                                mission,
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

                                            <CheckCircle2
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

                                                    {
                                                        mission.goal
                                                    }

                                                </div>

                                                <div
                                                    className="
                                                        text-xs
                                                        text-slate-500
                                                    "
                                                >

                                                    Completed autonomous execution

                                                </div>

                                            </div>

                                        </div>

                                        <span
                                            className="
                                                text-xs
                                                text-emerald-300
                                            "
                                        >

                                            SUCCESS

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