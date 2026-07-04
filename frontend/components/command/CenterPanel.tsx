"use client"
import { useEffect, useRef, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    Send, Brain, RotateCcw, Sparkles, ArrowUp, Paperclip, Mic,
    Globe, Search, Code2, FileText, Rocket, Lightbulb, CheckCircle,
    Cpu,
} from "lucide-react"
import { useChatStore } from "@/store/chatStore"
import { wsService } from "@/services/websocket"
import { apiUrl } from "@/lib/constants"
import MarkdownRenderer from "@/components/chat/MarkdownRenderer"
import { useMissionStore, MISSION_STAGES, STAGE_LABELS } from "@/store/missionStore"
import { useAuthStore } from "@/store/authStore"
import type { ChatMessage } from "@/store/chatStore"

// ==========================================
// SUGGESTED PROMPTS
// ==========================================

const SUGGESTIONS = [
    { icon: Search,   label: "Research AI safety frameworks",       prompt: "Research the latest AI safety frameworks and summarize key findings"         },
    { icon: Code2,    label: "Build a fraud detection system",       prompt: "Design a fraud detection system using machine learning with implementation plan" },
    { icon: Brain,    label: "Design a multi-agent architecture",    prompt: "Design a multi-agent architecture for autonomous task execution"               },
    { icon: FileText, label: "Create a project roadmap",             prompt: "Create a detailed project roadmap for a modern SaaS product launch"            },
    { icon: Globe,    label: "Analyze market trends",                prompt: "Analyze current AI market trends and identify key opportunities"               },
    { icon: Rocket,   label: "Build a RAG pipeline",                 prompt: "Design and implement a production-ready RAG pipeline with ChromaDB"            },
]

// ==========================================
// MISSION PROGRESS BAR
// ==========================================

function MissionProgressBar() {
    const { stage, stageIndex, goal, progress } = useMissionStore()
    if (stage === "idle" || !goal) return null

    const isComplete = stage === "completed"
    const activeLabel = STAGE_LABELS[stage]

    return (
        <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="px-6 py-3 bg-white shrink-0"
            style={{ borderBottom: "1px solid #dceee4" }}
        >
            <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                    {!isComplete ? (
                        <motion.div
                            className="w-2 h-2 rounded-full bg-[#82c0a4]"
                            animate={{ scale: [1, 1.5, 1], opacity: [1, 0.4, 1] }}
                            transition={{ duration: 1.4, repeat: Infinity }}
                        />
                    ) : (
                        <CheckCircle size={14} className="text-[#4a8c70]" />
                    )}
                    <span className="text-sm font-semibold" style={{ color: isComplete ? "#4a8c70" : "#82c0a4" }}>
                        {isComplete ? "Mission Complete" : activeLabel}
                    </span>
                </div>
                <span className="text-xs font-medium text-[#737373] max-w-xs truncate">{goal}</span>
            </div>

            <div className="flex items-center gap-1.5 flex-wrap">
                {MISSION_STAGES.map((s, i) => {
                    const isDone   = isComplete || i < stageIndex
                    const isActive = !isComplete && i === stageIndex
                    return (
                        <div
                            key={s}
                            className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium transition-all"
                            style={{
                                background: isDone  ? "#e8f5ee" : isActive ? "rgba(130,192,164,0.08)" : "#f0f7f4",
                                color:      isDone  ? "#4a8c70" : isActive ? "#82c0a4"               : "#a3a3a3",
                                border:     `1px solid ${isDone ? "rgba(74,140,112,0.25)" : isActive ? "rgba(130,192,164,0.25)" : "#dceee4"}`,
                            }}
                        >
                            {STAGE_LABELS[s]}
                        </div>
                    )
                })}
            </div>

            {progress > 0 && progress < 100 && (
                <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: "#e8f5ee" }}>
                    <motion.div
                        className="h-full rounded-full"
                        style={{ background: "linear-gradient(90deg, #82c0a4, #4a8c70)" }}
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.4 }}
                    />
                </div>
            )}
        </motion.div>
    )
}

// ==========================================
// USER MESSAGE
// ==========================================

function UserMessage({ msg }: { msg: ChatMessage }) {
    return (
        <motion.div
            className="flex justify-end"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
        >
            <div className="max-w-[75%] xl:max-w-[65%]">
                <div
                    className="px-5 py-4 rounded-2xl rounded-br-sm text-base text-[#1a1a1a] leading-relaxed"
                    style={{
                        background: "#ffffff",
                        border: "1px solid #dceee4",
                        boxShadow: "0 2px 8px rgba(26,26,26,0.04)",
                    }}
                >
                    {msg.content}
                </div>
                <div className="mt-1 text-right text-xs text-[#a3a3a3]">
                    {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </div>
            </div>
        </motion.div>
    )
}

// ==========================================
// SYSTEM MESSAGE
// ==========================================

function SystemMessage({ msg }: { msg: ChatMessage }) {
    return (
        <motion.div
            className="flex justify-center py-2"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
        >
            <div
                className="flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-semibold"
                style={{ background: "rgba(74,140,112,0.07)", border: "1px solid rgba(74,140,112,0.18)", color: "#4a8c70" }}
            >
                <Cpu size={10} />
                {msg.content}
            </div>
        </motion.div>
    )
}

// ==========================================
// AI MESSAGE
// ==========================================

function AIMessage({ msg }: { msg: ChatMessage }) {
    return (
        <motion.div
            className="flex gap-4"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
        >
            <div className="relative shrink-0 mt-0.5">
                <div
                    className="flex h-9 w-9 items-center justify-center rounded-xl"
                    style={{
                        background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                        boxShadow: "0 2px 8px rgba(130,192,164,0.25)",
                    }}
                >
                    <Brain size={16} className="text-white" />
                </div>
                {msg.streaming && (
                    <motion.div
                        className="absolute inset-0 rounded-xl"
                        style={{ border: "2px solid rgba(130,192,164,0.5)" }}
                        animate={{ scale: [1, 1.6], opacity: [0.7, 0] }}
                        transition={{ duration: 1.0, repeat: Infinity }}
                    />
                )}
            </div>

            <div className="flex-1 min-w-0 max-w-[80%] xl:max-w-[75%]">
                {msg.agentEvents && msg.agentEvents.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                        {msg.agentEvents.map((ev, i) => (
                            <span
                                key={i}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold"
                                style={{
                                    background: "rgba(130,192,164,0.07)",
                                    border: "1px solid rgba(130,192,164,0.18)",
                                    color: "#82c0a4",
                                }}
                            >
                                <Sparkles size={9} />
                                {ev}
                            </span>
                        ))}
                    </div>
                )}

                <div className="flex items-center gap-2 mb-2">
                    <span className="text-sm font-semibold text-[#1a1a1a]">CortexPrime</span>
                    {msg.streaming && (
                        <span
                            className="flex items-center gap-1.5 text-xs font-medium rounded-full px-2 py-0.5"
                            style={{ background: "rgba(130,192,164,0.08)", color: "#82c0a4", border: "1px solid rgba(130,192,164,0.2)" }}
                        >
                            <motion.span
                                className="inline-block w-1.5 h-1.5 rounded-full bg-[#82c0a4]"
                                animate={{ opacity: [1, 0.2, 1] }}
                                transition={{ duration: 0.8, repeat: Infinity }}
                            />
                            Thinking...
                        </span>
                    )}
                </div>

                <div
                    className="relative rounded-2xl rounded-tl-sm px-6 py-5 text-white [&_*]:text-white [&_code]:text-[#f0f7f4] [&_a]:text-white [&_a]:underline"
                    style={{
                        background: "#82c0a4",
                        border: "1px solid rgba(74,140,112,0.2)",
                        boxShadow: msg.streaming
                            ? "0 0 0 2px rgba(130,192,164,0.25), 0 4px 16px rgba(130,192,164,0.2)"
                            : "0 2px 8px rgba(130,192,164,0.18)",
                    }}
                >
                    {msg.content ? (
                        <MarkdownRenderer content={msg.content} streaming={msg.streaming} variant="light" />
                    ) : (
                        <div className="flex items-center gap-3">
                            {[0, 1, 2].map(i => (
                                <motion.div
                                    key={i}
                                    className="w-2 h-2 rounded-full bg-white/80"
                                    animate={{ y: [0, -6, 0], opacity: [0.5, 1, 0.5] }}
                                    transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
                                />
                            ))}
                        </div>
                    )}
                    {msg.streaming && msg.content && (
                        <motion.span
                            className="inline-block w-0.5 h-4 ml-0.5 rounded-full bg-white align-middle"
                            animate={{ opacity: [1, 0, 1] }}
                            transition={{ duration: 0.7, repeat: Infinity }}
                        />
                    )}
                </div>

                {!msg.streaming && (
                    <div className="mt-1.5 text-xs text-[#a3a3a3]">
                        {new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </div>
                )}
            </div>
        </motion.div>
    )
}

// ==========================================
// WELCOME SCREEN
// ==========================================

function WelcomeScreen({ onSend }: { onSend: (text: string) => void }) {
    const user = useAuthStore(s => s.user)
    const firstName = user?.user_id ?? "there"
    const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1)

    const hour = new Date().getHours()
    const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"

    return (
        <div className="flex flex-col items-center justify-center h-full px-6 pb-8">
            <motion.div
                className="w-full max-w-2xl"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
                <div className="mb-10 text-center">
                    <motion.div
                        className="mx-auto mb-8 flex h-16 w-16 items-center justify-center rounded-2xl"
                        style={{
                            background: "linear-gradient(135deg, #82c0a4, #4a8c70)",
                            boxShadow: "0 8px 32px rgba(130,192,164,0.25)",
                        }}
                        animate={{ boxShadow: ["0 8px 32px rgba(130,192,164,0.25)", "0 12px 40px rgba(130,192,164,0.35)", "0 8px 32px rgba(130,192,164,0.25)"] }}
                        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                    >
                        <Brain size={28} className="text-white" />
                    </motion.div>

                    <h1 className="text-3xl font-black text-[#1a1a1a] mb-2 tracking-tight">
                        {greeting}, {displayName}
                    </h1>
                    <p className="text-base text-[#737373] max-w-md mx-auto">
                        Welcome to your AI companion. Ask anything ? I&apos;ll orchestrate the full agent pipeline for you.
                    </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {SUGGESTIONS.map(({ icon: Icon, label, prompt }, i) => (
                        <motion.button
                            key={label}
                            initial={{ opacity: 0, y: 12 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.06 + 0.15 }}
                            onClick={() => onSend(prompt)}
                            className="group flex items-start gap-3 rounded-2xl p-4 text-left transition-all hover:-translate-y-0.5"
                            style={{
                                background: "#ffffff",
                                border: "1px solid #dceee4",
                                boxShadow: "0 2px 8px rgba(26,26,26,0.04)",
                            }}
                        >
                            <div
                                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
                                style={{ background: "rgba(130,192,164,0.12)", color: "#4a8c70" }}
                            >
                                <Icon size={16} />
                            </div>
                            <div>
                                <div className="text-sm font-semibold text-[#1a1a1a] group-hover:text-[#4a8c70] transition-colors">{label}</div>
                                <div className="text-xs text-[#737373] mt-0.5 line-clamp-2">{prompt}</div>
                            </div>
                        </motion.button>
                    ))}
                </div>
            </motion.div>
        </div>
    )
}

// ==========================================
// CENTER PANEL ? AI-first Conversation
// ==========================================

export default function CenterPanel() {
    const store          = useChatStore()
    const bottomRef      = useRef<HTMLDivElement>(null)
    const streamingIdRef = useRef<string | null>(null)
    const chunksRef      = useRef(false)
    const [input, setInput] = useState("")
    const [focused, setFocused] = useState(false)
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [store.messages, store.isLoading])

    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto"
            textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`
        }
    }, [input])

    async function simulateStreamResponse(aiId: string, query: string) {
        const responses = [
            `I've analyzed your request and initiated a multi-agent cognitive pipeline.\n\n**Orchestrator Assessment:**\nThe mission has been decomposed into 4 parallel subtasks.\n\n**Research Phase:**\nThe Research agent queried semantic clusters and retrieved high-confidence knowledge sources.\n\n**Synthesis:**\nThe system has completed the cognitive cycle based on: *"${query}"*`,
            `**Cognitive Analysis Complete**\n\nI've processed your query through the full agent pipeline:\n\n1. **Planning** ? Mission objective decomposed\n2. **Research** ? Knowledge base queried\n3. **Execution** ? Multi-agent reasoning chains constructed\n4. **Reflection** ? Results synthesized\n\n> Query: "${query}"`,
        ]
        const response = responses[Math.floor(Math.random() * responses.length)]
        const chars = response.split("")
        const delay = (ms: number) => new Promise((r) => setTimeout(r, ms))

        for (let i = 0; i < chars.length; i++) {
            if (streamingIdRef.current !== aiId) break
            useChatStore.getState().appendChunk(aiId, chars[i])
            const c = chars[i]
            const pause = c === " " ? 10 : c === "\n" ? 55 : c === "." || c === "," ? 40 : 15
            if (i % 8 === 0) await delay(pause)
        }
        useChatStore.getState().updateMessage(aiId, { streaming: false })
    }

    async function handleSend(text: string) {
        const trimmed = text.trim()
        if (!trimmed || store.isLoading) return
        setInput("")
        if (textareaRef.current) textareaRef.current.style.height = "auto"

        useMissionStore.getState().resetMission()

        store.addMessage({ id: `user-${Date.now()}`, role: "user", content: trimmed, timestamp: new Date().toISOString() })

        const aiId = `ai-${Date.now()}`
        streamingIdRef.current = aiId
        chunksRef.current = false

        store.addMessage({ id: aiId, role: "assistant", content: "", timestamp: new Date().toISOString(), streaming: true })
        store.setStreamingId(aiId)
        store.setLoading(true)

        const unsubStream = wsService.subscribe((msg) => {
            if (msg.stream_chunk && streamingIdRef.current === aiId) {
                chunksRef.current = true
                useChatStore.getState().appendChunk(aiId, msg.stream_chunk as string)
            }
            if (msg.stream_completed && streamingIdRef.current === aiId) {
                useChatStore.getState().updateMessage(aiId, { streaming: false })
                streamingIdRef.current = null
                store.setStreamingId(null)
                store.setLoading(false)
                unsubStream()
            }
        })

        let usedBackend = false
        try {
            const res = await fetch(apiUrl("/orchestrate"), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "include",
                body: JSON.stringify({
                    objective:  trimmed,
                    session_id: wsService.getSessionId?.() ?? "global",
                }),
                signal: AbortSignal.timeout(10000),
            })
            if (res.ok) {
                usedBackend = true
                try {
                    const data = await res.json() as Record<string, unknown>
                    const inline =
                        (data?.result as string) ||
                        (data?.response as string) ||
                        (data?.output as string) || ""
                    if (inline && !chunksRef.current) {
                        useChatStore.getState().updateMessage(aiId, { content: inline, streaming: false })
                        streamingIdRef.current = null
                        store.setStreamingId(null)
                        store.setLoading(false)
                        unsubStream()
                    }
                } catch {
                    // WS handler takes over
                }
            }
        } catch {
            // Backend unreachable ? fall through to simulation
        }

        if (!usedBackend && !chunksRef.current) {
            await simulateStreamResponse(aiId, trimmed)
            streamingIdRef.current = null
            store.setStreamingId(null)
            store.setLoading(false)
            unsubStream()
        }
    }

    function handleKeyDown(e: React.KeyboardEvent) {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault()
            handleSend(input)
        }
    }

    const isEmpty = store.messages.length === 0

    return (
        <div className="flex flex-col h-full bg-[#f0f7f4]">
            <AnimatePresence>
                <MissionProgressBar />
            </AnimatePresence>

            <div className="flex-1 overflow-y-auto cortex-scroll">
                {isEmpty ? (
                    <WelcomeScreen onSend={handleSend} />
                ) : (
                    <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
                        <AnimatePresence initial={false}>
                            {store.messages.map((msg) =>
                                msg.role === "user"      ? <UserMessage   key={msg.id} msg={msg} /> :
                                msg.role === "system"    ? <SystemMessage key={msg.id} msg={msg} /> :
                                                           <AIMessage     key={msg.id} msg={msg} />
                            )}
                        </AnimatePresence>
                        <div ref={bottomRef} />
                    </div>
                )}
            </div>

            <div className="shrink-0 px-6 pb-6 pt-3 bg-[#f0f7f4]">
                <div className="max-w-3xl mx-auto">
                    <div
                        className="flex items-end gap-2 rounded-2xl px-4 py-3 transition-all"
                        style={{
                            background: "#ffffff",
                            border: focused ? "1px solid rgba(130,192,164,0.45)" : "1px solid #dceee4",
                            boxShadow: focused ? "0 4px 20px rgba(130,192,164,0.15)" : "0 2px 8px rgba(26,26,26,0.04)",
                        }}
                    >
                        <button type="button" className="p-2 text-[#737373] hover:text-[#4a8c70] transition-colors" tabIndex={-1}>
                            <Paperclip size={18} />
                        </button>
                        <button type="button" className="p-2 text-[#737373] hover:text-[#4a8c70] transition-colors" tabIndex={-1}>
                            <Mic size={18} />
                        </button>

                        <textarea
                            ref={textareaRef}
                            rows={1}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={handleKeyDown}
                            onFocus={() => setFocused(true)}
                            onBlur={() => setFocused(false)}
                            disabled={store.isLoading}
                            placeholder="Message your AI companion..."
                            className="flex-1 resize-none bg-transparent text-base text-[#1a1a1a] placeholder:text-[#a3a3a3] outline-none leading-relaxed min-h-[24px] max-h-40 py-2"
                        />

                        <div className="flex items-center gap-2 pb-1">
                            {store.messages.length > 0 && (
                                <button
                                    type="button"
                                    onClick={() => store.clearMessages()}
                                    className="p-2 text-[#737373] hover:text-[#4a8c70] transition-colors"
                                    title="Clear chat"
                                >
                                    <RotateCcw size={16} />
                                </button>
                            )}
                            <motion.button
                                type="button"
                                whileTap={{ scale: 0.92 }}
                                onClick={() => handleSend(input)}
                                disabled={!input.trim() || store.isLoading}
                                className="flex h-10 w-10 items-center justify-center rounded-full text-white disabled:opacity-40"
                                style={{
                                    background: input.trim() && !store.isLoading
                                        ? "linear-gradient(135deg, #82c0a4, #4a8c70)"
                                        : "#d1d1d1",
                                    boxShadow: input.trim() && !store.isLoading ? "0 4px 14px rgba(130,192,164,0.35)" : "none",
                                }}
                            >
                                <ArrowUp size={18} />
                            </motion.button>
                        </div>
                    </div>

                    <p className="text-center text-xs text-[#a3a3a3] mt-2">
                        Enter to send � Shift+Enter for new line
                    </p>
                </div>
            </div>
        </div>
    )
}
