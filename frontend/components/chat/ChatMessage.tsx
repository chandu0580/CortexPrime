"use client"
import { motion } from "framer-motion"
import { Brain } from "lucide-react"
import { cn } from "@/utils/cn"
import { formatTimestamp } from "@/lib/formatting"
import MarkdownRenderer from "./MarkdownRenderer"
import { fadeInUp } from "@/lib/animations"
import type { ChatMessage } from "@/store/chatStore"

function AIAvatar({ streaming }: { streaming?: boolean }) {
    return (
        <div className="relative mt-0.5 shrink-0">
            <div
                className={cn(
                    "flex h-8 w-8 items-center justify-center rounded-xl",
                    "text-white shadow-md",
                    streaming && "shadow-[#82c0a4]/40"
                )}
                style={{ background: "linear-gradient(135deg, #82c0a4, #4a8c70)" }}
            >
                <Brain size={14} />
            </div>
            {streaming && (
                <motion.div
                    className="absolute inset-0 rounded-xl"
                    style={{ border: "2px solid rgba(130,192,164,0.5)" }}
                    animate={{ scale: [1, 1.6], opacity: [0.7, 0] }}
                    transition={{ duration: 1.0, repeat: Infinity }}
                />
            )}
        </div>
    )
}

interface ChatMessageProps {
    message: ChatMessage
}

export default function ChatMessageItem({ message }: ChatMessageProps) {
    const isUser = message.role === "user"

    return (
        <motion.div
            variants={fadeInUp}
            initial="hidden"
            animate="visible"
            className={cn("flex gap-3", isUser ? "justify-end" : "justify-start")}
        >
            {!isUser && <AIAvatar streaming={message.streaming} />}

            <div className={cn("max-w-[82%]", isUser && "flex flex-col items-end")}>
                {!isUser && (
                    <div className="mb-1 ml-1 flex items-center gap-2">
                        <span className="text-xs font-bold tracking-tight text-[#4a8c70]">
                            CortexPrime
                        </span>
                        {message.streaming && (
                            <span className="flex items-center gap-1 text-[10px] text-[#82c0a4]">
                                <motion.span
                                    className="inline-block h-1.5 w-1.5 rounded-full bg-[#82c0a4]"
                                    animate={{ opacity: [1, 0.2, 1] }}
                                    transition={{ duration: 0.8, repeat: Infinity }}
                                />
                                streaming
                            </span>
                        )}
                    </div>
                )}

                <div
                    className={cn(
                        "relative overflow-hidden rounded-2xl px-4 py-3 text-sm leading-relaxed",
                        isUser
                            ? "rounded-br-sm text-[#1a1a1a]"
                            : "rounded-bl-sm text-white"
                    )}
                    style={isUser ? {
                        background: "#ffffff",
                        border: "1px solid #dceee4",
                        boxShadow: "0 2px 8px rgba(26,26,26,0.04)",
                    } : {
                        background: "#82c0a4",
                        border: "1px solid rgba(74,140,112,0.2)",
                        boxShadow: message.streaming
                            ? "0 0 0 2px rgba(130,192,164,0.25), 0 4px 16px rgba(130,192,164,0.2)"
                            : "0 2px 8px rgba(130,192,164,0.18)",
                    }}
                >
                    {message.streaming && !isUser && (
                        <div className="message-streaming-overlay" aria-hidden />
                    )}

                    {isUser ? (
                        <p className="whitespace-pre-wrap">{message.content}</p>
                    ) : (
                        <MarkdownRenderer content={message.content} streaming={message.streaming} variant="light" />
                    )}
                </div>

                {!isUser && message.agentEvents && message.agentEvents.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                        {message.agentEvents.map((evt, i) => (
                            <span
                                key={i}
                                className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                                style={{
                                    background: "rgba(130,192,164,0.1)",
                                    border: "1px solid rgba(130,192,164,0.22)",
                                    color: "#4a8c70",
                                }}
                            >
                                {evt}
                            </span>
                        ))}
                    </div>
                )}

                <span className="ml-1 mt-1 block text-xs text-[#a3a3a3]">
                    {formatTimestamp(message.timestamp)}
                </span>
            </div>

            {isUser && (
                <div
                    className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-[10px] font-bold text-white"
                    style={{ background: "linear-gradient(135deg, #737373, #4a4a4a)" }}
                >
                    U
                </div>
            )}
        </motion.div>
    )
}
