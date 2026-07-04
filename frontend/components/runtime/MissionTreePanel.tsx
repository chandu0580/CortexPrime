
"use client"

import { useEffect, useState } from "react"

import {

    GitBranch,

    BrainCircuit,

    CheckCircle2,

    Activity,

    Sparkles,

    ChevronRight

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// MISSION NODE
// ==========================================

interface MissionNode {

    id?: string

    objective: string

    depth: number

    status?: string

    children?: MissionNode[]
}


// ==========================================
// COMPONENT
// ==========================================

export default function MissionTreePanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        missionTree,

        setMissionTree

    ] = useState<MissionNode | null>(
        null
    )

    const [

        executedSubgoals,

        setExecutedSubgoals

    ] = useState<string[]>([])


    // ==========================================
    // WEBSOCKET LISTENER
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        const handleEvent = (

            event: CognitionEvent
        ) => {

            // ==========================================
            // RECURSIVE PLAN TREE
            // ==========================================

            if (

                event.event_type ===
                "recursive_planning"

                &&

                event.payload?.plan_tree
            ) {

                setMissionTree(

                    event.payload.plan_tree
                )
            }

            // ==========================================
            // SUBGOAL EXECUTION
            // ==========================================

            if (

                event.event_type ===
                "subgoal_execution"
            ) {

                const subgoalResults =

                    event.payload
                    ?.subgoal_results

                if (

                    Array.isArray(
                        subgoalResults
                    )
                ) {

                    const completed =

                        subgoalResults.map(

                            (
                                result: any
                            ) =>

                                result.subgoal
                        )

                    setExecutedSubgoals(
                        completed
                    )
                }

                // ==========================================
                // SINGLE SUBGOAL EVENT
                // ==========================================

                if (

                    event.payload?.subgoal
                ) {

                    setExecutedSubgoals(

                        (previous) => [

                            ...previous,

                            event.payload.subgoal
                        ]
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
    // RENDER TREE
    // ==========================================

    const renderTree = (

        node: MissionNode
    ) => {

        const isCompleted =

            executedSubgoals.includes(
                node.objective
            )

        return (

            <div
                key={node.id}
                className="
                    ml-2
                    mt-3
                "
            >

                {/* NODE */}

                <div
                    className={`
                        relative

                        flex
                        items-start
                        gap-3

                        rounded-xl

                        border

                        p-4

                        transition-all
                        duration-300

                        ${
                            isCompleted

                                ? `
                                    bg-emerald-500/10
                                    border-emerald-400/30
                                  `

                                : `
                                    bg-white/5
                                    border-white/10
                                  `
                        }
                    `}
                >

                    {/* ICON */}

                    <div
                        className={`
                            mt-1

                            ${
                                isCompleted

                                    ? `
                                        text-emerald-400
                                      `

                                    : `
                                        text-[#4a8c70]
                                      `
                            }
                        `}
                    >

                        {isCompleted ? (

                            <CheckCircle2
                                className="
                                    w-5
                                    h-5
                                "
                            />

                        ) : (

                            <BrainCircuit
                                className="
                                    w-5
                                    h-5
                                "
                            />
                        )}

                    </div>

                    {/* CONTENT */}

                    <div
                        className="
                            flex-1
                        "
                    >

                        <div
                            className="
                                flex
                                items-center
                                gap-2
                                mb-1
                            "
                        >

                            <span
                                className="
                                    text-white
                                    font-medium
                                "
                            >

                                {node.objective}

                            </span>

                            <span
                                className="
                                    text-xs
                                    text-slate-400
                                "
                            >

                                Depth {node.depth}

                            </span>

                        </div>

                        <div
                            className="
                                flex
                                items-center
                                gap-2
                                mt-2
                            "
                        >

                            <div
                                className={`
                                    px-2
                                    py-1

                                    rounded-md

                                    text-xs

                                    ${
                                        isCompleted

                                            ? `
                                                bg-emerald-500/20
                                                text-emerald-300
                                              `

                                            : `
                                                bg-[#4a8c70]/20
                                                text-[#96cead]
                                              `
                                    }
                                `}
                            >

                                {isCompleted

                                    ? "Completed"

                                    : "Pending"}
                            </div>

                        </div>

                    </div>

                </div>

                {/* CHILDREN */}

                {node.children &&
                    node.children.length > 0 && (

                    <div
                        className="
                            ml-8
                            border-l
                            border-[#4a8c70]/20
                            pl-4
                        "
                    >

                        {node.children.map(

                            (child) =>

                                renderTree(
                                    child
                                )
                        )}

                    </div>
                )}

            </div>
        )
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

                        <GitBranch
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

                            Mission Tree

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Recursive Autonomous Planning

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


            {/* TREE */}

            <div
                className="
                    max-h-[650px]
                    overflow-y-auto
                    pr-2
                "
            >

                {missionTree ? (

                    renderTree(
                        missionTree
                    )

                ) : (

                    <div
                        className="
                            flex
                            flex-col
                            items-center
                            justify-center

                            py-20

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

                            Waiting for Mission

                        </h3>

                        <p
                            className="
                                text-slate-400
                                max-w-md
                            "
                        >

                            CortexPrime will generate
                            recursive mission trees
                            dynamically during execution.

                        </p>

                    </div>
                )}

            </div>

        </div>
    )
}