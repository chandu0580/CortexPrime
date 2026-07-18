"use client"

import { useRef, useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { ExecPanel, PulseDot } from "./ExecPanel"
import { Send, Brain, Loader2, Maximize2, MessageSquare } from "lucide-react"
import { wsService } from "@/services/websocket"
import { apiUrl } from "@/lib/constants"
import { useChatStore } from "@/store/chatStore"
import Link from "next/link"

export function ExecutiveChatPanel() {
  const [input, setInput] = useState("")
  const [messages, setMessages] = useState<Array<{ id: string; role: string; content: string }>>([])
  const [isLoading, setIsLoading] = useState(false)
  const [streamingContent, setStreamingContent] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streamingContent])

  async function handleSend(text: string) {
    if (!text.trim() || isLoading) return
    setInput("")

    const userMsg = { id: `user-${Date.now()}`, role: "user", content: text }
    setMessages((prev) => [...prev, userMsg])
    setIsLoading(true)
    setStreamingContent("")

    const unsub = wsService.subscribe((msg) => {
      if (msg.stream_chunk) {
        setStreamingContent((prev) => prev + (msg.stream_chunk as string))
      }
    })

    try {
      const res = await fetch(apiUrl("/orchestrate"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ objective: text }),
      })

      if (res.ok) {
        const data = (await res.json()) as Record<string, unknown>
        const content =
          (data.result as string) ||
          (data.response as string) ||
          (data.output as string) ||
          JSON.stringify(data, null, 2)

        setMessages((prev) => [
          ...prev,
          { id: `ai-${Date.now()}`, role: "assistant", content },
        ])
        setStreamingContent("")
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: `ai-${Date.now()}`,
            role: "assistant",
            content: `Error: Backend returned ${res.status}`,
          },
        ])
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `ai-${Date.now()}`,
          role: "assistant",
          content: `Connection error: ${(err as Error).message}`,
        },
      ])
    } finally {
      unsub()
      setIsLoading(false)
      setStreamingContent("")
    }
  }

  return (
    <ExecPanel
      title="Executive AI Chat"
      subtitle="Ask anything"
      accent="emerald"
      className="flex flex-col"
      headerRight={
        <Link href="/executive-platform/chat" className="text-[10px] text-white/30 hover:text-white/60 transition-colors flex items-center gap-1">
          <Maximize2 className="w-3 h-3" />
        </Link>
      }
    >
      <div className="flex flex-col h-full min-h-0">
        <div className="flex-1 overflow-y-auto space-y-2 mb-2 min-h-0 cortex-scroll">
          {messages.length === 0 && !streamingContent && (
            <div className="flex flex-col items-center justify-center py-6 text-center">
              <div className="w-8 h-8 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-2">
                <Brain className="w-4 h-4 text-emerald-400" />
              </div>
              <p className="text-xs text-white/40">Ask a question or give a command</p>
              <p className="text-[9px] text-white/20 mt-1">e.g. "Show me running missions"</p>
            </div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <motion.div
                key={msg.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-2 rounded-lg text-xs leading-relaxed ${
                  msg.role === "user"
                    ? "bg-emerald-500/10 text-white/80 ml-6"
                    : "bg-white/5 text-white/60 mr-6"
                }`}
              >
                {msg.content}
              </motion.div>
            ))}
          </AnimatePresence>
          {streamingContent && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="p-2 rounded-lg bg-white/5 text-white/60 text-xs leading-relaxed mr-6"
            >
              {streamingContent}
              <span className="inline-block w-1.5 h-3.5 bg-emerald-400/50 ml-0.5 animate-pulse" />
            </motion.div>
          )}
          {isLoading && !streamingContent && (
            <div className="flex items-center gap-2 p-2 text-white/30 text-xs">
              <Loader2 className="w-3 h-3 animate-spin" />
              Processing...
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <form
          onSubmit={(e) => { e.preventDefault(); handleSend(input) }}
          className="flex items-center gap-2 shrink-0"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a command..."
            disabled={isLoading}
            className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white/70 placeholder:text-white/20 outline-none focus:border-emerald-500/30 transition-colors disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="w-7 h-7 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 flex items-center justify-center transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          >
            <Send className="w-3 h-3 text-emerald-400" />
          </button>
        </form>
      </div>
    </ExecPanel>
  )
}