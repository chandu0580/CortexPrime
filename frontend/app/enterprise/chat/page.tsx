"use client"

import { useState, useRef } from "react"
import { useMissions, useStartMission } from "@/hooks/queries/useMissions"
import { Send } from "lucide-react"
import { ChatMessageList } from "@/components/enterprise"
import { Button, Input } from "@/components/enterprise/ui"
import type { ChatMessage } from "@/types/enterprise"

export default function AIChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { id: "welcome", role: "assistant", content: "Hello! I can help you create and manage missions. Try saying: \"Deploy a production Kubernetes cluster\" or \"Investigate the payment API incident\".", timestamp: new Date().toISOString() },
  ])
  const [input, setInput] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const startMission = useStartMission()
  const { data: missionsData } = useMissions()
  const missions = missionsData?.missions ?? []

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return
    const userMsg: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInput("")
    setIsStreaming(true)

    const goal = input.trim()
    const assistantId = (Date.now() + 1).toString()

    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, assistantMsg])

    const words = [
      "Analyzing", "mission", "requirements", "...",
      "Decomposing", "into", "tasks", "...",
      "Checking", "governance", "policies", "...",
      "Assigning", "agents", "...",
      "Executing", "plan", "...",
    ]

    for (let i = 0; i < words.length; i++) {
      await new Promise((r) => setTimeout(r, 80))
      setMessages((prev) =>
        prev.map((m) => m.id === assistantId ? { ...m, content: words.slice(0, i + 1).join(" ") } : m),
      )
    }

    try {
      const result = await startMission.mutateAsync({ goal })
      const finalMsg = result?.mission_id
        ? `Mission created successfully!\n\n**ID:** ${result.mission_id}\n**Status:** ${result.status}\n**Goal:** ${goal}\n\nYou can track progress in the Mission Center.`
        : `Mission launched for: "${goal}"`
      setMessages((prev) =>
        prev.map((m) => m.id === assistantId ? { ...m, content: finalMsg, metadata: { mission_id: result?.mission_id } } : m),
      )
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) => m.id === assistantId ? { ...m, content: `Failed to create mission: ${err instanceof Error ? err.message : "Unknown error"}` } : m),
      )
    }
    setIsStreaming(false)
  }

  const suggestedQueries = missions.length === 0
    ? ["Deploy a Kubernetes production namespace", "Investigate payment API high error rate", "Run security compliance scan"]
    : ["Create a new deployment mission", "Show me recent mission summaries", "Run a multi-agent audit"]

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] max-w-5xl mx-auto">
      <div className="mb-4">
        <h1 className="type-heading-xl text-[var(--text-primary)]">AI Chat</h1>
        <p className="type-body text-[var(--text-muted)] mt-1">Create and manage missions through conversation</p>
      </div>

      <div className="flex-1 surface-panel p-4 flex flex-col overflow-hidden">
        <ChatMessageList messages={messages} />

        <div className="mt-4 pt-4 border-t border-[var(--border)]">
          <div className="flex flex-wrap gap-2 mb-3">
            {suggestedQueries.map((q) => (
              <button
                key={q}
                onClick={() => setInput(q)}
                className="px-3 py-1 rounded-lg text-xs bg-[var(--surface-raised)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <Input
                placeholder="Describe what you want to accomplish..."
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                disabled={isStreaming}
              />
            </div>
            <Button
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              leftIcon={<Send className="w-4 h-4" />}
            >
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
