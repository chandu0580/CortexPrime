"use client"

import {
    useEffect,
    useState
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
// STATIC DATA
// ==========================================

const NODES: Node[] = [

    {
        id: "research",

        position: {
            x: 100,
            y: 100
        },

        data: {
            label: "🔎 Research"
        },

        style: {
            border: "2px solid #4a8c70",
            borderRadius: "16px",
            padding: 10,
            width: 220
        }
    },

    {
        id: "planner",

        position: {
            x: 450,
            y: 100
        },

        data: {
            label: "🧠 Planner"
        },

        style: {
            border: "2px solid #4a8c70",
            borderRadius: "16px",
            padding: 10,
            width: 220
        }
    },

    {
        id: "critic",

        position: {
            x: 800,
            y: 100
        },

        data: {
            label: "⚠️ Critic"
        },

        style: {
            border: "2px solid #4a8c70",
            borderRadius: "16px",
            padding: 10,
            width: 220
        }
    },

    {
        id: "optimizer",

        position: {
            x: 450,
            y: 320
        },

        data: {
            label: "⚙️ Optimizer"
        },

        style: {
            border: "2px solid #4a8c70",
            borderRadius: "16px",
            padding: 10,
            width: 220
        }
    }
]


const EDGES: Edge[] = [

    {
        id: "e1",
        source: "research",
        target: "planner",
        animated: true
    },

    {
        id: "e2",
        source: "planner",
        target: "critic",
        animated: true
    },

    {
        id: "e3",
        source: "planner",
        target: "optimizer",
        animated: true
    }
]


// ==========================================
// COMPONENT
// ==========================================

export default function CognitionGraph() {

    const [nodes, setNodes] =
        useState<Node[]>(NODES)

    // ==========================================
    // CONNECT WEBSOCKET
    // ==========================================

    useEffect(() => {

        websocketService.connect()

        websocketService.subscribe(

            (
                event: CognitionEvent
            ) => {

                const message = (

                    event.event ||

                    event.message ||

                    ""

                ).toLowerCase()

                setNodes(

                    (
                        previous
                    ) =>

                        previous.map(

                            (
                                node
                            ) => {

                                const active =

                                    message.includes(
                                        node.id
                                    )

                                return {

                                    ...node,

                                    style: {

                                        ...node.style,

                                        backgroundColor:

                                            active

                                                ? "#dbeafe"

                                                : "white",

                                        border:

                                            active

                                                ? "3px solid #2563eb"

                                                : "2px solid #4a8c70"
                                    }
                                }
                            }
                        )
                )
            }
        )

    }, [])

    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="h-[500px] bg-white rounded-2xl border overflow-hidden"
        >

            <ReactFlow

                nodes={nodes}

                edges={EDGES}

                fitView={true}

            >

                <Background />

                <Controls />

            </ReactFlow>

        </div>
    )
}