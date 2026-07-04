"use client"

import { useState } from "react"

import {

    Bot,

    Send,

    Sparkles,

    Loader2,

    Terminal,

    BrainCircuit

} from "lucide-react"

import { api } from "@/services/api"


// ==========================================
// TYPES
// ==========================================

interface ChatMessage {

    role: "user" | "assistant"

    content: string
}


// ==========================================
// COMPONENT
// ==========================================

export default function ExecutionChat() {

    // ======================================
    // STATE
    // ======================================

    const [

        input,

        setInput

    ] = useState("")

    const [

        loading,

        setLoading

    ] = useState(false)

    const [

        messages,

        setMessages

    ] = useState<ChatMessage[]>([

        {

            role: "assistant",

            content:
                (
                    "CortexPrime Autonomous "
                    + "Execution Platform Ready."
                )
        }
    ])


    // ======================================
    // EXECUTE
    // ======================================

    const executeGoal = async () => {

        if (!input.trim()) {

            return
        }

        const userMessage = {

            role:
                "user" as const,

            content:
                input
        }

        setMessages(

            (previous) => [

                ...previous,

                userMessage
            ]
        )

        const goal = input

        setInput("")

        setLoading(true)

        try {

            // ==================================
            // AUTONOMOUS EXECUTION
            // ==================================

            const result = await (

                api
                .post("/api/orchestrator/autonomous", {

                    goal,

                    max_iterations: 5,
                })
            )

            const response = JSON.stringify(

                result,

                null,

                2
            )

            setMessages(

                (previous) => [

                    ...previous,

                    {

                        role:
                            "assistant",

                        content:
                            response
                    }
                ]
            )

        } catch (error: any) {

            setMessages(

                (previous) => [

                    ...previous,

                    {

                        role:
                            "assistant",

                        content:
                            (
                                "Execution failed: "
                                + error.message
                            )
                    }
                ]
            )

        } finally {

            setLoading(false)
        }
    }


    // ======================================
    // UI
    // ======================================

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
                    gap-3
                    mb-6
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

                    <BrainCircuit
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

                        CortexPrime Execution Chat

                    </h2>

                    <p
                        className="
                            text-sm
                            text-slate-400
                        "
                    >

                        Autonomous AI Mission Runtime

                    </p>

                </div>

            </div>


            {/* CHAT */}

            <div
                className="
                    h-[500px]

                    overflow-y-auto

                    space-y-4

                    mb-4

                    pr-2
                "
            >

                {messages.map(

                    (
                        message,
                        index
                    ) => (

                        <div
                            key={index}

                            className={

                                `
                                flex

                                ${
                                    message.role ===
                                    "user"

                                        ? "justify-end"

                                        : "justify-start"
                                }
                                `
                            }
                        >

                            <div
                                className={

                                    `
                                    max-w-[85%]

                                    rounded-2xl

                                    px-4
                                    py-3

                                    whitespace-pre-wrap

                                    text-sm

                                    border

                                    ${
                                        message.role ===
                                        "user"

                                            ?

                                            `
                                            bg-[#4a8c70]/20
                                            border-[#82c0a4]/20
                                            text-[#e8f5ee]
                                            `

                                            :

                                            `
                                            bg-white/5
                                            border-white/10
                                            text-slate-200
                                            `
                                    }
                                    `
                                }
                            >

                                <div
                                    className="
                                        flex
                                        items-center
                                        gap-2
                                        mb-2
                                    "
                                >

                                    {message.role ===
                                    "assistant"

                                        ? (

                                            <Bot
                                                className="
                                                    w-4
                                                    h-4
                                                    text-[#4a8c70]
                                                "
                                            />

                                        )

                                        : (

                                            <Sparkles
                                                className="
                                                    w-4
                                                    h-4
                                                    text-[#96cead]
                                                "
                                            />

                                        )
                                    }

                                    <span
                                        className="
                                            text-xs
                                            opacity-70
                                        "
                                    >

                                        {message.role
                                            .toUpperCase()}

                                    </span>

                                </div>

                                {message.content}

                            </div>

                        </div>
                    )
                )}

                {loading && (

                    <div
                        className="
                            flex
                            justify-start
                        "
                    >

                        <div
                            className="
                                flex
                                items-center
                                gap-3

                                px-4
                                py-3

                                rounded-2xl

                                bg-white/5

                                border
                                border-white/10

                                text-slate-300
                            "
                        >

                            <Loader2
                                className="
                                    w-4
                                    h-4
                                    animate-spin
                                "
                            />

                            CortexPrime reasoning...

                        </div>

                    </div>
                )}

            </div>


            {/* INPUT */}

            <div
                className="
                    flex
                    items-center
                    gap-3
                "
            >

                <input

                    value={input}

                    onChange={(event) =>

                        setInput(
                            event.target.value
                        )
                    }

                    onKeyDown={(event) => {

                        if (
                            event.key === "Enter"
                        ) {

                            executeGoal()
                        }
                    }}

                    placeholder="
                        Enter autonomous mission...
                    "

                    className="

                        flex-1

                        bg-white/5

                        border
                        border-white/10

                        rounded-xl

                        px-4
                        py-3

                        text-white

                        outline-none

                        focus:border-[#82c0a4]/40
                    "
                />

                <button

                    onClick={executeGoal}

                    disabled={loading}

                    className="

                        flex
                        items-center
                        justify-center

                        w-12
                        h-12

                        rounded-xl

                        bg-[#4a8c70]/20

                        border
                        border-[#82c0a4]/20

                        hover:bg-[#4a8c70]/30

                        transition-all
                    "
                >

                    {loading

                        ? (

                            <Loader2
                                className="
                                    w-5
                                    h-5

                                    animate-spin

                                    text-[#96cead]
                                "
                            />

                        )

                        : (

                            <Send
                                className="
                                    w-5
                                    h-5

                                    text-[#96cead]
                                "
                            />
                        )
                    }

                </button>

            </div>


            {/* FOOTER */}

            <div
                className="
                    mt-4

                    flex
                    items-center
                    gap-2

                    text-xs
                    text-slate-500
                "
            >

                <Terminal
                    className="
                        w-4
                        h-4
                    "
                />

                Autonomous multi-agent cognition enabled

            </div>

        </div>
    )
}