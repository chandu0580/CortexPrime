"use client"

import { useEffect } from "react"
import { Bot, RefreshCw } from "lucide-react"
import { useExecutiveAgentStore } from "@/store/executiveAgentStore"
import { NotificationCenter, SuggestionsPanel } from "@/components/executive-agent/agent-panels"
import { ExecutiveTimeline, MissionPreparationPanel } from "@/components/executive-agent/timeline-and-preparations"
import { ExecutiveConversation } from "@/components/executive-agent/conversation"
import { PulseDot } from "@/components/executive-platform/shared"

export default function ExecutiveAgentPage() {
  const { startAgent, lastMonitoredAt } = useExecutiveAgentStore()

  useEffect(() => { startAgent() }, [startAgent])

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Bot className="w-7 h-7 text-emerald-400" />
            <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-400" />
            </span>
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Executive Agent</h1>
            <p className="text-xs text-white/40 mt-0.5 flex items-center gap-2">
              Autonomous monitoring active
              {lastMonitoredAt && <span className="text-white/20">· Last check: {new Date(lastMonitoredAt).toLocaleTimeString()}</span>}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <ExecutiveConversation />
          <MissionPreparationPanel />
        </div>
        <div className="space-y-4">
          <NotificationCenter />
          <SuggestionsPanel />
          <ExecutiveTimeline />
        </div>
      </div>
    </div>
  )
}