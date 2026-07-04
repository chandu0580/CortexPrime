"use client"

import {
    useEffect,
    useState,
    useMemo
} from "react"

import ReactFlow, {
    Background,
    Controls,
    Edge,
    Node
} from "reactflow"

import "reactflow/dist/style.css"

import {
    websocketService,
    CognitionEvent
} from "@/services/websocketService"


// ==========================================
// INITIAL NODES
// ==========================================

const initialNodes: Node[] = [

    {
        id: "research",

        position: {
            x: 100,
            y: 100
        },

        data: {
            label: "🔍 Research"
        },

        style: {
            background: "#ffffff",
            border: "2px solid #4a8c70",
            borderRadius: "12px",
            padding: 10
        }
    },

    {
        id: "planner",

        position: {
            x: 400,
            y: 100
        },

        data: {
            label: "🧠 Planner"
        },

        style: {
            background: "#ffffff",
            border: "2px solid #4a8c70",
            borderRadius: "12px",
            padding: 10
        }
    },

    {
        id: "critic",

        position: {
            x: 700,
            y: 100
        },

        data: {
            label: "⚠️ Critic"
        },

        style: {
            background: "#ffffff",
            border: "2px solid #4a8c70",
            borderRadius: "12px",
            padding: 10
        }
    },

    {
        id: "optimizer",

        position: {
            x: 400,
            y: 300
        },

        data: {
            label: "⚙️ Optimizer"
        },

        style: {
            background: "#ffffff",
            border: "2px solid #4a8c70",
            borderRadius: "12px",
            padding: 10
        }
    }
]


// ==========================================
// INITIAL EDGES
// ==========================================

const initialEdges: Edge[] = [

    {
        id: "r-p",

        source: "research",

        target: "planner",

        animated: true
    },

    {
        id: "p-c",

        source: "planner",

        target: "critic",

        animated: true
    },

    {
        id: "c-p",

        source: "critic",

        target: "planner",

        animated: true
    },

    {
        id: "p-o",

        source: "planner",

        target: "optimizer",

        animated: true
    }
]


// ==========================================
// COMPONENT
// ==========================================

export default function CognitionGraph() {

    const [nodes, setNodes] = useState(
        initialNodes
    )

    // ==========================================
    // MEMOIZED EDGES
    // ==========================================

    const memoizedEdges = useMemo(
        () => initialEdges,
        []
    )

    // ==========================================
    // NODE STATUS ENGINE
    // ==========================================

    const updateNodeStatus = (

        nodeId: string,

        status: (
            "idle"
            |
            "running"
            |
            "completed"
            |
            "failed"
        )
    ) => {

        let borderColor =
            "#4a8c70"

        let glowColor =
            "none"

        // ==========================================
        // STATUS COLORS
        // ==========================================

        if (
            status === "running"
        ) {

            borderColor =
                "#facc15"

            glowColor =
                "0px 0px 20px rgba(250,204,21,0.8)"
        }

        if (
            status === "completed"
        ) {

            borderColor =
                "#22c55e"

            glowColor =
                "0px 0px 20px rgba(34,197,94,0.7)"
        }

        if (
            status === "failed"
        ) {

            borderColor =
                "#ef4444"

            glowColor =
                "0px 0px 20px rgba(239,68,68,0.7)"
        }

        setNodes(

            (previousNodes) =>

                previousNodes.map(

                    (node) => {

                        if (
                            node.id === nodeId
                        ) {

                            return {

                                ...node,

                                style: {

                                    ...node.style,

                                    border:
                                        `3px solid ${borderColor}`,

                                    boxShadow:
                                        glowColor
                                }
                            }
                        }

                        return node
                    }
                )
        )
    }

    // ==========================================
    // WEBSOCKET EVENTS
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        websocketService.subscribe(

            (
                event: CognitionEvent
            ) => {

                console.log(
                    "🧠 Graph Event:",
                    event
                )

                const message = (

                    event.event ||

                    event.message ||

                    ""

                ).toLowerCase()

                // ==========================================
                // RESEARCH
                // ==========================================

                if (
                    message.includes(
                        "research"
                    )
                ) {

                    updateNodeStatus(
                        "research",
                        "running"
                    )

                    setTimeout(() => {

                        updateNodeStatus(
                            "research",
                            "completed"
                        )

                    }, 1500)
                }

                // ==========================================
                // PLANNER
                // ==========================================

                if (
                    message.includes(
                        "planner"
                    )
                ) {

                    updateNodeStatus(
                        "planner",
                        "running"
                    )

                    setTimeout(() => {

                        updateNodeStatus(
                            "planner",
                            "completed"
                        )

                    }, 1500)
                }

                // ==========================================
                // CRITIC
                // ==========================================

                if (
                    message.includes(
                        "critic"
                    )
                ) {

                    updateNodeStatus(
                        "critic",
                        "running"
                    )

                    setTimeout(() => {

                        updateNodeStatus(
                            "critic",
                            "completed"
                        )

                    }, 1500)
                }

                // ==========================================
                // OPTIMIZER
                // ==========================================

                if (
                    message.includes(
                        "optimizer"
                    )
                ) {

                    updateNodeStatus(
                        "optimizer",
                        "running"
                    )

                    setTimeout(() => {

                        updateNodeStatus(
                            "optimizer",
                            "completed"
                        )

                    }, 1500)
                }
            }
        )

        return () => {

            websocketService.disconnect()
        }

    }, [])

    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="w-full h-[600px] rounded-2xl overflow-hidden border bg-white"
        >

            <ReactFlow

                nodes={nodes}

                edges={memoizedEdges}

                fitView

            >

                <Background />

                <Controls />

            </ReactFlow>

        </div>
    )
}