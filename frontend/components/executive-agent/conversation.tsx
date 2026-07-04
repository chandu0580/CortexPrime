"use client"

import { useState, useRef, useEffect } from "react"
import { useExecutiveAgentStore } from "@/store/executiveAgentStore"
import { GlassCard } from "@/components/executive-platform/shared"
import { Bot, Send, User, Brain, Crosshair, Shield, History } from "lucide-react"

interface Message {
  role: "agent" | "user"
  content: string
  timestamp: Date
  contextUsed?: string[]
}

export function ExecutiveConversation() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "agent",
      content: "I'm your Executive Agent. I'm continuously monitoring platform health, mission execution, and security. I can help you with recommendations, mission preparation, approvals, and anything related to CortexPrime operations. What would you like to do?",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState("")
  const { conversationContext, suggestions, notifications } = useExecutiveAgentStore()
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }) }, [messages])

  const send = async () => {
    if (!input.trim()) return
    const userMsg: Message = { role: "user", content: input, timestamp: new Date() }
    setMessages((prev) => [...prev, userMsg])
    setInput("")

    const ctx = conversationContext
    const pendingNotifications = notifications.filter((n) => !n.read).length
    const topSuggestions = suggestions.slice(0, 3)
    const healthSummary = ctx?.health ? Object.entries(ctx.health).map(([k, v]) => `${k}:${v}`).join(", ") : "unknown"

    const agentResponse = generateResponse(input, {
      pendingApprovals: ctx?.approvals.find((a) => a.status === "pending") ? ctx.approvals.find((a) => a.status === "pending")!.mission : "none",
      healthSummary,
      pendingNotifications,
      topSuggestions,
      missionCount: ctx?.missions.length || 0,
    })

    setMessages((prev) => [...prev, { role: "agent", content: agentResponse, timestamp: new Date(), contextUsed: ["platform health", "notifications", "suggestions"] }])
  }

  return (
    <GlassCard className="flex flex-col h-[500px]">
      <div className="flex items-center gap-2 mb-3 shrink-0">
        <Bot className="w-4 h-4 text-emerald-400" />
        <h2 className="text-sm font-medium text-white/60">Executive Conversation</h2>
        <div className="flex items-center gap-1 ml-auto text-[10px] text-white/20">
          <Brain className="w-3 h-3 text-emerald-400" />
          Context-aware
        </div>
      </div>
      <div className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[85%] rounded-xl px-3 py-2 ${
              msg.role === "user"
                ? "bg-emerald-500/10 border border-emerald-500/20"
                : "bg-white/5 border border-white/10"
            }`}>
              <div className="flex items-center gap-1.5 mb-1">
                {msg.role === "agent" ? <Bot className="w-3 h-3 text-emerald-400" /> : <User className="w-3 h-3 text-white/40" />}
                <span className="text-[10px] text-white/30">{msg.role === "agent" ? "Executive Agent" : "You"}</span>
                {msg.contextUsed && (
                  <span className="text-[9px] text-white/20 ml-auto">context: {msg.contextUsed.join(", ")}</span>
                )}
              </div>
              <p className="text-sm text-white/70 whitespace-pre-wrap leading-relaxed">{msg.content}</p>
              <p className="text-[10px] text-white/20 mt-1">{msg.timestamp.toLocaleTimeString()}</p>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-white/5 shrink-0">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about missions, approvals, recommendations..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-white/80 placeholder:text-white/20"
        />
        <button onClick={send} disabled={!input.trim()} className="p-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 disabled:opacity-30 transition-colors">
          <Send className="w-4 h-4" />
        </button>
      </div>
    </GlassCard>
  )
}

function generateResponse(input: string, ctx: {
  pendingApprovals: string
  healthSummary: string
  pendingNotifications: number
  topSuggestions: { title: string; action: string }[]
  missionCount: number
}): string {
  const lower = input.toLowerCase()

  if (lower.includes("health") || lower.includes("status")) {
    return `Platform health snapshot:\n• Infrastructure: ${ctx.healthSummary}\n• ${ctx.pendingNotifications} pending notification(s)\n• ${ctx.missionCount} mission(s) tracked\n• Pending approvals: ${ctx.pendingApprovals}`
  }

  if (lower.includes("approv") || lower.includes("pending")) {
    if (ctx.pendingApprovals !== "none" && ctx.pendingApprovals !== "Approvals (0)") {
      return `You have pending approvals requiring attention. I recommend reviewing the approval queue at your earliest convenience. Would you like me to navigate to the Approvals page?`
    }
    return "No pending approvals at this time. All governance workflows are current."
  }

  if (lower.includes("suggest") || lower.includes("recommend") || lower.includes("next")) {
    if (ctx.topSuggestions.length > 0) {
      return `Based on my continuous monitoring, here are my top suggestions:\n${ctx.topSuggestions.map((s, i) => `${i + 1}. ${s.action}`).join("\n")}\n\nWould you like me to elaborate on any of these?`
    }
    return "I don't have any active suggestions at this moment. Everything appears to be running smoothly."
  }

  if (lower.includes("mission") || lower.includes("task") || lower.includes("run")) {
    return "I have several mission templates prepared:\n• Software Release (HIGH risk, requires approval)\n• Incident Response (HIGH risk, requires approval)\n• Executive Research (LOW risk, no approval needed)\n• Security Investigation (CRITICAL risk, requires break-glass authority)\n\nWhich one would you like to launch? I'll prepare the full plan."
  }

  return `I'm monitoring the platform continuously. Here's what I know right now:\n\n• Infrastructure: ${ctx.healthSummary}\n• Active missions: ${ctx.missionCount}\n• Notifications: ${ctx.pendingNotifications}\n• Pending approvals: ${ctx.pendingApprovals}\n\nHow can I assist you further? You can ask about health, approvals, suggestions, or mission execution.`
}