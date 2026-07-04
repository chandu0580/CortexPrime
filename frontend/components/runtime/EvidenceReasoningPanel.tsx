"use client"

import { useEffect, useState } from "react"

import {

    ShieldCheck,

    AlertTriangle,

    Brain,

    Activity,

    CheckCircle2,

    Globe,

    Link2,

    Sparkles

} from "lucide-react"

import {

    websocketService,

    CognitionEvent

} from "@/services/websocketService"


// ==========================================
// EVIDENCE NODE
// ==========================================

interface EvidenceNode {

    id: string

    title?: string

    url?: string

    confidence?: number

    supports_claim?: boolean
}


// ==========================================
// COMPONENT
// ==========================================

export default function EvidenceReasoningPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [

        evidenceNodes,

        setEvidenceNodes

    ] = useState<EvidenceNode[]>([])

    const [

        confidenceScore,

        setConfidenceScore

    ] = useState<number>(0)

    const [

        hallucinationScore,

        setHallucinationScore

    ] = useState<number>(0)

    const [

        contradictions,

        setContradictions

    ] = useState<string[]>([])

    const [

        claimValidation,

        setClaimValidation

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
            // EVIDENCE GRAPH
            // ==========================================

            if (

                event.event_type ===
                "evidence_graph_completed"
            ) {

                const graph =

                    event.payload
                    ?.evidence_graph

                if (!graph) {

                    return
                }

                setEvidenceNodes(

                    graph.evidence_nodes || []
                )

                setConfidenceScore(

                    graph.overall_confidence || 0
                )

                setHallucinationScore(

                    graph.hallucination_score || 0
                )

                setContradictions(

                    graph.contradictions || []
                )
            }

            // ==========================================
            // CLAIM VALIDATION
            // ==========================================

            if (

                event.event_type ===
                "claim_validation"
            ) {

                setClaimValidation(

                    event.payload
                    ?.supported || false
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
    // CONFIDENCE COLOR
    // ==========================================

    const getConfidenceColor = (

        score: number
    ) => {

        if (score >= 0.75) {

            return "text-emerald-400"
        }

        if (score >= 0.5) {

            return "text-yellow-400"
        }

        return "text-red-400"
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

                        <ShieldCheck
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

                            Evidence Reasoning

                        </h2>

                        <p
                            className="
                                text-sm
                                text-slate-400
                            "
                        >

                            Trust Validation &
                            Citation Grounding

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

                {/* CONFIDENCE */}

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
                                text-[#4a8c70]
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Confidence

                        </span>

                    </div>

                    <div
                        className={`
                            text-3xl
                            font-bold

                            ${getConfidenceColor(
                                confidenceScore
                            )}
                        `}
                    >

                        {Math.round(
                            confidenceScore * 100
                        )}%

                    </div>

                </div>


                {/* HALLUCINATION */}

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
                                text-yellow-400
                            "
                        />

                        <span
                            className="
                                text-sm
                                text-slate-300
                            "
                        >

                            Hallucination Risk

                        </span>

                    </div>

                    <div
                        className="
                            text-3xl
                            font-bold
                            text-yellow-400
                        "
                    >

                        {Math.round(
                            hallucinationScore * 100
                        )}%

                    </div>

                </div>


                {/* VALIDATION */}

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

                            Claim Status

                        </span>

                    </div>

                    <div
                        className={`
                            text-2xl
                            font-bold

                            ${
                                claimValidation

                                    ? `
                                        text-emerald-400
                                      `

                                    : `
                                        text-red-400
                                      `
                            }
                        `}
                    >

                        {claimValidation

                            ? "Supported"

                            : "Weak"}

                    </div>

                </div>

            </div>


            {/* CONTRADICTIONS */}

            {contradictions.length > 0 && (

                <div
                    className="
                        mb-6

                        rounded-xl

                        bg-red-500/10

                        border
                        border-red-400/20

                        p-4
                    "
                >

                    <div
                        className="
                            flex
                            items-center
                            gap-2
                            mb-3
                        "
                    >

                        <AlertTriangle
                            className="
                                w-5
                                h-5
                                text-red-400
                            "
                        />

                        <h3
                            className="
                                text-sm
                                font-semibold
                                text-red-300
                            "
                        >

                            Contradictions Detected

                        </h3>

                    </div>

                    <div
                        className="
                            space-y-2
                        "
                    >

                        {contradictions.map(

                            (
                                contradiction,
                                index
                            ) => (

                                <div
                                    key={index}

                                    className="
                                        text-sm
                                        text-red-200
                                    "
                                >

                                    • {contradiction}

                                </div>
                            )
                        )}

                    </div>

                </div>
            )}


            {/* EVIDENCE SOURCES */}

            <div>

                <h3
                    className="
                        text-sm
                        font-semibold
                        text-slate-300
                        mb-3
                    "
                >

                    Evidence Sources

                </h3>

                <div
                    className="
                        space-y-3

                        max-h-[500px]
                        overflow-y-auto
                    "
                >

                    {evidenceNodes.map(

                        (node) => (

                            <div
                                key={node.id}

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
                                        items-start
                                        justify-between
                                        gap-4
                                    "
                                >

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
                                                    font-medium
                                                    text-white
                                                "
                                            >

                                                {node.title ||
                                                    "Untitled Source"}

                                            </span>

                                        </div>

                                        {node.url && (

                                            <div
                                                className="
                                                    flex
                                                    items-center
                                                    gap-2
                                                    mb-3
                                                "
                                            >

                                                <Link2
                                                    className="
                                                        w-3
                                                        h-3
                                                        text-slate-400
                                                    "
                                                />

                                                <a
                                                    href={node.url}

                                                    target="_blank"

                                                    rel="noopener noreferrer"

                                                    className="
                                                        text-xs
                                                        text-[#96cead]

                                                        hover:text-[#96cead]

                                                        truncate
                                                    "
                                                >

                                                    {node.url}

                                                </a>

                                            </div>
                                        )}

                                        <div
                                            className="
                                                flex
                                                items-center
                                                gap-3
                                            "
                                        >

                                            <div
                                                className={`
                                                    px-2
                                                    py-1

                                                    rounded-md

                                                    text-xs
                                                    font-medium

                                                    ${
                                                        node.supports_claim

                                                            ? `
                                                                bg-emerald-500/10
                                                                text-emerald-300
                                                                border
                                                                border-emerald-400/20
                                                              `

                                                            : `
                                                                bg-red-500/10
                                                                text-red-300
                                                                border
                                                                border-red-400/20
                                                              `
                                                    }
                                                `}
                                            >

                                                {node.supports_claim

                                                    ? "Supports Claim"

                                                    : "Weak Evidence"}

                                            </div>

                                        </div>

                                    </div>

                                    {/* SCORE */}

                                    <div
                                        className="
                                            text-right
                                        "
                                    >

                                        <div
                                            className={`
                                                text-xl
                                                font-bold

                                                ${getConfidenceColor(
                                                    node.confidence || 0
                                                )}
                                            `}
                                        >

                                            {Math.round(
                                                (node.confidence || 0) * 100
                                            )}%

                                        </div>

                                        <div
                                            className="
                                                text-xs
                                                text-slate-400
                                            "
                                        >

                                            confidence

                                        </div>

                                    </div>

                                </div>

                            </div>
                        )
                    )}

                    {evidenceNodes.length === 0 && (

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

                                Awaiting Evidence Graph

                            </h3>

                            <p
                                className="
                                    text-slate-400
                                    max-w-md
                                "
                            >

                                CortexPrime will analyze,
                                validate, and visualize
                                evidence confidence during
                                deep research execution.

                            </p>

                        </div>
                    )}

                </div>

            </div>

        </div>
    )
}