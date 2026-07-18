"use client"

import { useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Bot, User, Sparkles } from "lucide-react"
import type { ChatMessage } from "@/types/enterprise"

export function ChatMessageBubble({ msg }: { msg: ChatMessage }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}
    >
      {msg.role !== "user" && (
        <div className="w-8 h-8 rounded-lg bg-[var(--accent-muted)] flex items-center justify-center shrink-0">
          {msg.role === "assistant" ? (
            <Sparkles className="w-4 h-4 text-[var(--accent)]" />
          ) : (
            <Bot className="w-4 h-4 text-[var(--info)]" />
          )}
        </div>
      )}
      <div
        className={`max-w-[80%] p-3 rounded-xl ${
          msg.role === "user"
            ? "bg-[var(--accent)] text-[var(--text-inverse)]"
            : "bg-[var(--surface-raised)] text-[var(--text-primary)]"
        }`}
      >
        <p className="type-body-sm whitespace-pre-wrap">{msg.content}</p>
        {msg.metadata && (msg.metadata.mission_id as string) ? (
          <p className="type-caption text-[var(--text-muted)] mt-1">
            Mission: {msg.metadata.mission_id as string}
          </p>
        ) : null}
      </div>
      {msg.role === "user" && (
        <div className="w-8 h-8 rounded-lg bg-[var(--surface-raised)] flex items-center justify-center shrink-0">
          <User className="w-4 h-4 text-[var(--text-muted)]" />
        </div>
      )}
    </motion.div>
  )
}

export function ChatMessageList({ messages }: { messages: ChatMessage[] }) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  return (
    <div className="flex-1 overflow-y-auto space-y-4 cortex-scroll pr-2">
      <AnimatePresence>
        {messages.map((msg) => (
          <ChatMessageBubble key={msg.id} msg={msg} />
        ))}
      </AnimatePresence>
      <div ref={endRef} />
    </div>
  )
}
