"use client"

import { useCallback, useRef, useState } from "react"
import type { Citation, WorkspaceChatResponse } from "@/types/workspace"
import { CitationViewer } from "./CitationViewer"

interface Message {
  id: string
  role: "user" | "assistant"
  content: string
  citations?: Citation[]
  chunks_used?: number
  model_used?: string
  timestamp: Date
}

interface Props {
  wsId: string
  token?: string | null
  disabled?: boolean
}

export function WorkspaceChat({ wsId, token, disabled }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [query, setQuery]       = useState("")
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () =>
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50)

  const send = useCallback(async () => {
    const q = query.trim()
    if (!q || loading || disabled) return

    setError(null)
    setQuery("")

    const userMsg: Message = {
      id:        crypto.randomUUID(),
      role:      "user",
      content:   q,
      timestamp: new Date(),
    }
    setMessages((prev) => [...prev, userMsg])
    scrollToBottom()

    setLoading(true)
    try {
      const { workspaceChat } = await import("@/services/workspaceApi")
      const res: WorkspaceChatResponse = await workspaceChat(wsId, q, 6, token)

      const assistantMsg: Message = {
        id:          crypto.randomUUID(),
        role:        "assistant",
        content:     res.answer,
        citations:   res.citations,
        chunks_used: res.chunks_used,
        model_used:  res.model_used,
        timestamp:   new Date(),
      }
      setMessages((prev) => [...prev, assistantMsg])
      scrollToBottom()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Chat failed")
    } finally {
      setLoading(false)
    }
  }, [query, loading, disabled, wsId, token])

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-4 px-1 pb-4 min-h-0">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
            <span className="text-4xl">💬</span>
            <p className="text-sm">Ask anything about your documents</p>
            <div className="flex flex-col gap-1 text-center text-xs text-slate-600">
              <p>"Summarize the main findings"</p>
              <p>"What risks are mentioned?"</p>
              <p>"Create a roadmap from this document"</p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-7 h-7 rounded-full bg-teal-900/60 border border-teal-700 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                🧠
              </div>
            )}
            <div className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-teal-900/40 border border-teal-800 text-slate-100 ml-auto"
                : "bg-slate-800/60 border border-slate-700 text-slate-200"
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.role === "assistant" && msg.citations && msg.citations.length > 0 && (
                <CitationViewer citations={msg.citations} />
              )}
              {msg.role === "assistant" && (
                <div className="flex items-center gap-3 mt-2 pt-2 border-t border-slate-700/50">
                  <span className="text-xs text-slate-600">
                    {msg.chunks_used} chunks · {msg.model_used}
                  </span>
                  <span className="text-xs text-slate-700 ml-auto">
                    {msg.timestamp.toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-7 h-7 rounded-full bg-slate-700 border border-slate-600 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                👤
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex gap-3 justify-start">
            <div className="w-7 h-7 rounded-full bg-teal-900/60 border border-teal-700 flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
              🧠
            </div>
            <div className="bg-slate-800/60 border border-slate-700 rounded-xl px-4 py-3">
              <div className="flex gap-1 items-center">
                <div className="w-1.5 h-1.5 rounded-full bg-[#82c0a4] animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-1.5 h-1.5 rounded-full bg-[#82c0a4] animate-bounce" style={{ animationDelay: "120ms" }} />
                <div className="w-1.5 h-1.5 rounded-full bg-[#82c0a4] animate-bounce" style={{ animationDelay: "240ms" }} />
                <span className="text-xs text-slate-500 ml-2">Retrieving & reasoning…</span>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400 bg-red-950/30 border border-red-800 rounded-lg px-3 py-2 text-center">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="pt-3 border-t border-slate-700/60">
        <div className="flex gap-2">
          <textarea
            className={`flex-1 resize-none bg-slate-800/60 border border-slate-600 rounded-xl px-4 py-3
              text-sm text-slate-200 placeholder-slate-500 outline-none focus:border-teal-500
              transition-colors min-h-[48px] max-h-[120px]
              ${disabled ? "opacity-50 cursor-not-allowed" : ""}
            `}
            rows={1}
            placeholder={disabled ? "Upload documents first…" : "Ask about your documents…"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            disabled={disabled || loading}
          />
          <button
            onClick={send}
            disabled={!query.trim() || loading || disabled}
            className="px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-40
              disabled:cursor-not-allowed rounded-xl text-white text-sm font-medium
              transition-colors flex-shrink-0 self-end"
          >
            Send
          </button>
        </div>
        <p className="text-xs text-slate-600 mt-1 ml-1">Enter to send · Shift+Enter for new line</p>
      </div>
    </div>
  )
}
