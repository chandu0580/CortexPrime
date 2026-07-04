"use client"

import { useState } from "react"


// ==========================================
// COMPONENT
// ==========================================

export default function ExecutionControlPanel() {

    // ==========================================
    // STATE
    // ==========================================

    const [objective, setObjective] =
        useState("")

    const [loading, setLoading] =
        useState(false)

    const [response, setResponse] =
        useState<any>(null)

    const [error, setError] =
        useState("")


    // ==========================================
    // EXECUTE ORCHESTRATION
    // ==========================================

    const executeObjective = async () => {

        if (!objective.trim()) {

            setError(
                "Please enter an objective"
            )

            return
        }

        try {

            setLoading(true)

            setError("")

            setResponse(null)

            const apiResponse = await fetch(

                "http://127.0.0.1:8000/orchestrate",

                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        objective
                    })
                }
            )

            if (!apiResponse.ok) {

                throw new Error(
                    "Backend request failed"
                )
            }

            const result =
                await apiResponse.json()

            setResponse(result)

        } catch (err: any) {

            console.error(err)

            setError(

                err.message ||

                "Execution failed"
            )

        } finally {

            setLoading(false)
        }
    }


    // ==========================================
    // UI
    // ==========================================

    return (

        <div
            className="bg-white border border-gray-200 rounded-2xl shadow-sm p-6"
        >

            {/* HEADER */}

            <div className="mb-6">

                <h2
                    className="text-3xl font-black"
                >

                    ⚡ CortexPrime Control Center

                </h2>

                <p
                    className="text-gray-500 mt-2"
                >

                    Execute realtime multi-agent cognitive workflows

                </p>

            </div>


            {/* INPUT */}

            <div className="space-y-4">

                <textarea

                    value={objective}

                    onChange={(event) =>

                        setObjective(
                            event.target.value
                        )
                    }

                    placeholder={

                        "Example: Research the future of autonomous AI systems and generate a strategic execution plan..."
                    }

                    className="w-full min-h-40 border border-gray-300 rounded-xl p-4 outline-none focus:ring-2 focus:ring-blue-500 resize-none"

                />


                {/* BUTTON */}

                <button

                    onClick={executeObjective}

                    disabled={loading}

                    className="px-6 py-3 rounded-xl bg-black text-white font-semibold hover:opacity-90 transition disabled:opacity-50"

                >

                    {

                        loading

                            ? "🧠 CortexPrime Executing..."

                            : "🚀 Execute Objective"
                    }

                </button>

            </div>


            {/* ERROR */}

            {

                error && (

                    <div
                        className="mt-6 border border-red-200 bg-red-50 text-red-600 rounded-xl p-4"
                    >

                        {error}

                    </div>
                )
            }


            {/* RESPONSE */}

            {

                response && (

                    <div
                        className="mt-8 border border-gray-200 rounded-2xl p-5 bg-gray-50"
                    >

                        <h3
                            className="text-xl font-bold mb-4"
                        >

                            🧠 Execution Response

                        </h3>

                        <div
                            className="max-h-[500px] overflow-auto rounded-xl bg-black text-green-400 p-4 text-sm"
                        >

                            <pre
                                className="whitespace-pre-wrap"
                            >

                                {

                                    JSON.stringify(

                                        response,

                                        null,

                                        2
                                    )
                                }

                            </pre>

                        </div>

                    </div>
                )
            }

        </div>
    )
}