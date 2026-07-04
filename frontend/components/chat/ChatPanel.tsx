"use client"
import { useEffect, useRef } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useChatStore } from "@/store/chatStore"
import { wsService } from "@/services/websocket"
import { apiUrl } from "@/lib/constants"
import ChatMessageItem from "./ChatMessage"
import TypingIndicator from "./TypingIndicator"
import ChatInput from "./ChatInput"
import { Brain, Search, Code2, FileText, Globe, Rocket } from "lucide-react"

const SUGGESTIONS = [
    { icon: Search,   label: "Research AI safety frameworks", prompt: "Research the latest breakthroughs in multi-agent AI systems" },
    { icon: Code2,    label: "Build a fraud detection system", prompt: "Design a fraud detection system using machine learning" },
    { icon: Brain,    label: "Design multi-agent architecture", prompt: "Design a multi-agent architecture for autonomous task execution" },
    { icon: Rocket,   label: "Build a RAG pipeline", prompt: "Design and implement a production-ready RAG pipeline with ChromaDB" },
]

export default function ChatPanel() {
    const store          = useChatStore()
    const bottomRef      = useRef<HTMLDivElement>(null)
    const streamingIdRef = useRef<string | null>(null)
    const chunksRef      = useRef(false)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [store.messages, store.isLoading])

    async function handleSend(text: string) {
        store.addMessage({
            id:        `user-${Date.now()}`,
            role:      "user",
            content:   text,
            timestamp: new Date().toISOString(),
        })

        const aiId = `ai-${Date.now()}`
        streamingIdRef.current = aiId
        chunksRef.current      = false

        store.addMessage({
            id:        aiId,
            role:      "assistant",
            content:   "",
            timestamp: new Date().toISOString(),
            streaming: true,
        })
        store.setStreamingId(aiId)
        store.setLoading(true)

        const unsubStream = wsService.subscribe((msg) => {
            if (msg.stream_chunk && streamingIdRef.current === aiId) {
                chunksRef.current = true
                useChatStore.getState().appendChunk(aiId, msg.stream_chunk as string)
            }
        })

        try {
            const res = await fetch(apiUrl("/orchestrate"), {
                method:  "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body:    JSON.stringify({ objective: text }),
            })

            if (res.ok) {
                const data = await res.json() as Record<string, unknown>
                if (!chunksRef.current) {
                    const content =
                        (data?.result   as string) ||
                        (data?.response as string) ||
                        (data?.output   as string) ||
                        JSON.stringify(data, null, 2)
                    useChatStore.getState().updateMessage(aiId, { content, streaming: false })
                } else {
                    useChatStore.getState().updateMessage(aiId, { streaming: false })
                }
            } else {
                throw new Error(`Backend returned ${res.status}: ${res.statusText}`)
            }
        } catch (err) {
            if (!chunksRef.current) {
                useChatStore.getState().updateMessage(aiId, {
                    content:   `**Connection Error**\n\n${(err as Error).message}\n\nEnsure the CortexPrime backend is running on port 8000.`,
                    streaming: false,
                })
            } else {
                useChatStore.getState().updateMessage(aiId, { streaming: false })
            }
        } finally {
            unsubStream()
            streamingIdRef.current = null
            store.setLoading(false)
            store.setStreamingId(null)
        }
    }

    const isEmpty = store.messages.length === 0

    return (
        <div
            className="flex h-full flex-col overflow-hidden rounded-2xl"
            style={{ background: "#ffffff", border: "1px solid #dceee4", boxShadow: "0 4px 16px rgba(26,26,26,0.06)" }}
        >
            <div
                className="flex items-center justify-between px-5 py-3.5 shrink-0"
                style={{ borderBottom: "1px solid #e8f5ee" }}
            >
                <div className="flex items-center gap-2.5">
                    <div className="relative">
                        <div
                            className="flex h-8 w-8 items-center justify-center rounded-xl text-white shadow-md"
                            style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}
                        >
                            <Brain size={15} />
                        </div>
                        {store.isLoading && (
                            <motion.div
                                className="absolute inset-0 rounded-xl"
                                style={{ border: "2px solid rgba(130,192,164,0.5)" }}
                                animate={{ scale: [1, 1.5], opacity: [0.7, 0] }}
                                transition={{ duration: 1, repeat: Infinity }}
                            />
                        )}
                    </div>
                    <div>
                        <h2 className="text-sm font-bold leading-none text-[#1a1a1a]">
                            AI Command Interface
                        </h2>
                        <p className="mt-0.5 text-[10px] text-[#737373]">Autonomous cognitive execution</p>
                    </div>
                </div>

                <AnimatePresence>
                    {store.isLoading && (
                        <motion.div
                            initial={{ opacity: 0, x: 10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: 10 }}
                            className="flex items-center gap-2"
                        >
                            <div className="flex gap-1">
                                {[0, 1, 2].map((i) => (
                                    <motion.div
                                        key={i}
                                        className="h-1 w-1 rounded-full bg-[#82c0a4]"
                                        animate={{ scale: [1, 1.6, 1], opacity: [0.4, 1, 0.4] }}
                                        transition={{ duration: 0.6, repeat: Infinity, delay: i * 0.15 }}
                                    />
                                ))}
                            </div>
                            <span className="text-[11px] font-medium text-[#4a8c70]">Processing</span>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            <div className="cortex-scroll flex-1 overflow-y-auto px-5 py-5 bg-[#f0f7f4]">
                {isEmpty ? (
                    <div className="flex h-full flex-col items-center justify-center gap-6 py-8">
                        <motion.div
                            className="flex h-16 w-16 items-center justify-center rounded-2xl text-white"
                            style={{
                                background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                                boxShadow: "0 8px 32px rgba(130,192,164,0.25)",
                            }}
                            animate={{ boxShadow: ["0 8px 32px rgba(130,192,164,0.25)", "0 12px 40px rgba(130,192,164,0.35)", "0 8px 32px rgba(130,192,164,0.25)"] }}
                            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                        >
                            <Brain size={28} />
                        </motion.div>

                        <div className="text-center">
                            <h3 className="text-xl font-black text-[#1a1a1a]">CortexPrime Runtime</h3>
                            <p className="mt-1.5 text-sm text-[#737373] max-w-xs leading-relaxed">
                                Your AI companion — powered by orchestrated cognition.
                            </p>
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                            {SUGGESTIONS.map((s, i) => (
                                <motion.button
                                    key={i}
                                    initial={{ opacity: 0, y: 8 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ delay: i * 0.08 + 0.25 }}
                                    onClick={() => handleSend(s.prompt)}
                                    className="group flex items-start gap-2.5 rounded-2xl px-3.5 py-3 text-left transition-all hover:-translate-y-0.5"
                                    style={{
                                        background: "#ffffff",
                                        border: "1px solid #dceee4",
                                        boxShadow: "0 2px 8px rgba(26,26,26,0.04)",
                                    }}
                                >
                                    <s.icon size={14} className="mt-0.5 shrink-0 text-[#4a8c70]" />
                                    <span className="text-xs text-[#4a4a4a] group-hover:text-[#4a8c70] transition-colors">{s.label}</span>
                                </motion.button>
                            ))}
                        </div>
                    </div>
                ) : (
                    <div className="space-y-5">
                        <AnimatePresence initial={false}>
                            {store.messages.map((msg) => (
                                <ChatMessageItem key={msg.id} message={msg} />
                            ))}
                        </AnimatePresence>

                        {store.isLoading && !store.streamingId && <TypingIndicator />}

                        <div ref={bottomRef} />
                    </div>
                )}
            </div>

            <div className="shrink-0 p-4 bg-white" style={{ borderTop: "1px solid #e8f5ee" }}>
                <ChatInput onSend={handleSend} disabled={store.isLoading} />
            </div>
        </div>
    )
}
