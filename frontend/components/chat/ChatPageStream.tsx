"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Send, Bot, User, Loader2, Plus, Target, Sparkles,
  ChevronDown, MessageSquare, Trash2, Play, Pause,
} from "lucide-react"
import CortexShell from "@/components/layout/CortexShell"
import { cn } from "@/utils/cn"
import { stagger, variants } from "@/lib/motion-tokens"

interface ChatMessage {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  timestamp: Date
  streaming?: boolean
}

interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: Date
}

const welcomeMessage: ChatMessage = {
  id: "welcome",
  role: "assistant",
  content: "Hello! I'm CortexPrime AI. I can help you create and manage missions, answer questions, and orchestrate agents. What would you like to do?",
  timestamp: new Date(),
}

const suggestionPrompts = [
  "Create a market intelligence mission",
  "Analyze competitor landscape",
  "What are my active missions?",
  "Generate a customer sentiment report",
]

export default function ChatPageStream() {
  const [conversations, setConversations] = useState<Conversation[]>([
    { id: "c1", title: "New Chat", messages: [welcomeMessage], createdAt: new Date() },
  ])
  const [activeConv, setActiveConv] = useState("c1")
  const [input, setInput] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const currentConv = conversations.find((c) => c.id === activeConv) ?? conversations[0]

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [])

  useEffect(() => { scrollToBottom() }, [currentConv?.messages, scrollToBottom])

  function addMessage(convId: string, message: ChatMessage) {
    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, messages: [...c.messages, message] } : c))
    )
  }

  function updateLastMessage(convId: string, content: string) {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? { ...c, messages: c.messages.map((m, i) => (i === c.messages.length - 1 ? { ...m, content, streaming: false } : m)) }
          : c
      )
    )
  }

  function appendToLastMessage(convId: string, chunk: string) {
    setConversations((prev) =>
      prev.map((c) =>
        c.id === convId
          ? { ...c, messages: c.messages.map((m, i) => (i === c.messages.length - 1 ? { ...m, content: m.content + chunk, streaming: true } : m)) }
          : c
      )
    )
  }

  async function handleSend() {
    if (!input.trim() || isStreaming) return
    const convId = activeConv
    const userMsg: ChatMessage = { id: `u-${Date.now()}`, role: "user", content: input.trim(), timestamp: new Date() }
    addMessage(convId, userMsg)
    setInput("")

    const assistantMsg: ChatMessage = { id: `a-${Date.now()}`, role: "assistant", content: "", timestamp: new Date(), streaming: true }
    addMessage(convId, assistantMsg)
    setIsStreaming(true)

    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, title: c.messages.length <= 2 ? input.trim().slice(0, 40) + "..." : c.title } : c))
    )

    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: input.trim(),
          conversation_id: convId,
          messages: currentConv.messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      })

      if (!res.ok) {
        updateLastMessage(convId, "Sorry, I encountered an error processing your request. Please try again.")
        setIsStreaming(false)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        updateLastMessage(convId, "No response stream available.")
        setIsStreaming(false)
        return
      }

      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text = decoder.decode(value, { stream: true })
        appendToLastMessage(convId, text)
      }

      updateLastMessage(convId, currentConv.messages[currentConv.messages.length - 1]?.content ?? "")
    } catch {
      updateLastMessage(convId, "Connection error. Please check your connection and try again.")
    }
    setIsStreaming(false)
  }

  function newConversation() {
    const id = `c${Date.now()}`
    setConversations((prev) => [
      ...prev,
      { id, title: "New Chat", messages: [welcomeMessage], createdAt: new Date() },
    ])
    setActiveConv(id)
  }

  function clearConversation(id: string) {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, messages: [welcomeMessage], title: "New Chat" } : c))
    )
  }

  return (
    <CortexShell title="AI Chat" subtitle="Conversational interface with streaming responses">
      <div className="mx-auto flex h-[calc(100vh-120px)] max-w-[1600px] gap-0 p-0">
        <div
          className="flex w-64 shrink-0 flex-col border-r p-4"
          style={{ borderRight: "1px solid var(--border)", background: "var(--surface)" }}
        >
          <button
            onClick={newConversation}
            aria-label="New Chat"
            className="flex items-center gap-2 rounded-[12px] px-4 py-2.5 text-[0.8rem] font-semibold text-white shadow-sm transition-colors mb-4"
            style={{ background: "var(--accent)" }}
          >
            <Plus className="h-4 w-4" /> New Chat
          </button>
          <div className="flex-1 overflow-y-auto space-y-1">
            {conversations.map((conv) => (
              <button
                key={conv.id}
                onClick={() => setActiveConv(conv.id)}
                className="w-full flex items-center gap-2 rounded-[10px] px-3 py-2 text-left text-[0.75rem] font-medium transition-all"
                style={{
                  background: activeConv === conv.id ? "var(--accent-muted)" : "transparent",
                  color: activeConv === conv.id ? "var(--accent)" : "var(--text-secondary)",
                }}
              >
                <MessageSquare className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{conv.title}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-1 flex-col">
          <div
            className="flex-1 overflow-y-auto px-6 py-6 space-y-4"
            role="log"
            aria-live="polite"
            aria-label="Chat messages"
          >
            <AnimatePresence>
              {currentConv?.messages.map((msg) => (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={cn("flex gap-3", msg.role === "user" ? "justify-end" : "justify-start")}
                >
                  {msg.role !== "user" && (
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                      style={{ background: "var(--accent-muted)" }}
                    >
                      <Bot className="h-4 w-4" style={{ color: "var(--accent)" }} />
                    </div>
                  )}
                  <div
                    className={cn("max-w-[70%] rounded-[16px] px-4 py-3")}
                    style={
                      msg.role === "user"
                        ? { background: "var(--accent)", color: "white" }
                        : { background: "var(--surface)", color: "var(--text-primary)", border: "1px solid var(--border)" }
                    }
                  >
                    <p className="text-[0.82rem] leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                      {msg.streaming && (
                        <span
                          className="inline-block w-2 h-4 ml-0.5 animate-blink"
                          style={{ background: "var(--accent)" }}
                        />
                      )}
                    </p>
                    <p
                      className="text-[0.6rem] mt-1"
                      style={{ color: msg.role === "user" ? "rgba(255,255,255,0.6)" : "var(--text-muted)" }}
                    >
                      {msg.timestamp.toLocaleTimeString()}
                    </p>
                  </div>
                  {msg.role === "user" && (
                    <div
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px]"
                      style={{ background: "var(--accent)" }}
                    >
                      <User className="h-4 w-4 text-white" />
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {currentConv?.messages.length === 1 && (
              <div className="flex flex-wrap gap-2 mt-4">
                {suggestionPrompts.map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => { setInput(prompt); setTimeout(() => handleSend(), 100) }}
                    className="rounded-[10px] px-3.5 py-2 text-[0.72rem] font-medium transition-all"
                    style={{
                      border: "1px solid var(--border)",
                      background: "var(--surface)",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Sparkles className="h-3 w-3 inline mr-1.5" style={{ color: "var(--accent)" }} />
                    {prompt}
                  </button>
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div
            className="border-t px-6 py-4"
            style={{ borderTop: "1px solid var(--border)", background: "var(--surface)" }}
          >
            <div className="flex items-center gap-3">
              <div className="flex-1 relative">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend() } }}
                  placeholder="Type a message or create a mission..."
                  disabled={isStreaming}
                  aria-label="Chat message"
                  className="w-full rounded-[14px] px-4 py-3 pr-12 text-[0.82rem] outline-none disabled:opacity-50"
                  style={{
                    border: "1px solid var(--border)",
                    background: "var(--surface-raised)",
                    color: "var(--text-primary)",
                  }}
                />
              </div>
              <button
                onClick={handleSend}
                disabled={!input.trim() || isStreaming}
                aria-label="Send message"
                className="flex h-11 w-11 items-center justify-center rounded-[12px] text-white shadow-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ background: "var(--accent)" }}
              >
                {isStreaming ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
            <p className="mt-2 text-[0.6rem] text-center" style={{ color: "var(--text-muted)" }}>
              CortexPrime AI may produce inaccurate information. Verify important facts.
            </p>
          </div>
        </div>
      </div>
    </CortexShell>
  )
}
