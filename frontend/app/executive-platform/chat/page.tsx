"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Sparkles, Mic, Square } from "lucide-react"

interface Message {
  role: "user" | "assistant"
  content: string
  timestamp: Date
}

export default function ExecutiveChat() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: "Good afternoon, Executive. CortexPrime is online. All subsystems nominal. How can I assist you today?", timestamp: new Date() },
  ])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [streamingText, setStreamingText] = useState("")
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages, streamingText])

  const send = async () => {
    if (!input.trim() || loading) return
    const userMsg: Message = { role: "user", content: input, timestamp: new Date() }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setLoading(true)
    setStreamingText("")

    try {
      const res = await fetch("/api/mission-library/missions/executive_research/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          params: { topic: input, context: "Executive chat inquiry", focus_areas: "analysis,recommendations", questions: input },
        }),
      })
      const data = await res.json()
      const response = data?.result?.response || data?.result?.error || "I apologize, but I was unable to process that request. Please try rephrasing."
      setMessages((prev) => [...prev, { role: "assistant", content: response, timestamp: new Date() }])
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Connection issue. Please check that the backend is running.", timestamp: new Date() }])
    }
    setLoading(false)
    setStreamingText("")
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col h-[calc(100vh-4rem)]">
      <h1 className="text-2xl font-semibold tracking-tight shrink-0 mb-4">Executive Chat</h1>
      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[75%] rounded-2xl px-4 py-3 ${
              msg.role === "user"
                ? "bg-emerald-500/10 border border-emerald-500/20 text-white/90"
                : "bg-white/5 border border-white/10 text-white/70"
            }`}>
              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              <p className="text-[10px] text-white/20 mt-1">{msg.timestamp.toLocaleTimeString()}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="max-w-[75%] rounded-2xl px-4 py-3 bg-white/5 border border-white/10">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="shrink-0 mt-4 flex items-center gap-2 p-2 rounded-xl border border-white/10 bg-white/[0.02]">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask CortexPrime anything..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder:text-white/20 px-2"
        />
        <button className="p-2 rounded-lg hover:bg-white/5 text-white/40 hover:text-emerald-400 transition-colors">
          <Mic className="w-4 h-4" />
        </button>
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="p-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-colors disabled:opacity-30"
        >
          {loading ? <Square className="w-4 h-4" /> : <Send className="w-4 h-4" />}
        </button>
      </div>
    </div>
  )
}